"""Read-only local table research; numeric links remain candidates until verified.

No network or process access. Reuses the repository's wire/table reader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import assist_report as tables

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.ssr_parser import get_table_dir


def packed(data: bytes) -> list[int]:
    result, pos = [], 0
    while pos < len(data):
        value, pos = tables.wire.read_varint(data, pos)
        result.append(value)
    return result


class Catalog:
    def __init__(self, directory: str | None = None):
        located = directory or get_table_dir()
        if not located:
            raise ValueError("Cannot locate local Table directory")
        self.directory = Path(located)
        self.lang = tables.language_map(self.directory)
        self.cache = {}

    def rows(self, name: str):
        if name not in self.cache:
            self.cache[name] = tables.table_rows(self.directory, name)
        return self.cache[name]

    def describe(self, row):
        result = []
        for n, w, v in row:
            item = {"field": n, "wire": w}
            if not isinstance(v, bytes):
                item["value"] = v
            else:
                try:
                    sub = tables.wire.protobuf(v)
                except tables.wire.WireError:
                    sub = []
                if len(sub) == 1 and sub[0][:2] == (1, 0) and sub[0][2] in self.lang:
                    item.update(languageId=sub[0][2], text=self.lang[sub[0][2]])
                else:
                    try:
                        text = v.decode("utf-8")
                    except UnicodeDecodeError:
                        text = None
                    if text is not None and all(c.isprintable() or c in "\r\n\t" for c in text):
                        item["text"] = text
                    else:
                        item["hex"] = v.hex()
                        try:
                            item["packedVarintCandidates"] = packed(v)
                        except tables.wire.WireError:
                            pass
            result.append(item)
        return result

    def source(self, name):
        path = self.directory / (name + ".bytes")
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tables")
    sub = ap.add_subparsers(dest="command", required=True)
    row = sub.add_parser("row")
    row.add_argument("table")
    row.add_argument("ids", nargs="+", type=int)
    search = sub.add_parser("text")
    search.add_argument("needles", nargs="+")
    search.add_argument("--in-tables", nargs="+", required=True)
    refs = sub.add_parser("refs")
    refs.add_argument("ids", nargs="+", type=int)
    refs.add_argument("--in-tables", nargs="+", required=True)
    args = ap.parse_args()
    c = Catalog(args.tables)
    if args.command == "row":
        for ident in args.ids:
            print(json.dumps({"table": args.table, "id": ident, "fields": c.describe(c.rows(args.table).get(ident, []))}, ensure_ascii=False))
    elif args.command == "text":
        for name in args.in_tables:
            for ident, fields in c.rows(name).items():
                described = c.describe(fields)
                matches = [x for x in described if any(n in x.get("text", "") for n in args.needles)]
                if matches:
                    print(json.dumps({"table": name, "id": ident, "matches": matches}, ensure_ascii=False))
    else:
        targets = set(args.ids)
        for name in args.in_tables:
            for ident, fields in c.rows(name).items():
                matches = []
                for n, w, v in fields:
                    if w == 0 and v in targets:
                        matches.append({"field": n, "value": v, "kind": "scalar"})
                    elif w == 2:
                        try:
                            found = targets.intersection(packed(v))
                        except tables.wire.WireError:
                            continue
                        if found:
                            matches.append({"field": n, "values": sorted(found), "kind": "packed-candidate"})
                if matches:
                    print(json.dumps({"table": name, "id": ident, "matches": matches}, ensure_ascii=False))


if __name__ == "__main__":
    main()
