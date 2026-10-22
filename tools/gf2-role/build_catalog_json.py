"""Build the ID-indexed encyclopedia JSON from existing lists and local tables.

No network access. Run from any directory:
    python tools/gf2-role/build_catalog_json.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from export_local_catalog import Exporter, ROOT


COLLECTIONS = {"BattleSkillDisplayData": "skills", "BattleBuffPerformData": "buffs", "BattleDictionaryData": "terms"}
PERCENT_STATS = {"crit": "暴击率", "critMult": "暴击伤害", "powPercent": "攻击加成",
                 "maxHpPercent": "生命加成", "shieldArmorPercent": "防御加成"}


def sid(value):
    return str(value) if value is not None else None


def load_lists():
    characters, weapons, groups, sources = {}, {}, {}, {}
    for filename in ["ssr.json", "non_ssr.json"]:
        path = ROOT / "json" / filename
        document = json.loads(path.read_text(encoding="utf-8"))
        sources[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        for group, items in document.items():
            if not isinstance(items, dict):
                continue
            groups[group] = items
            destination = characters if group.endswith("_character") else weapons if group.endswith("_weapon") else None
            if destination is None:
                continue
            for ident, name in items.items():
                if ident in destination and destination[ident] != name:
                    raise ValueError(f"Conflicting names for {ident}")
                destination[ident] = name
    if set(characters).intersection(weapons):
        raise ValueError("Character and weapon IDs overlap")
    for group, items in groups.items():
        for ident, name in items.items():
            if characters.get(ident, weapons.get(ident)) != name:
                raise ValueError(f"Unmatched existing list entry: {group}.{ident}={name}")
    return {"SSR_character": characters, "SSR_weapon": weapons}, groups, sources


def is_visible_skill(ident, raw):
    # Display ID 10000 explicitly denotes an internal placeholder.
    return ident is not None and ident != 10000 and str(ident) in raw["skills"]


def public_display(record, raw_upgrade):
    markers = set(re.findall(r"\{(\d+)\}", record["descriptionTemplate"] + raw_upgrade))
    refs = []
    for ref in record["references"]:
        if str(ref["index"]) not in markers:
            continue
        if ref["status"] != "name-resolved":
            raise ValueError(f"Unresolved displayed reference: {record['id']}: {ref['raw']}")
        refs.append({"index": ref["index"], "collection": COLLECTIONS[ref["table"]], "id": sid(ref["id"]), "name": ref["name"],
                     "variants": [{"gradeId": sid(v["gradeId"]), "collection": COLLECTIONS[v["table"]],
                                   "id": sid(v["id"]), "name": v["name"]} for v in ref["variants"]]})
    grade_descriptions = [{"gradeId": sid(g["gradeId"]), "description": g["description"],
                           "upgradeDescription": g["upgradeDescription"]} for g in record["gradeDescriptions"]]
    return {"id": sid(record["id"]), "name": record["name"], "level": record["level"],
            "typeLabel": record["typeLabel"], "description": record["description"],
            "upgradeDescription": record["upgradeDescription"], "references": refs, "gradeDescriptions": grade_descriptions}


def talent_bonuses(prop):
    if prop is None:
        return []
    if prop.get("missing"):
        raise ValueError(f"Missing talent property {prop['id']}")
    # These five fields are percentage-point bonuses stored in thousandths;
    # converting the labels does not calculate any leveled/account panel.
    unknown = set(prop["rawValues"]) - PERCENT_STATS.keys()
    if unknown:
        raise ValueError(f"Unsupported talent bonus fields: {sorted(unknown)}")
    return [{"stat": key, "label": PERCENT_STATS[key], "value": value / 10, "unit": "%"}
            for key, value in prop["rawValues"].items() if value]


def build(directory=None):
    lists, groups, sources = load_lists()
    exporter = Exporter(directory)
    raw = exporter.export(lists)
    result = {"schemaVersion": 1, "source": "local-game-tables", "items": {}, "skills": {}, "buffs": {}, "terms": {}}
    for collection in ["skills", "buffs", "terms"]:
        for ident, record in raw[collection].items():
            if collection == "skills" and not is_visible_skill(record["id"], raw):
                continue
            row = exporter.c.rows(record["table"])[record["id"]]
            upgrade = exporter.text(row, 8) if collection == "skills" else ""
            result[collection][ident] = public_display(record, upgrade)

    for character in raw["characters"]:
        grades = [{"id": sid(g["id"]), "rank": rank, "label": g["label"],
                   "skillIds": [sid(i) for i in g["skillIds"] if is_visible_skill(i, raw)],
                   "specialSkillIds": [sid(i) for i in g["specialSkillIds"] if is_visible_skill(i, raw)]}
                  for rank, g in enumerate(character["grades"])]
        talents = []
        for talent in character["talents"]:
            skill_id = sid(talent["skillId"]) if is_visible_skill(talent["skillId"], raw) else None
            bonuses = talent_bonuses(talent["property"])
            description = result["skills"][skill_id]["description"] if skill_id else ""
            bonus_text = "；".join(f"{b['label']}+{b['value']:g}%" for b in bonuses)
            talents.append({"id": sid(talent["id"]), "name": talent["name"], "category": talent["category"],
                            "description": "\n".join(x for x in [description, bonus_text] if x),
                            "skillId": skill_id, "bonuses": bonuses})
        normal = sid(character["normalAttackSkillId"])
        archive = character["archive"]
        ident = sid(character["id"])
        result["items"][ident] = {"id": ident, "type": "character", "name": character["name"], "rarity": character["rarity"],
                                   "description": character["description"], "quote": character["quote"], "weaponQuote": character["weaponQuote"],
                                   "duty": character["duty"], "weaponType": character["weaponType"],
                                   "model": archive["model"], "weaponName": archive["weaponName"], "organization": archive["organization"],
                                   "voiceActors": {"zh": archive["chineseVoiceActor"], "ja": archive["japaneseVoiceActor"]},
                                   "normalAttackSkillId": normal, "grades": grades, "talents": talents}
    for weapon in raw["weapons"]:
        ident = sid(weapon["id"])
        trait = sid(weapon["traitSkillId"]) if is_visible_skill(weapon["traitSkillId"], raw) else None
        imprint = sid(weapon["imprintSkillId"]) if is_visible_skill(weapon["imprintSkillId"], raw) else None
        levels = [{"level": x["level"], "skillId": sid(x["skillId"])} for x in weapon["skillLevels"] if is_visible_skill(x["skillId"], raw)]
        result["items"][ident] = {"id": ident, "type": "weapon", "name": weapon["name"], "rarity": weapon["rarity"],
                                   "description": weapon["description"], "weaponType": weapon["weaponType"], "iconResource": weapon["iconResource"],
                                   "skillLevels": levels, "traitSkillId": trait,
                                   "traitDescription": result["skills"][trait]["description"] if trait else "",
                                   "imprintSkillId": imprint, "imprintDescription": result["skills"][imprint]["description"] if imprint else ""}
    for collection in ["items", "skills", "buffs", "terms"]:
        result[collection] = dict(sorted(result[collection].items(), key=lambda pair: int(pair[0])))
    for group, entries in groups.items():
        for ident, expected_name in entries.items():
            item = result["items"].get(ident)
            if item is None or item["name"] != expected_name:
                raise ValueError(f"Catalog does not match {group}.{ident}")
    for collection in ["skills", "buffs", "terms"]:
        for record in result[collection].values():
            for ref in record["references"]:
                for target in [ref, *ref["variants"]]:
                    if target["id"] not in result[target["collection"]]:
                        raise ValueError(f"Broken public reference: {collection}.{record['id']} -> {target['id']}")
    report = {"inputLists": sources, "localSources": raw["sources"],
              "listCoverage": {group: len(items) for group, items in groups.items()},
              "counts": {collection: len(result[collection]) for collection in ["items", "skills", "buffs", "terms"]},
              "characters": len(raw["characters"]), "weapons": len(raw["weapons"]),
              "researchWarnings": raw["warnings"], "internalSkills": raw["internalSkills"]}
    return result, report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tables")
    ap.add_argument("--output", type=Path, default=ROOT / "json" / "catalog.json")
    ap.add_argument("--report", type=Path, default=ROOT / "logs" / "catalog_probe_20261018" / "catalog_build_report.json")
    args = ap.parse_args()
    result, report = build(args.tables)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "characters": report["characters"], "weapons": report["weapons"],
                      "counts": report["counts"], "bytes": args.output.stat().st_size,
                      "report": str(args.report.resolve()), "researchWarnings": report["researchWarnings"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
