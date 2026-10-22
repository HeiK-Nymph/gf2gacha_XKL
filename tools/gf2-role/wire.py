"""GF2 game-wire frame and protobuf reader.

Frames: 3-byte little-endian sequence, 2-byte little-endian block length,
then a block holding one or more messages.
Message: 2-byte little-endian command, 2-byte little-endian payload length.

Field numbers below are observed wire facts, not an official schema.
"""

from __future__ import annotations

import struct


class WireError(ValueError):
    pass


def read_varint(data: bytes, pos: int = 0) -> tuple[int, int]:
    value = 0
    for shift in range(0, 70, 7):
        if pos >= len(data):
            raise WireError("varint truncated")
        byte = data[pos]
        pos += 1
        if shift == 63 and byte > 1:
            raise WireError("varint overflow")
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
    raise WireError("varint too long")


def protobuf(data: bytes) -> list[tuple[int, int, object]]:
    """Decode a protobuf message into (field, wire_type, value) triples."""
    fields: list[tuple[int, int, object]] = []
    pos = 0
    while pos < len(data):
        key, pos = read_varint(data, pos)
        field, wire = key >> 3, key & 7
        if field == 0:
            raise WireError("field number 0")
        if wire == 0:
            value, pos = read_varint(data, pos)
        elif wire == 1:
            if pos + 8 > len(data):
                raise WireError("fixed64 truncated")
            value = struct.unpack_from("<Q", data, pos)[0]
            pos += 8
        elif wire == 2:
            length, pos = read_varint(data, pos)
            if pos + length > len(data):
                raise WireError("length-delimited truncated")
            value = data[pos:pos + length]
            pos += length
        elif wire == 5:
            if pos + 4 > len(data):
                raise WireError("fixed32 truncated")
            value = struct.unpack_from("<I", data, pos)[0]
            pos += 4
        else:
            raise WireError(f"unsupported wire type {wire}")
        fields.append((field, wire, value))
    return fields


def frames(data: bytes) -> tuple[int, list[tuple[int, int, bytes]]]:
    """Split a reassembled stream into (sequence, command, payload) messages."""
    pos = 0
    messages: list[tuple[int, int, bytes]] = []
    last_sequence = -1
    while pos < len(data):
        if pos + 5 > len(data):
            raise WireError(f"frame header truncated at {pos}")
        sequence = int.from_bytes(data[pos:pos + 3], "little")
        length = struct.unpack_from("<H", data, pos + 3)[0]
        pos += 5
        if pos + length > len(data):
            raise WireError(f"block truncated at {pos}")
        block = data[pos:pos + length]
        pos += length
        last_sequence = sequence
        inner = 0
        while inner < len(block):
            if inner + 4 > len(block):
                raise WireError("message header truncated")
            command = struct.unpack_from("<H", block, inner)[0]
            size = struct.unpack_from("<H", block, inner + 2)[0]
            inner += 4
            if inner + size > len(block):
                raise WireError("message payload truncated")
            messages.append((sequence, command, block[inner:inner + size]))
            inner += size
    return last_sequence, messages


def blocks(fields: list[tuple[int, int, object]], number: int) -> list[bytes]:
    """All length-delimited values of one field number."""
    return [v for n, w, v in fields if n == number and w == 2 and isinstance(v, bytes)]


def scalar(fields: list[tuple[int, int, object]], number: int) -> int | None:
    for n, w, v in fields:
        if n == number and w == 0:
            return int(v)
    return None


def nested(fields: list[tuple[int, int, object]], number: int) -> list[tuple[int, int, object]]:
    """First length-delimited value of a field, decoded as a message."""
    for n, w, v in fields:
        if n == number and w == 2 and isinstance(v, bytes):
            return protobuf(v)
    return []


def walk(fields, path="", depth=0, max_depth=8):
    """Yield (path, field, wire, value) for every field, recursing into messages."""
    for n, w, v in fields:
        here = f"{path}.{n}" if path else str(n)
        yield here, n, w, v
        if w == 2 and depth < max_depth and v:
            try:
                sub = protobuf(v)
            except WireError:
                continue
            if sub:
                yield from walk(sub, here, depth + 1, max_depth)
