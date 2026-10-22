"""Scan an assist snapshot for known panel values across plausible encodings.

Values come from the UID 4382210 screenshot sample (attack, defense, crit,
crit damage). A hit is an encoding candidate, not proof of semantics.
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


def encodings(value: float) -> dict[str, bytes]:
    out = {
        "int": None,
        "half": struct.pack("<e", value),
        "float": struct.pack("<f", value),
        "double": struct.pack("<d", value),
    }
    if value == int(value):
        out["int"] = int(value).to_bytes(8, "little")
        out["varint"] = encode_varint(int(value))
    return {k: v for k, v in out.items() if v}


def encode_varint(n: int) -> bytes:
    out = bytearray()
    while n > 127:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


def scan_record(root_fields, needles: dict[str, dict[str, bytes]], max_depth=12):
    """Walk every nested message and test each raw payload against needles."""
    hits = []
    stack = [("", root_fields, 0)]
    while stack:
        path, fields, depth = stack.pop()
        if depth > max_depth:
            continue
        for n, w, v in fields:
            if not isinstance(v, bytes):
                continue
            here = f"{path}.{n}" if path else str(n)
            for label, by_enc in needles.items():
                for enc, pattern in by_enc.items():
                    if pattern in v:
                        hits.append({"label": label, "encoding": enc, "path": here})
            try:
                sub = wire.protobuf(v)
            except wire.WireError:
                continue
            if sub:
                stack.append((here, sub, depth + 1))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server-stream", required=True)
    ap.add_argument("--sample", default=str(Path(__file__).with_name("panel_sample.json")))
    ap.add_argument("--out")
    args = ap.parse_args()

    sample = json.loads(Path(args.sample).read_text(encoding="utf-8"))
    stream = Path(args.server_stream).read_bytes()
    characters = snap.assist_characters(stream)
    report = []
    for character in characters:
        combat = character["role"]["combatPower"]
        label = str(combat)
        entry = dict(sample["characters"][label]) if label in sample["characters"] else None
        needles = {}
        if entry:
            for key, value in entry.items():
                for scale in sample["scales"]:
                    needles[f"{key}"] = {f"{name}@{scale}": pat
                        for name, pat in encodings(value * scale).items()}
        report.append({
            "combatPower": combat,
            "roleId": character["role"]["id"],
            "hasReference": entry is not None,
            "hits": scan_record(character["snapshot"], needles) if needles else [],
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
