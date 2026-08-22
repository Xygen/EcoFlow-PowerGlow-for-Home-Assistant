from custom_components.ecoflow_powerglow.parser import (
    extract_powerglow_reports,
    parse_powerglow_detail_response,
    parse_powerglow_mqtt_payload,
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


def test_parse_mqtt_incremental_report_by_serial() -> None:
    payload = b'{"params":{"hrSn":"HF33Z1234567890","hrPwr":927,"temp":54}}'
    parsed = parse_powerglow_mqtt_payload(payload, "HF33Z1234567890")
    assert parsed == {"heating_power_w": 927.0, "water_temperature_c": 54.0}


def test_parse_mqtt_powerocean_heating_rod_quota_for_single_child() -> None:
    payload = (
        b'{"data":{"quotaMap":{"ems_heating_rod.heatingPower":101,'
        b'"ems_heating_rod.targetPower":19,"ems_heating_rod.targetTemp":61}}}'
    )
    assert parse_powerglow_mqtt_payload(payload, "HF33Z1234567890") == {}
    assert parse_powerglow_mqtt_payload(
        payload,
        "HF33Z1234567890",
        allow_unscoped=True,
    ) == {
        "heating_power_w": 101.0,
        "target_power_w": 19.0,
        "target_temperature_c": 61.0,
    }


def test_parse_mqtt_fast_powerglow_load_report() -> None:
    serial = "HF33Z12345678901"
    payload = bytes.fromhex(
        "0a530a1e0a1c0a1058585858585858585858585858585858150000c842250000c84210"
        "6018202001280140d4014821501e580170aea98f347881a601800103880101c2011058"
        "5858585858585858585858585858580a5a0a250a230a1708d701121058585858585858"
        "58585858585858585818011500201e452500201e45106018202001280140f101482150"
        "25580170aea98f347881a601800103880101c201105858585858585858585858585858"
        "5858"
    ).replace(b"X" * 16, serial.encode())
    assert parse_powerglow_mqtt_payload(payload, serial) == {
        "heating_power_w": 100.0
    }
    assert parse_powerglow_mqtt_payload(payload, "HF33Z00000000000") == {}


def test_parse_mqtt_fast_powerglow_zero_load_report() -> None:
    serial = "HF33Z12345678901"
    payload = bytes.fromhex(
        "0a490a140a120a1058585858585858585858585858585858106018202001280140d401"
        "48215014580170f3afee337881a601800103880101c201105858585858585858585858"
        "58585858580a500a1b0a190a1708d7011210585858585858585858585858585858581"
        "801106018202001280140f1014821501b580170f3afee337881a601800103880101c2"
        "011058585858585858585858585858585858"
    ).replace(b"X" * 16, serial.encode())
    assert parse_powerglow_mqtt_payload(payload, serial) == {
        "heating_power_w": 0.0
    }


def test_parse_mqtt_powerglow_parameter_report() -> None:
    serial = "HF33Z12345678901"
    payload = bytes.fromhex(
        "0a5c0a2f0a105858585858585858585858585858585810001803200028003500006442"
        "3d0000a0424001480050dc0b5864600010601820200140d4014808502f580178d40180"
        "0103880101c2011058585858585858585858585858585858"
    ).replace(b"X" * 16, serial.encode())
    assert parse_powerglow_mqtt_payload(payload, serial) == {
        "mode_raw": 0.0,
        "water_temperature_c": 57.0,
        "run_state_raw": 1.0,
        "error_code_raw": 0.0,
        "water_tank_volume_l": 1500.0,
        "self_check_pct": 100.0,
        "run_flag_raw": 0.0,
    }
