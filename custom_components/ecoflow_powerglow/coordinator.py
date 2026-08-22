"""Data coordinator and write dispatcher for PowerGlow."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PowerGlowApiClient
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONFIRMED_WRITE_GRACE_SECONDS,
    DOMAIN,
    ENERGY_STREAM_KEEPALIVE_SECONDS,
    LATEST_QUOTAS_INTERVAL_SECONDS,
    UPDATE_INTERVAL_SECONDS,
)
from .ecoflow.cloud_mqtt import EcoFlowMQTTClient
from .ecoflow.energy_stream import build_powerglow_parameter_payload
from .ecoflow.proto_encoding import extract_envelope_varint
from .parser import parse_powerglow_mqtt_payload

_LOGGER = logging.getLogger(__name__)
_COMMAND_CONFIRM_TIMEOUT = 5


@dataclass(slots=True)
class _PendingCommand:
    serial: str
    key: str
    value: int
    confirmed: asyncio.Future[None]
    broker_echoed: asyncio.Future[None]


@dataclass(slots=True)
class _ConfirmedWrite:
    value: int
    expires_at: float


class PowerGlowCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Poll consumer details and maintain one MQTT writer per PowerOcean."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.api = PowerGlowApiClient(
            async_get_clientsession(hass),
            entry.data[CONF_EMAIL],
            entry.data[CONF_PASSWORD],
        )
        self.devices: dict[str, dict[str, Any]] = {}
        self._mqtt: dict[str, EcoFlowMQTTClient] = {}
        self._pending_commands: dict[int, _PendingCommand] = {}
        self._confirmed_writes: dict[tuple[str, str], _ConfirmedWrite] = {}
        self._command_sequence = int(time.time() * 1000) & 0x7FFFFFFF
        self.mqtt_frames: list[dict[str, Any]] = []
        self._energy_stream_handle: asyncio.TimerHandle | None = None
        self._latest_quotas_handle: asyncio.TimerHandle | None = None
        self._initialized = False

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            if not self._initialized:
                await self.api.async_login()
                self.devices = await self.api.async_discover_powerglows()
                if not self.devices:
                    raise UpdateFailed("No PowerGlow found")
                self._initialized = True

            # Telemetry uses the consumer HTTP API and must remain available
            # even when the optional MQTT write channel cannot connect.
            try:
                await self._async_setup_mqtt()
            except Exception as exc:
                _LOGGER.warning("PowerGlow controls unavailable: %s", exc)

            data: dict[str, dict[str, Any]] = {}
            for serial, device in self.devices.items():
                if not device.get("parent_sn"):
                    data[serial] = {}
                    continue
                device_data = await self.api.async_read_powerglow(device)
                self._apply_confirmed_writes(serial, device_data)
                data[serial] = device_data
            return data
        except UpdateFailed:
            raise
        except Exception as exc:
            raise UpdateFailed(f"EcoFlow PowerGlow update failed: {exc}") from exc

    async def _async_setup_mqtt(self) -> None:
        parent_serials = {
            item["parent_sn"]
            for item in self.devices.values()
            if item.get("parent_sn") and item["parent_sn"] not in self._mqtt
        }
        if not parent_serials:
            return

        credentials = await self.api.async_get_mqtt_credentials()
        account = credentials.get("certificateAccount") or credentials.get("userName", "")
        password = credentials.get("certificatePassword") or credentials.get("password", "")
        if not account or not password:
            raise ConnectionError("Incomplete MQTT credentials")

        for parent_sn in parent_serials:
            client = EcoFlowMQTTClient(
                certificate_account=account,
                certificate_password=password,
                device_sn=parent_sn,
                message_handler=lambda topic, payload, parent=parent_sn: self._schedule_mqtt_frame(
                    parent, topic, payload
                ),
                user_id=self.api.user_id,
                wss_mode=True,
                enhanced_mode=True,
            )
            created = await self.hass.async_add_executor_job(client.create_client)
            if not created:
                _LOGGER.warning(
                    "PowerGlow MQTT client creation failed for parent %s…",
                    parent_sn[:4],
                )
                continue
            connected = await self.hass.async_add_executor_job(client.connect)
            if not connected:
                _LOGGER.warning(
                    "PowerGlow MQTT connection failed for parent %s…",
                    parent_sn[:4],
                )
                continue
            await self.hass.async_add_executor_job(client.start_loop)
            self._mqtt[parent_sn] = client

        if self._mqtt:
            self._ensure_mqtt_maintenance()

    async def async_set_parameter(self, serial: str, key: str, value: int) -> None:
        """Write exactly one optional PowerGlow parameter."""
        device = self.devices[serial]
        if key not in {
            "target_temperature_c",
            "target_power_w",
            "run_state_raw",
            "mode_raw",
        }:
            raise ValueError(f"Unsupported writable PowerGlow parameter: {key}")

        seq = self._next_command_sequence()
        payload = build_powerglow_parameter_payload(
            powerglow_sn=serial,
            parent_sn=device["parent_sn"],
            target_temperature=value if key == "target_temperature_c" else None,
            target_power=value if key == "target_power_w" else None,
            run_state_control=value if key == "run_state_raw" else None,
            mode=value if key == "mode_raw" else None,
            seq=seq,
        )
        self._record_command_frame(device["parent_sn"], key, value, payload)
        client = self._mqtt.get(device["parent_sn"])
        if client is None or not client.is_connected():
            raise ConnectionError("PowerOcean MQTT writer is not connected")

        pending = _PendingCommand(
            serial,
            key,
            value,
            self.hass.loop.create_future(),
            self.hass.loop.create_future(),
        )
        self._pending_commands[seq] = pending
        try:
            sent = await self.hass.async_add_executor_job(client.send_proto_set, payload)
            if not sent:
                raise ConnectionError("EcoFlow rejected the MQTT publish")
            try:
                await asyncio.wait_for(
                    asyncio.shield(pending.confirmed), _COMMAND_CONFIRM_TIMEOUT
                )
            except TimeoutError as exc:
                if pending.broker_echoed.done():
                    # QoS delivery of the device SET reply is not guaranteed.
                    # The broker echo proves that the exact command reached the
                    # app topic; accept it provisionally and let the regular
                    # HTTP poll remain the authoritative follow-up.
                    self._apply_pending_value(pending)
                    self._append_mqtt_frame(
                        {
                            "timestamp": datetime.now(UTC).isoformat(),
                            "kind": "broker_echo_fallback",
                            "key": key,
                            "value": value,
                        }
                    )
                    _LOGGER.debug(
                        "PowerGlow SET reply missing; accepted matching broker echo"
                    )
                    return
                raise ConnectionError(
                    "EcoFlow did not confirm the MQTT command"
                ) from exc
        finally:
            self._pending_commands.pop(seq, None)

    def _next_command_sequence(self) -> int:
        """Return a non-zero sequence not currently awaiting confirmation."""
        while True:
            self._command_sequence = (self._command_sequence + 1) & 0x7FFFFFFF
            if self._command_sequence and self._command_sequence not in self._pending_commands:
                return self._command_sequence

    def _schedule_mqtt_frame(self, parent_sn: str, topic: str, payload: bytes) -> None:
        """Safely bridge a Paho-thread callback to Home Assistant's event loop."""
        loop = self.hass.loop
        if loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._record_mqtt_frame, parent_sn, topic, payload)
        except RuntimeError:
            # Home Assistant may close the loop while Paho is finishing unload.
            return

    def _record_command_frame(
        self, parent_sn: str, key: str, value: int, payload: bytes
    ) -> None:
        """Record a redacted HA-originated command for protocol comparison."""
        self._append_mqtt_frame(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "kind": "ha_set",
                "key": key,
                "value": value,
                "size": len(payload),
                "hex": self._redact_payload(payload, parent_sn).hex(),
            }
        )

    def _record_mqtt_frame(
        self, parent_sn: str, topic: str, payload: bytes
    ) -> None:
        """Record official-app SET traffic and device SET replies."""
        if topic.endswith("/thing/property/set_reply") or topic.endswith("/set_reply"):
            kind = "set_reply"
        elif topic.endswith("/thing/property/set"):
            kind = "observed_set"
        else:
            parsed_keys = self._apply_mqtt_telemetry(parent_sn, payload)
            if parsed_keys or self._payload_mentions_powerglow(parent_sn, payload):
                self._append_mqtt_frame(
                    {
                        "timestamp": datetime.now(UTC).isoformat(),
                        "kind": "telemetry",
                        "channel": self._telemetry_channel(topic),
                        "size": len(payload),
                        "parsed_keys": sorted(parsed_keys),
                    }
                )
            return
        self._append_mqtt_frame(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "kind": kind,
                "size": len(payload),
                "hex": self._redact_payload(payload, parent_sn).hex(),
            }
        )
        if kind == "observed_set":
            self._record_command_broker_echo(payload)
        elif kind == "set_reply":
            self._apply_command_confirmation(payload)

    def _apply_mqtt_telemetry(self, parent_sn: str, payload: bytes) -> set[str]:
        """Merge Enhanced-mode JSON or protobuf telemetry into coordinator data."""
        serials = [
            serial
            for serial, device in self.devices.items()
            if device.get("parent_sn") == parent_sn
        ]
        allow_unscoped = len(serials) == 1
        updated_data = dict(self.data or {})
        parsed_keys: set[str] = set()

        for serial in serials:
            parsed = parse_powerglow_mqtt_payload(
                payload,
                serial,
                allow_unscoped=allow_unscoped,
            )
            if not parsed:
                continue
            device_data = dict(updated_data.get(serial, {}))
            device_data.update(parsed)
            self._apply_confirmed_writes(
                serial,
                device_data,
                reported_keys=set(parsed),
            )
            updated_data[serial] = device_data
            parsed_keys.update(parsed)

        if parsed_keys:
            self.async_set_updated_data(updated_data)
        return parsed_keys

    def _payload_mentions_powerglow(self, parent_sn: str, payload: bytes) -> bool:
        """Return whether a frame contains a child serial in plain protobuf bytes."""
        return any(
            serial.encode("ascii", errors="ignore") in payload
            for serial, device in self.devices.items()
            if device.get("parent_sn") == parent_sn
        )

    @staticmethod
    def _telemetry_channel(topic: str) -> str:
        """Return a non-sensitive diagnostic topic label."""
        if topic.endswith("/quota"):
            return "quota"
        if topic.endswith("/get_reply"):
            return "get_reply"
        if "/app/device/property/" in topic:
            return "property"
        return "other"

    def _ensure_mqtt_maintenance(self) -> None:
        """Keep the Enhanced-mode stream and quota replies alive."""
        if self._energy_stream_handle is None:
            self._energy_stream_handle = self.hass.loop.call_later(
                ENERGY_STREAM_KEEPALIVE_SECONDS,
                self._send_energy_stream_keepalive,
            )
        if self._latest_quotas_handle is None:
            self._latest_quotas_handle = self.hass.loop.call_later(
                LATEST_QUOTAS_INTERVAL_SECONDS,
                self._send_latest_quotas,
            )

    def _send_energy_stream_keepalive(self) -> None:
        """Re-activate PowerOcean energy-stream reports."""
        self._energy_stream_handle = None
        for client in self._mqtt.values():
            if client.is_connected():
                self.hass.async_add_executor_job(client.send_energy_stream_switch)
        if self._mqtt:
            self._ensure_mqtt_maintenance()

    def _send_latest_quotas(self) -> None:
        """Request the newest app-level quota snapshot."""
        self._latest_quotas_handle = None
        for client in self._mqtt.values():
            if client.is_connected():
                self.hass.async_add_executor_job(client.send_latest_quotas)
        if self._mqtt:
            self._ensure_mqtt_maintenance()

    def _matching_pending_command(self, payload: bytes) -> _PendingCommand | None:
        """Return a pending PowerGlow command matching this envelope sequence."""
        if (
            extract_envelope_varint(payload, 8) != 212
            or extract_envelope_varint(payload, 9) != 99
        ):
            return None
        seq = extract_envelope_varint(payload, 14)
        return self._pending_commands.get(seq) if seq is not None else None

    def _record_command_broker_echo(self, payload: bytes) -> None:
        """Record that the broker echoed an exact pending SET envelope."""
        pending = self._matching_pending_command(payload)
        if pending is not None and not pending.broker_echoed.done():
            pending.broker_echoed.set_result(None)

    def _apply_command_confirmation(self, payload: bytes) -> None:
        """Publish a matching device-confirmed command value immediately to HA."""
        pending = self._matching_pending_command(payload)
        if pending is None or pending.confirmed.done():
            return

        self._apply_pending_value(pending)
        pending.confirmed.set_result(None)

    def _apply_pending_value(self, pending: _PendingCommand) -> None:
        """Publish a confirmed or provisionally broker-echoed value to HA."""
        self._confirmed_writes[(pending.serial, pending.key)] = _ConfirmedWrite(
            pending.value,
            self.hass.loop.time() + CONFIRMED_WRITE_GRACE_SECONDS,
        )
        updated_data = dict(self.data)
        device_data = dict(updated_data.get(pending.serial, {}))
        device_data[pending.key] = float(pending.value)
        updated_data[pending.serial] = device_data
        self.async_set_updated_data(updated_data)

    def _apply_confirmed_writes(
        self,
        serial: str,
        device_data: dict[str, Any],
        *,
        reported_keys: set[str] | None = None,
    ) -> None:
        """Prevent stale cloud snapshots from undoing a confirmed local write."""
        now = self.hass.loop.time()
        for identity, write in list(self._confirmed_writes.items()):
            write_serial, key = identity
            if write_serial != serial:
                continue
            if write.expires_at <= now:
                self._confirmed_writes.pop(identity, None)
                continue
            cloud_matches = False
            if reported_keys is None or key in reported_keys:
                try:
                    cloud_matches = float(device_data[key]) == float(write.value)
                except (KeyError, TypeError, ValueError):
                    pass
            if cloud_matches:
                self._confirmed_writes.pop(identity, None)
            else:
                device_data[key] = float(write.value)

    def _redact_payload(self, payload: bytes, parent_sn: str) -> bytes:
        redacted = payload
        serials = [parent_sn, *self.devices]
        for serial in serials:
            encoded = serial.encode("ascii", errors="ignore")
            if encoded:
                redacted = redacted.replace(encoded, b"X" * len(encoded))
        return redacted

    def _append_mqtt_frame(self, frame: dict[str, Any]) -> None:
        self.mqtt_frames.append(frame)
        del self.mqtt_frames[:-20]

    async def async_shutdown(self) -> None:
        for handle in (
            self._energy_stream_handle,
            self._latest_quotas_handle,
        ):
            if handle is not None:
                handle.cancel()
        self._energy_stream_handle = None
        self._latest_quotas_handle = None
        self._confirmed_writes.clear()
        for client in self._mqtt.values():
            await self.hass.async_add_executor_job(client.disconnect)
        self._mqtt.clear()
