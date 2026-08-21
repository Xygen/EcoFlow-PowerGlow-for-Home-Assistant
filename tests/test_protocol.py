import pytest

from custom_components.ecoflow_powerglow.ecoflow.energy_stream import (
    build_powerglow_parameter_payload,
)
from custom_components.ecoflow_powerglow.ecoflow.proto_encoding import (
    extract_envelope_varint,
)


def test_powerglow_command_is_stable_for_known_values() -> None:
    payload = build_powerglow_parameter_payload(
        powerglow_sn="HF33Z1234567890",
        parent_sn="HJ31Z1234567890",
        target_temperature=60,
        seq=1,
    )
    assert payload.hex() == (
        "0a480a130a0f484633335a31323334353637383930203c10201860200128013803"
        "40d4014863501358017001800103880101ba0103696f73ca010f484a33315a313233"
        "34353637383930"
    )


@pytest.mark.parametrize("temperature", [9, 81])
def test_rejects_unsafe_temperature(temperature: int) -> None:
    with pytest.raises(ValueError):
        build_powerglow_parameter_payload(
            powerglow_sn="HF33Z1234567890",
            parent_sn="HJ31Z1234567890",
            target_temperature=temperature,
            seq=1,
        )


def test_rejects_multiple_target_parameters() -> None:
    with pytest.raises(ValueError):
        build_powerglow_parameter_payload(
            powerglow_sn="HF33Z1234567890",
            parent_sn="HJ31Z1234567890",
            target_temperature=60,
            target_power=3500,
            seq=1,
        )


def test_powerglow_run_and_mode_commands_use_verified_optional_fields() -> None:
    run_payload = build_powerglow_parameter_payload(
        powerglow_sn="HF33Z1234567890",
        parent_sn="HJ31Z1234567890",
        run_state_control=1,
        seq=36,
    )
    mode_payload = build_powerglow_parameter_payload(
        powerglow_sn="HF33Z1234567890",
        parent_sn="HJ31Z1234567890",
        mode=0,
        seq=37,
    )
    assert b"\x0a\x0fHF33Z1234567890\x10\x01" in run_payload
    assert b"\x0a\x0fHF33Z1234567890\x18\x00" in mode_payload


def test_powerglow_accepts_fine_grained_target_power() -> None:
    payload = build_powerglow_parameter_payload(
        powerglow_sn="HF33Z1234567890",
        parent_sn="HJ31Z1234567890",
        target_power=19,
        seq=38,
    )
    assert b"\x0a\x0fHF33Z1234567890\x28\x13" in payload


def test_extract_matching_sequence_from_captured_set_reply() -> None:
    reply = bytes.fromhex(
        "0a460a120a1058585858585858585858585858585858106018202001280140d4"
        "01486350125801600170247881a601800103880101c201105858585858585858"
        "5858585858585858"
    )
    assert extract_envelope_varint(reply, 8) == 212
    assert extract_envelope_varint(reply, 9) == 99
    assert extract_envelope_varint(reply, 14) == 36
