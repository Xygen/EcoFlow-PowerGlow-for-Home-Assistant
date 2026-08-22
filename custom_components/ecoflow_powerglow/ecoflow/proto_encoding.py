"""Shared protobuf encoding and decoding primitives.

Used by PowerGlow command builders and the Enhanced-mode telemetry parser.
"""

from __future__ import annotations

from collections.abc import Iterator

type ProtobufValue = int | bytes


def encode_varint(value: int) -> bytes:
    """Encode an int as a protobuf unsigned varint."""
    if value < 0:
        value = value + (1 << 64)
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)


def encode_field_varint(field_number: int, value: int) -> bytes:
    """Encode a varint field (wire type 0)."""
    tag = (field_number << 3) | 0
    return encode_varint(tag) + encode_varint(value)


def encode_field_bytes(field_number: int, data: bytes) -> bytes:
    """Encode a length-delimited field (wire type 2)."""
    tag = (field_number << 3) | 2
    return encode_varint(tag) + encode_varint(len(data)) + data


def decode_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    """Decode one unsigned protobuf varint and return value and next offset."""
    value = 0
    shift = 0
    while offset < len(data) and shift < 70:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
    raise ValueError("invalid protobuf varint")


def iter_protobuf_fields(
    data: bytes,
) -> Iterator[tuple[int, int, ProtobufValue]]:
    """Yield primitive protobuf fields while preserving repeats and wire types."""
    offset = 0
    while offset < len(data):
        tag, offset = decode_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07
        if field_number == 0:
            raise ValueError("invalid protobuf field number 0")

        if wire_type == 0:
            value, offset = decode_varint(data, offset)
        elif wire_type == 1:
            if offset + 8 > len(data):
                raise ValueError("truncated protobuf fixed64 field")
            value = data[offset : offset + 8]
            offset += 8
        elif wire_type == 2:
            length, offset = decode_varint(data, offset)
            if offset + length > len(data):
                raise ValueError("truncated protobuf bytes field")
            value = data[offset : offset + length]
            offset += length
        elif wire_type == 5:
            if offset + 4 > len(data):
                raise ValueError("truncated protobuf fixed32 field")
            value = data[offset : offset + 4]
            offset += 4
        else:
            raise ValueError(f"unsupported protobuf wire type: {wire_type}")

        yield field_number, wire_type, value


def _find_field(data: bytes, field_number: int, wire_type: int) -> int | bytes | None:
    """Return the first matching primitive field from a protobuf message."""
    for current_field, current_wire, value in iter_protobuf_fields(data):
        if current_field == field_number and current_wire == wire_type:
            return value
    return None


def extract_envelope_varint(payload: bytes, field_number: int) -> int | None:
    """Extract a varint from the inner EcoFlow Send_Header_Msg envelope."""
    try:
        header = _find_field(payload, 1, 2)
        if not isinstance(header, bytes):
            return None
        value = _find_field(header, field_number, 0)
        return value if isinstance(value, int) else None
    except ValueError:
        return None
