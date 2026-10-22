"""Turn a 10429 assist response into a user-facing character report.

Output is plain JSON: character name/level/rarity/combat power and the equipped
weapon with its name and level. Weapon mods are intentionally out of scope for
the mini-program feature; their decode lives in the research notes. All names
are resolved from the game's local tables; no network access and no account
identifiers beyond the in-game UID.

Example:
    python assist_report.py --server-stream assist.bin \
        --tables "<game>/GF2_Exilium_Data/LocalCache/Data/Table" --out report.json
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

# Affix lanes at or above this value are calibration markers, not stats.
CALIBRATION_THRESHOLD = 64


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


def affix_ranges(directory: Path) -> dict[int, dict]:
    """Affix type code -> observed value range, from AffixGroupData."""
    path = directory / "AffixGroupData.bytes"
    data = path.read_bytes()
    offset = struct.unpack_from("<I", data, 0)[0]
    rows = [wire.protobuf(row) for row in wire.blocks(wire.protobuf(data[offset + 4:]), 1)]
    result: dict[int, dict] = {}
    for row in rows:
        type_code = wire.scalar(row, 3)
        low = wire.scalar(row, 5)
        high = wire.scalar(row, 6)
        if type_code is None:
            continue
        entry = result.setdefault(type_code, {"min": low, "max": high})
        if low is not None:
            entry["min"] = min(entry["min"] or low, low)
        if high is not None:
            entry["max"] = max(entry["max"] or high, high)
    return result


def language_map(directory: Path) -> dict[int, str]:
    path = directory / "LangPackageTableCnData.bytes"
    data = path.read_bytes()
    offset = struct.unpack_from("<I", data, 0)[0]
    rows = [wire.protobuf(row) for row in wire.blocks(wire.protobuf(data[offset + 4:]), 1)]
    result = {}
    for row in rows:
        key = wire.scalar(row, 1)
        text = next((v.decode("utf-8", "replace") for n, w, v in row
                     if n == 2 and w == 2 and isinstance(v, bytes)), None)
        if key is not None and text:
            result[key] = text
    return result


def localized(field: list, lang: dict[int, str]) -> str | None:
    """Resolve a nested {1: languageKey} payload to text."""
    if not isinstance(field, bytes):
        return None
    try:
        sub = wire.protobuf(field)
    except wire.WireError:
        return None
    for _, w, value in sub:
        if w == 0:
            text = lang.get(value)
            if text:
                return text
    return None


def stat_name_table(directory: Path) -> dict[int, str]:
    """Affix type code -> stat key such as 'pow' / 'max_hp'."""
    path = directory / "LanguagePropertyData.bytes"
    data = path.read_bytes()
    offset = struct.unpack_from("<I", data, 0)[0]
    rows = [wire.protobuf(row) for row in wire.blocks(wire.protobuf(data[offset + 4:]), 1)]
    result = {}
    for row in rows:
        ident = wire.scalar(row, 1)
        key = next((v.decode("utf-8", "replace") for n, w, v in row
                    if n == 4 and w == 2 and isinstance(v, bytes)), None)
        if ident is not None and key:
            result[ident] = key
    return result


def decode_mod(mod_fields: list, mod_configs: dict, stat_names: dict, ranges: dict) -> dict:
    config_id = wire.scalar(mod_fields, 2)
    config = mod_configs.get(config_id, [])
    affixes = []
    calibration = 0
    for field in (3, 7):
        for value in [v for n, w, v in mod_fields if n == field and w == 0]:
            if not isinstance(value, int):
                continue
            for shift in (0, 16, 32, 48):
                lane = (value >> shift) & 0xFFFF
                if not lane:
                    continue
                type_code, amount = lane >> 8, lane & 0xFF
                if amount >= CALIBRATION_THRESHOLD:
                    calibration += 1
                else:
                    affixes.append({
                        "type": type_code,
                        "nameHint": stat_names.get(type_code),
                        "value": amount,
                        "range": ranges.get(type_code),
                    })
    return {
        "configId": config_id,
        "instanceId": wire.scalar(mod_fields, 1),
        "affixes": affixes,
        "calibrationMarks": calibration,
        "configFields": [v for n, w, v in config if w == 0][:8],
    }


def build_report(stream_path: Path, tables_dir: Path) -> dict:
    lang = language_map(tables_dir)
    stat_names = stat_name_table(tables_dir)
    ranges = affix_ranges(tables_dir)
    gun_data = table_rows(tables_dir, "GunData")
    weapon_configs = table_rows(tables_dir, "GunWeaponData")
    mod_configs = table_rows(tables_dir, "WeaponModData")

    characters = []
    for character in snap.assist_characters(stream_path.read_bytes()):
        role = character["role"]
        gun = gun_data.get(role["id"], [])
        name = None
        for n, w, v in gun:
            if n in (2, 3):
                name = localized(v, lang)
                if name:
                    break

        menus = snap.menu_instances(character["snapshot"])
        weapons = []
        for payload in menus["weapons"]:
            fields = wire.protobuf(payload)
            config_id = wire.scalar(fields, 2)
            config = weapon_configs.get(config_id, [])
            weapon_name = None
            for n, w, v in config:
                if n == 2:
                    weapon_name = localized(v, lang)
                    if weapon_name:
                        break
            weapons.append({
                "configId": config_id,
                "name": weapon_name,
                "level": wire.scalar(fields, 3),
            })

        characters.append({
            "roleId": role["id"],
            "name": name,
            "level": role["level"],
            "rarity": role["rarity"],
            "combatPower": role["combatPower"],
            "weapons": weapons,
        })

    return {"characters": characters}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server-stream", required=True)
    ap.add_argument("--tables", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    report = build_report(Path(args.server_stream), Path(args.tables))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}: {len(report['characters'])} characters")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
