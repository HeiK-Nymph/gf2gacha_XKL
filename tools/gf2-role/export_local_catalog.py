"""Export SSR details from installed game tables, without network/process access.

Usage: python tools/gf2-role/export_local_catalog.py --output <catalog.json>
Field links are documented in LOCAL_CATALOG_FINDINGS.md. This is a research
export, not a calculator for leveled/account-specific combat panels.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from collections import defaultdict, deque
from pathlib import Path

from local_catalog_probe import Catalog, ROOT, packed


def scalar(row, field):
    return next((v for n, w, v in row if n == field and w == 0), None)


def numbers(row, field):
    result = []
    for n, w, v in row:
        if n != field:
            continue
        if w == 0:
            result.append(v)
        elif w == 2:
            result.extend(packed(v))
    return result


def plain(text):
    return html.unescape(re.sub(r"</?color(?:=[^>]+)?>|</?[bi]>", "", text or ""))


class Exporter:
    def __init__(self, directory=None):
        self.c = Catalog(directory)
        self.displays = self.c.rows("BattleSkillDisplayData")
        self.buffs = self.c.rows("BattleBuffPerformData")
        self.dictionary = self.c.rows("BattleDictionaryData")
        self.buff_configs = self.c.rows("BattleBuffData")
        self.runtime_skills = self.c.rows("BattleSkillData")
        self.share_groups = self.c.rows("BuffShareLimitByGroupData")
        self.share_limits = self.c.rows("BuffShareLimitData")
        self.skill_ids, self.buff_ids = set(), set()
        self.links = defaultdict(list)
        self.warnings = []
        for ident, row in self.c.rows("GunGradeData").items():
            self.links[("grades", scalar(row, 2))].append((ident, row))
        for ident, row in self.c.rows("TalentKeyData").items():
            for owner in {scalar(row, 9), scalar(row, 15)} - {None}:
                self.links[("talents", owner)].append((ident, row))
        for ident, row in self.c.rows("WeaponBreakData").items():
            self.links[("weaponLevels", scalar(row, 2))].append((ident, row))
        for ident, row in self.c.rows("GunClassData").items():
            self.links[("upgradeStages", scalar(row, 2))].append((ident, row))

    def text(self, row, field):
        return next((f["text"] for f in self.c.describe(row) if f["field"] == field and "text" in f), "")

    def prop(self, ident):
        if ident is None:
            return None
        row = self.c.rows("PropertyData").get(ident)
        if row is None:
            self.warnings.append(f"Missing PropertyData row {ident}")
            return {"id": ident, "missing": True}
        # Names confirmed by current DLL's PropertyData FieldNumber constants.
        names = {2: "pow", 3: "maxHp", 5: "shieldArmor", 7: "maxAp", 8: "maxWillValue",
                 9: "crit", 10: "critMult", 29: "powPercent", 30: "maxHpPercent", 32: "shieldArmorPercent"}
        return {"id": ident, "table": "PropertyData", "rawValues": {names[n]: v for n, w, v in row if w == 0 and n in names},
                "rawFields": {str(n): v for n, w, v in row if w == 0 and n != 1},
                "interpretation": "Raw configuration; level/scaling/rounding and final panel calculation are not established."}

    def add_skill(self, ident):
        if ident is not None:
            self.skill_ids.add(ident)
        return ident

    def character(self, ident, expected):
        row = self.c.rows("GunData").get(ident, [])
        name = self.text(row, 2)
        if not row or name != expected:
            raise ValueError(f"Character name/ID mismatch: {ident}: {expected!r} / {name!r}")
        archive_id = scalar(row, 11)
        archive = self.c.rows("GunCharacterData").get(archive_id, [])
        if archive and scalar(archive, 9) != ident:
            self.warnings.append(f"Archive {archive_id} does not point back to character {ident}; omitted")
            archive = []
        attack = self.add_skill(scalar(row, 18))
        grades = []
        for grade_id, grade in sorted(self.links[("grades", ident)]):
            skills = numbers(grade, 4)
            special = numbers(grade, 14)
            for skill in skills + special:
                self.add_skill(skill)
            grades.append({"id": grade_id, "label": self.text(grade, 3), "skillIds": skills, "specialSkillIds": special})
        talents = []
        for talent_id, talent in sorted(self.links[("talents", ident)]):
            skill = self.add_skill(scalar(talent, 6))
            talents.append({"id": talent_id, "name": self.text(talent, 7), "category": self.text(talent, 4),
                            "skillId": skill, "property": self.prop(scalar(talent, 5))})
        stages = [{"id": stage_id, "stage": scalar(stage, 3), "label": self.text(stage, 4),
                   "levelLimit": scalar(stage, 6), "property": self.prop(scalar(stage, 8))}
                  for stage_id, stage in sorted(self.links[("upgradeStages", scalar(row, 29))])]
        return {"id": ident, "name": name, "rarity": scalar(row, 15), "description": self.text(row, 6), "quote": self.text(row, 7),
                "weaponQuote": self.text(row, 67), "duty": self.text(self.c.rows("GunDutyData").get(scalar(row, 13), []), 2),
                "weaponType": self.text(self.c.rows("GunWeaponTypeData").get(scalar(row, 23), []), 2),
                "archive": {"id": archive_id, "chineseVoiceActor": self.text(archive, 12), "japaneseVoiceActor": self.text(archive, 13),
                            "model": self.text(archive, 16), "weaponName": self.text(archive, 18), "organization": self.text(archive, 19)},
                "basePropertyConfig": self.prop(scalar(row, 40)), "normalAttackSkillId": attack,
                "grades": grades, "talents": talents, "upgradeStages": stages}

    def weapon(self, ident, expected):
        row = self.c.rows("GunWeaponData").get(ident, [])
        name = self.text(row, 2)
        if not row or name != expected:
            raise ValueError(f"Weapon name/ID mismatch: {ident}: {expected!r} / {name!r}")
        battle = self.c.rows("BattleWeaponData").get(ident, [])
        levels = []
        for break_id, level in sorted(self.links[("weaponLevels", ident)]):
            skill = scalar(level, 4)
            if not scalar(level, 3) or skill not in self.displays:
                continue  # A level-zero placeholder is not an actual weapon skill.
            levels.append({"id": break_id, "level": scalar(level, 3), "skillId": self.add_skill(skill)})
        return {"id": ident, "name": name, "rarity": scalar(row, 11), "description": self.text(row, 3),
                "weaponType": self.text(self.c.rows("GunWeaponTypeData").get(scalar(row, 4), []), 2),
                "iconResource": self.text(row, 8), "modelResource": self.text(row, 9),
                "basePropertyConfig": self.prop(scalar(row, 21)), "skillLevels": levels,
                "traitSkillId": self.add_skill(scalar(battle, 4)), "imprintSkillId": self.add_skill(scalar(battle, 5))}

    def buff_target(self, target):
        """Resolve a concrete Buff id to its local display row, retaining links."""
        path = [{"table": "BattleBuffPerformData", "id": target}]
        if target not in self.buffs:
            display_id = scalar(self.buff_configs.get(target, []), 3)
            if display_id in self.buffs:
                path.append({"table": "BattleBuffData", "id": target, "field": 3})
                target = display_id
        return target, self.text(self.buffs.get(target, []), 2), path

    def share_variants(self, group_id, slot):
        """Resolve group/slot through local grade-specific BuffShareLimit rows.

        Slot is one-based in the semicolon list; it is not the Buff level.
        Preserve every grade variant rather than choosing an upgraded effect
        from Wiki or treating the group id as a concrete Buff id.
        """
        variants = []
        row_ids = numbers(self.share_groups.get(group_id, []), 2)
        for row_id in row_ids:
            row = self.share_limits.get(row_id, [])
            grades_text, sets_text = self.text(row, 4), self.text(row, 5)
            grades = grades_text.split(",") if grades_text else [None]
            sets = sets_text.split(",")
            if len(grades) != len(sets):
                self.warnings.append(f"BuffShareLimitData {row_id}: grade/set count mismatch")
                continue
            for grade, buff_set in zip(grades, sets):
                choices = buff_set.split(";")
                if not 1 <= slot <= len(choices):
                    self.warnings.append(f"BuffShareLimitData {row_id}: slot {slot} missing at grade {grade}")
                    continue
                selected = choices[slot - 1]
                match = re.fullmatch(r"(\d+)(?:-(-?\d+))?", selected)
                if not match:
                    self.warnings.append(f"BuffShareLimitData {row_id}: unsupported Buff expression {selected!r}")
                    continue
                buff_id = int(match.group(1))
                target, label, display_path = self.buff_target(buff_id)
                variants.append({"gradeId": int(grade) if grade is not None else None, "buffId": buff_id,
                                 "suffixArgument": int(match.group(2)) if match.group(2) is not None else None,
                                 "id": target, "table": "BattleBuffPerformData", "name": label,
                                 "status": "name-resolved" if label else "unresolved",
                                 "resolutionPath": [{"table": "BuffShareLimitByGroupData", "id": group_id, "field": 2},
                                                    {"table": "BuffShareLimitData", "id": row_id, "gradeId": int(grade) if grade else None,
                                                     "field": 5, "slot": slot, "selected": selected}, *display_path]})
        return variants

    def references(self, row):
        result = []
        for index, token in enumerate(self.text(row, 4).split(";")):
            if not token:
                continue
            kind, sep, value = token.partition(":")
            target, target_table = None, None
            resolution_path = []
            variants = []
            if sep and kind == "1" and value.isdecimal():
                target, target_table = int(value), "BattleDictionaryData"
            elif sep and kind == "0":
                parts = value.split(",")
                if len(parts) == 3 and parts[0] == "-1" and all(x.isdecimal() for x in parts[1:]):
                    variants = self.share_variants(int(parts[1]), int(parts[2]))
                    if variants:
                        # The top-level text uses the first available local
                        # grade; all other versions are exported explicitly.
                        first = variants[0]
                        target, target_table = first["id"], first["table"]
                        resolution_path = first["resolutionPath"]
                elif len(parts) in [1, 2] and parts[0].isdecimal() and (len(parts) == 1 or parts[1].isdecimal()):
                    target, _, resolution_path = self.buff_target(int(parts[0]))
                    target_table = "BattleBuffPerformData"
            rows = self.dictionary if target_table == "BattleDictionaryData" else self.buffs
            label = self.text(rows.get(target, []), 2) if target is not None else ""
            result.append({"index": index, "raw": token, "table": target_table, "id": target, "name": label,
                           "resolutionPath": resolution_path, "variants": variants,
                           "status": "name-resolved" if label else "unresolved"})
        return result

    def display(self, ident, row, table):
        refs = self.references(row)
        def resolve(field):
            text = self.text(row, field)
            for ref in refs:
                if ref["name"]:
                    text = text.replace("{" + str(ref["index"]) + "}", ref["name"])
            return plain(text)
        grade_ids = sorted({v["gradeId"] for ref in refs for v in ref["variants"] if v["gradeId"] is not None})
        grade_descriptions = []
        for grade_id in grade_ids:
            texts = {"description": self.text(row, 3), "upgradeDescription": self.text(row, 8) if table == "BattleSkillDisplayData" else ""}
            targets = []
            for ref in refs:
                variant = next((v for v in ref["variants"] if v["gradeId"] == grade_id), None)
                label = variant["name"] if variant else ref["name"]
                if label:
                    for key in texts:
                        texts[key] = texts[key].replace("{" + str(ref["index"]) + "}", label)
                if variant:
                    targets.append({"index": ref["index"], "table": variant["table"], "id": variant["id"], "name": label})
            grade_descriptions.append({"gradeId": grade_id, **{key: plain(value) for key, value in texts.items()}, "referenceTargets": targets})
        return {"id": ident, "table": table, "name": self.text(row, 2), "level": scalar(row, 9) if table == "BattleSkillDisplayData" else None,
                "descriptionTemplate": self.text(row, 3), "description": resolve(3), "references": refs,
                "unresolvedDescriptionPlaceholders": sorted(set(re.findall(r"\{\d+\}", resolve(3)))),
                "gradeDescriptions": grade_descriptions,
                "descriptionContext": "First available local grade for dynamic references; choose gradeDescriptions/reference variants for a specific grade.",
                "typeLabel": self.text(row, 22) if table == "BattleSkillDisplayData" else "",
                "upgradeDescription": resolve(8) if table == "BattleSkillDisplayData" else ""}

    def export(self, catalog):
        chars = [self.character(int(i), n) for i, n in catalog["SSR_character"].items()]
        weapons = [self.weapon(int(i), n) for i, n in catalog["SSR_weapon"].items()]
        skills, buffs, terms, internal = {}, {}, {}, {}
        pending = deque(("BattleSkillDisplayData", i) for i in sorted(self.skill_ids))
        seen = set()
        while pending:
            table, ident = pending.popleft()
            if (table, ident) in seen:
                continue
            seen.add((table, ident))
            source = {"BattleSkillDisplayData": self.displays, "BattleBuffPerformData": self.buffs, "BattleDictionaryData": self.dictionary}[table]
            row = source.get(ident)
            if row is None:
                if table == "BattleSkillDisplayData" and ident in self.runtime_skills:
                    runtime_row = self.runtime_skills[ident]
                    display_id = scalar(runtime_row, 10)
                    display_name = self.text(self.displays.get(display_id, []), 2)
                    placeholder = display_id == 10000 and bool(display_name)
                    internal[str(ident)] = {"id": ident, "table": "BattleSkillData", "displayId": display_id,
                                            "displayName": display_name, "runtimeFields": self.c.describe(runtime_row),
                                            "status": "internal-placeholder" if placeholder else "no-display-row"}
                    if placeholder:
                        continue
                self.warnings.append(f"Missing {table} row {ident}")
                continue
            record = self.display(ident, row, table)
            destination = {"BattleSkillDisplayData": skills, "BattleBuffPerformData": buffs, "BattleDictionaryData": terms}[table]
            destination[str(ident)] = record
            if table == "BattleDictionaryData" and ident in self.displays:
                pending.append(("BattleSkillDisplayData", ident))
            for ref in record["references"]:
                if ref["status"] == "name-resolved":
                    pending.append((ref["table"], ref["id"]))
                for variant in ref["variants"]:
                    if variant["status"] == "name-resolved":
                        pending.append((variant["table"], variant["id"]))
        summary = {"characters": len(chars), "weapons": len(weapons), "skills": len(skills), "buffs": len(buffs), "terms": len(terms),
                   "charactersWithArchive": sum(bool(x["archive"]["model"]) for x in chars),
                   "charactersWithTalents": sum(bool(x["talents"]) for x in chars),
                   "weaponsWithSkills": sum(bool(x["skillLevels"]) for x in weapons),
                   "unresolvedSkillDescriptions": sum(bool(x["unresolvedDescriptionPlaceholders"]) for x in skills.values()),
                   "unresolvedBuffDescriptions": sum(bool(x["unresolvedDescriptionPlaceholders"]) for x in buffs.values()),
                   "unresolvedTermDescriptions": sum(bool(x["unresolvedDescriptionPlaceholders"]) for x in terms.values()),
                   "internalPlaceholderSkills": sum(x["status"] == "internal-placeholder" for x in internal.values()),
                   "internalSkillsWithoutDisplay": sum(x["status"] == "no-display-row" for x in internal.values()),
                   "dynamicReferenceExpressions": len({r["raw"] for rows in [skills, buffs, terms] for x in rows.values() for r in x["references"] if r["variants"]}),
                   "unresolvedDynamicVariants": sum(v["status"] == "unresolved" for rows in [skills, buffs, terms] for x in rows.values() for r in x["references"] for v in r["variants"])}
        growth = [{"level": level, "property": self.prop(scalar(row, 4))}
                  for level, row in sorted(self.c.rows("GunLevelExpData").items())]
        names = sorted(set(self.c.cache) | {"LangPackageTableCnData"})
        return {"source": "Installed local game tables only; no Wiki/API data", "tableDirectory": str(self.c.directory),
                "limitations": ["Raw properties are not final leveled/account-specific attributes.",
                                "Placeholder substitutions are observed name links, not execution of the client formatter.",
                                "Dynamic references carry all available local grade variants; a grade context is needed to choose their exact effect.",
                                "Local version text can differ from Wiki; original templates are preserved."],
                "sources": {name: self.c.source(name) for name in names}, "summary": summary,
                "warnings": sorted(set(self.warnings)), "characters": chars, "weapons": weapons, "skills": skills, "buffs": buffs,
                "terms": terms, "characterLevelGrowthConfigs": growth, "internalSkills": internal}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tables")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    catalog = json.loads((ROOT / "json/ssr.json").read_text(encoding="utf-8"))
    result = Exporter(args.tables).export(catalog)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "summary": result["summary"], "warnings": result["warnings"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
