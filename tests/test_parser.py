from custom_components.ecoflow_powerglow.parser import (
    extract_powerglow_reports,
    parse_powerglow_detail_response,
    powerglow_operating_mode,
)


def test_parse_exact_serial_and_merge_energy_stream() -> None:
    response = {
        "data": {
            "quota": {
                "JTS1_HEATING_ROD_PARAM_REPORT": {
                    "hrSn": "HF33Z1234567890",
                    "mode": 0,
                    "temp": 58,
                    "targetTemp": 60,
                    "targetPower": 3500,
                    "waterTankVolume": 1500,
                    "runStat": 1,
                },
                "JTS1_HEATING_ROD_ENERGY_STREAM_REPORT": {
                    "hrEnergyStream": [
                        {"hrSn": "HF33Z1234567890", "hrPwr": 1750, "fromPv": 1750},
                        {"hrSn": "HF33Z0000000000", "hrPwr": 9000},
                    ]
                },
            }
        }
    }
    assert extract_powerglow_reports(response) == {"HF33Z1234567890", "HF33Z0000000000"}
    parsed = parse_powerglow_detail_response(response, "HF33Z1234567890")
    assert parsed["heating_power_w"] == 1750
    assert parsed["target_temperature_c"] == 60
    assert parsed["power_from_pv_w"] == 1750


def test_operating_mode_combines_run_state_and_mode() -> None:
    assert powerglow_operating_mode({"run_state_raw": 0, "mode_raw": 1}) == "off"
    assert powerglow_operating_mode({"run_state_raw": 1, "mode_raw": 0}) == "solar"
    assert powerglow_operating_mode({"run_state_raw": 1, "mode_raw": 1}) == "manual"
    assert powerglow_operating_mode({"run_state_raw": 2, "mode_raw": 0}) is None
