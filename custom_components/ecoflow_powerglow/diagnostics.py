"""Diagnostics support for EcoFlow PowerGlow."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_EMAIL, CONF_PASSWORD
from .coordinator import PowerGlowCoordinator

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD, "serial", "parent_sn"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return a privacy-safe snapshot without tokens or MQTT credentials."""
    coordinator: PowerGlowCoordinator = entry.runtime_data
    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "devices": [
            {
                "serial_prefix": serial[:4],
                "parent_prefix": str(device.get("parent_sn", ""))[:4],
                "has_parent": bool(device.get("parent_sn")),
            }
            for serial, device in coordinator.devices.items()
        ],
        "data_keys": {
            serial[:4]: sorted(values)
            for serial, values in coordinator.data.items()
        },
        "mqtt_connected": {
            parent[:4]: client.is_connected()
            for parent, client in coordinator._mqtt.items()
        },
        "mqtt_frames": list(coordinator.mqtt_frames),
    }
