"""Supplement unresolved local descriptions with attributable official Wiki text."""
from __future__ import annotations

import argparse
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import re
from html.parser import HTMLParser

import requests


class WikiHTML(HTMLParser):
    """Retain visible text and tooltip text without executing page HTML."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.tooltips = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"p", "div", "br", "tr", "td", "th", "li"}:
            self.parts.append("\n")
        tip = attrs.get("data-dec")
        if tip is not None:
            self.stack.append({"tag": tag, "depth": 0, "parts": [], "description": tip})
        else:
            for entry in self.stack:
                if tag not in {"br", "img", "hr", "input", "meta", "link"}:
                    entry["depth"] += 1

    def handle_endtag(self, tag):
        done = []
        for entry in self.stack:
            if entry["depth"] == 0 and tag == entry["tag"]:
                self.tooltips.append({"name": "".join(entry["parts"]).strip(), "description": entry["description"]})
                done.append(entry)
            else:
                entry["depth"] -= 1
        for entry in done:
            self.stack.remove(entry)
        if tag in {"p", "div", "tr", "td", "th", "li"}:
            self.parts.append("\n")

    def handle_data(self, text):
        self.parts.append(text)
        for entry in self.stack:
            entry["parts"].append(text)

    @property
    def text(self):
        return "\n".join(t for s in "".join(self.parts).splitlines() if (t := re.sub(r"\s+", " ", s).strip()))


def parse_html(value):
    parser = WikiHTML()
    parser.feed(value)
    return {"text": parser.text, "tooltips": parser.tooltips}


def sections(info):
    result = []
    for field, value in info.items():
        if isinstance(value, str) and "<" in value:
            result.append({"field": field, "name": field, **parse_html(value)})
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, dict) and isinstance(item.get("desc"), str):
                    result.append({"field": field, "index": index, "name": item.get("name", ""), **parse_html(item["desc"])})
    return result


def fetch_page(owner, expected, cache):
    target = cache / f"wiki_doll_{owner}.json"
    if target.exists():
        info = json.loads(target.read_text(encoding="utf-8"))
        mode = "cache"
    else:
        response = requests.post("https://gf2-bbs-api.exiliumgf.com/wiki/hero_detail", json={"id": owner},
                                 headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=25)
        response.raise_for_status()
        body = response.json()
        if str(body.get("Code")) != "0":
            raise ValueError(f"Wiki error: {body.get('Code')} {body.get('Message')}")
        info = (body.get("data") or {}).get("info")
        mode = "network"
    if not isinstance(info, dict) or str(info.get("hero_id")) != str(owner) or info.get("name") != expected:
        raise ValueError(f"Wiki ID/name mismatch for {owner}/{expected}")
    if mode == "network":
        target.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"id": owner, "name": expected, "sourceUrl": f"https://gf2-bbs.exiliumgf.com/wiki/doll?id={owner}",
            "cache": str(target.resolve()), "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "mode": mode, "sections": sections(info)}


def supplement(local, research, mappings):
    result = deepcopy(local)
    result["source"] = "Local game tables supplemented with matching-ID official Wiki names and tooltip definitions"
    result["localSummary"] = deepcopy(local["summary"])
    result["localWarnings"] = deepcopy(local["warnings"])
    result["wikiSources"] = {i: {k: p[k] for k in ["id", "name", "sourceUrl", "cache", "sha256"]}
                             for i, p in research["pages"].items()}
    result["wikiReferences"] = {}
    failures = list(research["failures"])
    for raw, rule in mappings.items():
        page = research["pages"].get(str(rule["ownerId"]))
        if not page:
            failures.append({"reference": raw, "error": "Matching Wiki page unavailable"})
            continue
        labels = {rule["name"], *rule.get("variants", [])}
        definitions = []
        for section in page["sections"]:
            for tip in section["tooltips"]:
                if tip["name"] in labels:
                    entry = {"name": tip["name"], "description": parse_html(tip["description"])["text"],
                             "wikiField": section["field"], "wikiSection": section["name"], "index": section.get("index")}
                    if entry not in definitions:
                        definitions.append(entry)
        if not definitions:
            failures.append({"reference": raw, "error": "Reviewed name has no tooltip definition on matching Wiki page"})
            continue
        result["wikiReferences"][raw] = {**rule, "reference": raw, "definitions": definitions,
                                         "sourceUrl": page["sourceUrl"], "sourceSha256": page["sha256"]}

    changes, remaining = [], []
    for group in ["skills", "buffs", "terms"]:
        for record in result[group].values():
            before = record["description"]
            previous_upgrade = record["upgradeDescription"]
            used = []
            for ref in record["references"]:
                if ref["status"] != "unresolved":
                    continue
                rule = result["wikiReferences"].get(ref["raw"])
                # Character-level ID association is mandatory, even if another
                # page happens to contain a similarly named effect.
                if rule is None or rule["ownerId"] != record["id"] // 10000:
                    continue
                label = rule.get("recordNames", {}).get(str(record["id"]), rule["name"])
                record.setdefault("localReferences", deepcopy(record["references"]))
                ref.update(name=label, status="wiki-name-resolved", sourceUrl=rule["sourceUrl"],
                           wikiReference=ref["raw"])
                marker = "{" + str(ref["index"]) + "}"
                record["description"] = record["description"].replace(marker, label)
                record["upgradeDescription"] = record["upgradeDescription"].replace(marker, label)
                used.append({"reference": ref["raw"], "name": label, "sourceUrl": rule["sourceUrl"]})
            if used:
                record["localDescription"] = before
                record["localUpgradeDescription"] = previous_upgrade
                record["wikiSupplements"] = used
                changes.append({"group": group, "id": record["id"], "name": record["name"], "supplements": used,
                                "descriptionWasUnresolved": bool(re.search(r"\{\d+\}", before))})
            record["unresolvedDescriptionPlaceholders"] = sorted(set(re.findall(r"\{\d+\}", record["description"])))
            record["unresolvedUpgradePlaceholders"] = sorted(set(re.findall(r"\{\d+\}", record["upgradeDescription"])))
            for ref in record["references"]:
                if ref["status"] == "unresolved":
                    marker = "{" + str(ref["index"]) + "}"
                    remaining.append({"group": group, "recordId": record["id"], "recordName": record["name"],
                                      "reference": ref["raw"], "visibleInDescription": marker in record["description"],
                                      "visibleInUpgrade": marker in record["upgradeDescription"]})

    # Read actual runtime rows to distinguish internal placeholders from a
    # missing player-facing skill. Never assign Wiki text to an invented ID.
    from local_catalog_probe import Catalog
    catalog = Catalog(local["tableDirectory"])
    runtime = catalog.rows("BattleSkillData")
    display_rows = catalog.rows("BattleSkillDisplayData")
    internal = []
    for warning in local["warnings"]:
        match = re.fullmatch(r"Missing BattleSkillDisplayData row (\d+)", warning)
        if not match:
            continue
        ident = int(match.group(1))
        fields = catalog.describe(runtime.get(ident, []))
        display_id = next((x["value"] for x in fields if x["field"] == 10 and "value" in x), None)
        display = catalog.describe(display_rows.get(display_id, []))
        display_name = next((x["text"] for x in display if x["field"] == 2 and "text" in x), "")
        placeholder = display_id == 10000 and "占位" in display_name
        internal.append({"id": ident, "ownerId": ident // 10000, "runtimeFields": fields,
                         "displayId": display_id, "displayName": display_name,
                         "status": "internal-placeholder-confirmed" if placeholder else "no-independent-description-found",
                         "wikiSourceUrl": f"https://gf2-bbs.exiliumgf.com/wiki/doll?id={ident // 10000}"})
    result["internalSkillReferences"] = internal
    result["supplementRuntimeSource"] = catalog.source("BattleSkillData")
    result["warnings"] = [f"No independent description for internal skill {x['id']}" for x in internal
                          if x["status"] == "no-independent-description-found"]
    result["summary"]["unresolvedSkillDescriptions"] = sum(bool(x["unresolvedDescriptionPlaceholders"]) for x in result["skills"].values())
    result["wikiSupplementSummary"] = {
        "pagesChecked": len(research["pages"]), "referenceNamesAdded": len(result["wikiReferences"]),
        "skillDescriptionsCompleted": sum(x["group"] == "skills" and x["descriptionWasUnresolved"] for x in changes),
        "buffDescriptionsCompleted": sum(x["group"] == "buffs" and x["descriptionWasUnresolved"] for x in changes),
        "recordsSupplemented": len(changes), "remainingSkillDescriptions": result["summary"]["unresolvedSkillDescriptions"],
        "remainingBuffDescriptions": sum(bool(x["unresolvedDescriptionPlaceholders"]) for x in result["buffs"].values()),
        "remainingUpgradeDescriptions": sum(bool(x["unresolvedUpgradePlaceholders"]) for group in ["skills", "buffs", "terms"] for x in result[group].values()),
        "internalPlaceholdersConfirmed": sum(x["status"] == "internal-placeholder-confirmed" for x in internal),
        "internalSkillsWithoutIndependentDescription": sum(x["status"] == "no-independent-description-found" for x in internal),
        "unusedUnresolvedReferences": sum(not x["visibleInDescription"] and not x["visibleInUpgrade"] for x in remaining),
        "failures": len(failures)}
    report = {"summary": result["wikiSupplementSummary"], "changes": changes, "remainingReferences": remaining,
              "internalSkillReferences": internal, "failures": failures,
              "reviewNotes": [v["note"] for v in mappings.values() if "note" in v]}
    return result, report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--local", type=Path, required=True)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--overrides", type=Path, default=Path(__file__).with_name("wiki_reference_overrides.json"))
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    local = json.loads(args.local.read_text(encoding="utf-8"))
    names = {x["id"]: x["name"] for x in local["characters"]}
    owners = {s["id"] // 10000 for field in ["skills", "buffs"] for s in local[field].values()
              if any(r["status"] == "unresolved" for r in s["references"])}
    owners.update(int(m.group(1)) // 10000 for w in local["warnings"] if (m := re.search(r"row (\d+)", w)))
    args.cache.mkdir(parents=True, exist_ok=True)
    pages, failures = {}, []
    with ThreadPoolExecutor(max_workers=3) as executor:
        jobs = {executor.submit(fetch_page, i, names[i], args.cache): i for i in sorted(owners) if i in names}
        for future in as_completed(jobs):
            owner = jobs[future]
            try:
                page = future.result()
                pages[str(owner)] = page
                print(json.dumps({"id": owner, "name": names[owner], "mode": page["mode"],
                                  "sections": len(page["sections"]), "tooltips": sum(len(s["tooltips"]) for s in page["sections"])}, ensure_ascii=False), flush=True)
            except Exception as exc:
                failures.append({"id": owner, "name": names[owner], "error": str(exc)})
                print(json.dumps(failures[-1], ensure_ascii=False), flush=True)
    result = {"checkedAt": datetime.now(timezone.utc).isoformat(), "pages": pages, "failures": failures}
    output = args.cache / "wiki_missing_research.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output.resolve()), "pages": len(pages), "failures": failures}, ensure_ascii=False))
    mappings = json.loads(args.overrides.read_text(encoding="utf-8"))["references"]
    augmented, report = supplement(local, result, mappings)
    augmented["localCatalogSource"] = {"path": str(args.local.resolve()), "sha256": hashlib.sha256(args.local.read_bytes()).hexdigest()}
    augmented["reviewedMappingSource"] = {"path": str(args.overrides.resolve()), "sha256": hashlib.sha256(args.overrides.read_bytes()).hexdigest()}
    augmented_path = args.output or args.cache / "catalog_details_with_wiki.json"
    if augmented_path.resolve() == args.local.resolve():
        raise ValueError("Output must differ from local-only input to preserve source data")
    augmented_path.parent.mkdir(parents=True, exist_ok=True)
    augmented_path.write_text(json.dumps(augmented, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path = args.cache / "wiki_supplement_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"augmented": str(augmented_path.resolve()), "report": str(report_path.resolve()), "summary": report["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
