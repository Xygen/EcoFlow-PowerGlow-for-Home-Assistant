"""PowerGlow consumer-detail parser."""

from __future__ import annotations

import base64
import binascii
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
            for source, target in _FIELD_MAP.items():
                if source in item:
                    try:
                        result[target] = float(item[source])
                    except (TypeError, ValueError):
                        pass
    return result


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
