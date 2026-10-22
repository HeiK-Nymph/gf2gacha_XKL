"""Correlate an archived assist snapshot with static tables.

Prints, per character: identity, weapon instance and config, weapon mods with
their decoded affix slots, and plugin instance ids. Used to build the panel
derivation corpus; no account identifiers beyond in-game ids are printed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import struct
from pathlib import Path

_spec = importlib.util.spec_from_file_location("snap", Path(__file__).with_name("assist_snapshot.py"))
snap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(snap)
wire = snap.wire


def table_rows(directory: Path, name: str) -> dict[int, list]:
    path = directory / f"{name}.bytes"
    data = path.read_bytes()
    offset = struct.unpack_from("<I", data, 0)[0]
    rows = [wire.protobuf(row) for row in wire.blocks(wire.protobuf(data[offset + 4:]), 1)]
    result = {}
    for row in rows:
        ident = wire.scalar(row, 1)
        if ident is not None:
            result[ident] = row
    return result


def affix_slots(mod: list, tables: dict) -> list[dict]:
    """Split a weapon mod's packed affix integers into (type, amount) pairs."""
    config_id = wire.scalar(mod, 2)
    config = tables["WeaponModData"].get(config_id, [])
    slots = []
    for field in (3, 7):
        for value in [v for n, w, v in mod if n == field and w == 0]:
            if not isinstance(value, int):
                continue
            lanes = []
            for shift in (0, 16, 32, 48):
                lane = (value >> shift) & 0xFFFF
                if lane:
                    lanes.append({"raw": lane, "type": lane >> 8, "amount": lane & 0xFF})
            if lanes:
                slots.append({"field": field, "value": value, "lanes": lanes})
    return slots


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server-stream", required=True)
    ap.add_argument("--tables", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()

    tables_dir = Path(args.tables)
    tables = {
        name: table_rows(tables_dir, name)
        for name in ["WeaponModData", "GunWeaponData", "GunData", "AffixPlanIdData"]
    }

    characters = snap.assist_characters(Path(args.server_stream).read_bytes())
    report = []
    for character in characters:
        menus = snap.menu_instances(character["snapshot"])
        mods = []
        for payload in menus["mods"]:
            mod = wire.protobuf(payload)
            mods.append({
                "instance": wire.scalar(mod, 1),
                "configId": wire.scalar(mod, 2),
                "slots": affix_slots(mod, tables),
            })
        weapons = []
        for weapon_payload in menus["weapons"]:
            weapon = wire.protobuf(weapon_payload)
            config_id = wire.scalar(weapon, 2)
            config = tables["GunWeaponData"].get(config_id, [])
            mod_refs = [v for n, w, v in weapon if n == 8 and w == 2]
            weapons.append({
                "instance": wire.scalar(weapon, 1),
                "configId": config_id,
                "level": wire.scalar(weapon, 3),
                "modRefs": [b.hex() for b in mod_refs],
                "configFields": [{"field": n, "value": v} for n, w, v in config if w == 0],
            })
        report.append({
            "role": character["role"],
            "weapons": weapons,
            "mods": mods,
            "pluginCount": len(menus["plugins"]),
        })

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
