"""Decode a captured 10429 assist response into character/snapshot records.

Observed layout: top-level repeated field 3 = one character entry; field 2 =
role identity (id/level/rarity/voice/combat power); field 3 = character
snapshot whose field 30 holds equipment menus (field 6 plugin, 9 weapon mod,
11 weapon instances).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("wire", Path(__file__).with_name("wire.py"))
wire = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wire)


def assist_characters(server_stream: bytes) -> list[dict]:
    """Parse a reassembled server stream and return every 10429 character."""
    _, messages = wire.frames(server_stream)
    result = []
    for _, command, payload in messages:
        if command != 10429:
            continue
        top = wire.protobuf(payload)
        for entry in wire.blocks(top, 3):
            fields = wire.protobuf(entry)
            role_blocks = wire.blocks(fields, 2)
            snapshot_blocks = wire.blocks(fields, 3)
            role = wire.protobuf(role_blocks[0]) if role_blocks else []
            snapshot = wire.protobuf(snapshot_blocks[0]) if snapshot_blocks else []
            result.append({
                "role": {
                    "id": wire.scalar(role, 1),
                    "level": wire.scalar(role, 3),
                    "rarity": wire.scalar(role, 6),
                    "voiceCode": wire.scalar(role, 7),
                    "combatPower": wire.scalar(role, 8),
                },
                "snapshot": snapshot,
                "snapshotBytes": len(snapshot_blocks[0]) if snapshot_blocks else 0,
            })
    return result


def menu_instances(snapshot: list) -> dict[str, list[bytes]]:
    """Equipment instance payloads out of snapshot field 30."""
    for n, w, v in snapshot:
        if n == 30 and w == 2 and isinstance(v, bytes):
            menus = wire.protobuf(v)
            return {
                "plugins": wire.blocks(menus, 6),
                "mods": wire.blocks(menus, 9),
                "weapons": wire.blocks(menus, 11),
            }
    return {"plugins": [], "mods": [], "weapons": []}
