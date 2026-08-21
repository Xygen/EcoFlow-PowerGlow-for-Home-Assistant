"""Protobuf command builders for PowerGlow and PowerOcean keepalive."""

from __future__ import annotations

import time

from .proto_encoding import encode_field_bytes, encode_field_varint


def _sequence(seq: int) -> int:
    return seq or (int(time.time() * 1000) & 0x7FFFFFFF)


def build_energy_stream_activate_payload(seq: int = 0) -> bytes:
    """Build the verified PowerOcean EnergyStreamSwitch keepalive frame."""
    pdata = encode_field_varint(1, 1)
    return _build_envelope(
        pdata,
        destination=96,
        cmd_func=96,
        cmd_id=97,
        seq=_sequence(seq),
    )


def build_device_get_all_payload(seq: int = 0) -> bytes:
    """Build the generic app get-all request used after reconnects."""
    header = bytearray()
    header.extend(encode_field_varint(2, 32))
    header.extend(encode_field_varint(3, 32))
    header.extend(encode_field_varint(14, _sequence(seq)))
    header.extend(encode_field_bytes(23, b"app"))
    return encode_field_bytes(1, bytes(header))


def build_powerglow_parameter_payload(
    *,
    powerglow_sn: str,
    parent_sn: str,
    target_temperature: int | None = None,
    target_power: int | None = None,
    run_state_control: int | None = None,
    mode: int | None = None,
    seq: int = 0,
) -> bytes:
    """Build HeatingRodParamSet (cmd_func=212, cmd_id=99).

    Every setting in the protobuf definition is optional. Send exactly one
    target field so a temperature or power change cannot alter run state, mode,
    or tank volume as a side effect.
    """
    if not powerglow_sn or not parent_sn:
        raise ValueError("PowerGlow and parent serial numbers are required")
    values = (target_temperature, target_power, run_state_control, mode)
    if sum(value is not None for value in values) != 1:
        raise ValueError("exactly one target parameter is required")
    if target_temperature is not None and not 10 <= target_temperature <= 80:
        raise ValueError("target_temperature must be 10..80 °C")
    if target_power is not None and not 0 <= target_power <= 9000:
        raise ValueError("target_power must be 0..9000 W")
    if run_state_control not in {None, 0, 1}:
        raise ValueError("run_state_control must be 0 or 1")
    if mode not in {None, 0, 1}:
        raise ValueError("mode must be 0 (solar) or 1 (manual)")

    pdata = bytearray()
    pdata.extend(encode_field_bytes(1, powerglow_sn.encode("ascii")))
    if run_state_control is not None:
        pdata.extend(encode_field_varint(2, run_state_control))
    if mode is not None:
        pdata.extend(encode_field_varint(3, mode))
    if target_temperature is not None:
        pdata.extend(encode_field_varint(4, target_temperature))
    if target_power is not None:
        pdata.extend(encode_field_varint(5, target_power))
    return _build_envelope(
        bytes(pdata),
        # Captured from the official iOS app: PowerGlow parameter commands are
        # routed to the PowerOcean system destination (96), while cmd_func
        # remains the heating-rod function (212).
        destination=96,
        cmd_func=212,
        cmd_id=99,
        seq=_sequence(seq),
        device_sn=parent_sn,
    )


def _build_envelope(
    pdata: bytes,
    *,
    destination: int,
    cmd_func: int,
    cmd_id: int,
    seq: int,
    device_sn: str = "",
) -> bytes:
    """Build the app-compatible Send_Header_Msg envelope."""
    header = bytearray()
    header.extend(encode_field_bytes(1, pdata))
    header.extend(encode_field_varint(2, 32))
    header.extend(encode_field_varint(3, destination))
    header.extend(encode_field_varint(4, 1))
    header.extend(encode_field_varint(5, 1))
    header.extend(encode_field_varint(7, 3))
    header.extend(encode_field_varint(8, cmd_func))
    header.extend(encode_field_varint(9, cmd_id))
    header.extend(encode_field_varint(10, len(pdata)))
    header.extend(encode_field_varint(11, 1))
    header.extend(encode_field_varint(14, seq))
    header.extend(encode_field_varint(16, 3))
    header.extend(encode_field_varint(17, 1))
    header.extend(encode_field_bytes(23, b"ios"))
    if device_sn:
        header.extend(encode_field_bytes(25, device_sn.encode("ascii")))
    return encode_field_bytes(1, bytes(header))
