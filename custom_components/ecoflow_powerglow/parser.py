"""PowerGlow consumer-detail parser."""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections.abc import Iterator
from typing import Any

_FIELD_MAP = {
    "heatingPower": "heating_power_w",
    "hrPwr": "heating_power_w",
    "targetPower": "target_power_w",
    "temp": "water_temperature_c",
    "targetTemp": "target_temperature_c",
    "fromPv": "power_from_pv_w",
    "fromGrid": "power_from_grid_w",
    "fromBat": "power_from_battery_w",
    "waterTankVolume": "water_tank_volume_l",
    "selfcheckPercent": "self_check_pct",
    "mode": "mode_raw",
    "runFlag": "run_flag_raw",
    "runStat": "run_state_raw",
    "errorCode": "error_code_raw",
}
_PARAM_SUFFIX = "JTS1_HEATING_ROD_PARAM_REPORT"
_ENERGY_SUFFIX = "JTS1_HEATING_ROD_ENERGY_STREAM_REPORT"
_SERIAL_RE = re.compile(r"^[A-Z0-9]{12,32}$")


def parse_powerglow_detail_response(response: dict[str, Any], serial: str) -> dict[str, Any]:
    """Parse the two known reports for one exact PowerGlow serial."""
    result: dict[str, Any] = {}
    for kind, report in _iter_reports(response):
        items = report.get("hrEnergyStream", []) if kind == "energy" else [report]
        if not isinstance(items, list):
            items = [report]
        for item in items:
            if not isinstance(item, dict) or _decode_serial(item.get("hrSn")) != serial:
                continue
            _merge_powerglow_fields(item, result)
    return result


def parse_powerglow_mqtt_payload(
    payload: bytes,
    serial: str,
    *,
    allow_unscoped: bool = False,
) -> dict[str, Any]:
    """Parse a JSON MQTT update for one PowerGlow.

    Enhanced-mode replies use several shapes: the consumer-detail report,
    direct incremental items carrying ``hrSn``, and PowerOcean quota maps with
    ``ems_heating_rod.*`` keys. Unscoped quota values are accepted only when
    the parent has exactly one PowerGlow, so one accessory cannot update
    another accessory by accident.
    """
    try:
        response = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(response, dict):
        return {}

    result = parse_powerglow_detail_response(response, serial)
    for item in _iter_dicts(response):
        if _decode_serial(item.get("hrSn")) == serial:
            _merge_powerglow_fields(item, result)

        if not allow_unscoped:
            continue

        heating_rod = item.get("ems_heating_rod")
        if isinstance(heating_rod, dict):
            _merge_powerglow_fields(heating_rod, result)

        scoped: dict[str, Any] = {}
        prefix = "ems_heating_rod."
        for key, value in item.items():
            if isinstance(key, str) and key.startswith(prefix):
                scoped[key.removeprefix(prefix)] = value
        _merge_powerglow_fields(scoped, result)

    return result


def _merge_powerglow_fields(item: dict[str, Any], result: dict[str, Any]) -> None:
    """Merge known numeric PowerGlow fields from one report item."""
    for source, target in _FIELD_MAP.items():
        if source in item:
            try:
                result[target] = float(item[source])
            except (TypeError, ValueError):
                pass


def _iter_dicts(value: Any) -> Iterator[dict[str, Any]]:
    """Yield every dictionary in an arbitrary JSON value."""
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_dicts(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_dicts(nested)


def extract_powerglow_reports(response: dict[str, Any]) -> set[str]:
    """Return all verifiable PowerGlow serials in known reports."""
    serials: set[str] = set()
    for kind, report in _iter_reports(response):
        items = report.get("hrEnergyStream", []) if kind == "energy" else [report]
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and (serial := _decode_serial(item.get("hrSn"))):
                serials.add(serial)
    return serials


def powerglow_operating_mode(data: dict[str, Any]) -> str | None:
    """Return the user-facing operating mode from run state and mode reports."""
    try:
        run_state = int(data["run_state_raw"])
    except (KeyError, TypeError, ValueError):
        return None
    if run_state == 0:
        return "off"
    if run_state != 1:
        return None

    try:
        mode = int(data["mode_raw"])
    except (KeyError, TypeError, ValueError):
        return None
    return {0: "solar", 1: "manual"}.get(mode)


def _iter_reports(value: Any) -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        for key, nested in value.items():
            if isinstance(key, str) and isinstance(nested, dict):
                if key.endswith(_PARAM_SUFFIX):
                    yield "parameter", nested
                elif key.endswith(_ENERGY_SUFFIX):
                    yield "energy", nested
            yield from _iter_reports(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_reports(nested)


def _decode_serial(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return ""
    value = value.strip()
    if _SERIAL_RE.fullmatch(value.upper()):
        return value.upper()
    try:
        decoded = base64.b64decode(value, validate=True).decode("ascii").strip().upper()
    except (binascii.Error, UnicodeDecodeError):
        return ""
    return decoded if _SERIAL_RE.fullmatch(decoded) else ""
