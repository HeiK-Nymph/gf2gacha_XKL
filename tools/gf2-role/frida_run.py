"""Attach Frida to a process and run a panel-hunt phase.

Loads frida_panel_hunt.js with caller-supplied globals, prints the message
stream, and detaches. Read-only: the script scans memory and reports hits.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

import frida

SCRIPT = Path(__file__).with_name("frida_panel_hunt.js")
NEIGHBORHOOD = Path(__file__).with_name("frida_neighborhood.js")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int)
    ap.add_argument("--name", help="process name to attach to when --pid is absent")
    ap.add_argument("--phase", default="recon", choices=["recon", "scan"])
    ap.add_argument("--neighborhood", action="store_true",
                    help="anchor-and-siblings mode: --values[0] is the anchor")
    ap.add_argument("--window", type=int, default=512)
    ap.add_argument("--values", nargs="*", default=[])
    ap.add_argument("--labels", nargs="*", default=[])
    ap.add_argument("--encodings", nargs="*", default=["float32", "int32"],
                    help="encodings to try per value; scales apply to integer encodings")
    ap.add_argument("--scales", nargs="*", type=int, default=[1, 10, 100])
    ap.add_argument("--wait", type=float, default=0, help="seconds to wait before detaching")
    ap.add_argument("--out")
    args = ap.parse_args()

    if args.pid:
        session = frida.attach(args.pid)
    elif args.name:
        session = frida.attach(args.name)
    else:
        print("need --pid or --name", file=sys.stderr)
        return 2

    messages = []
    done = threading.Event()

    def on_message(message, data):
        messages.append(message)
        payload = message.get("payload") if isinstance(message, dict) else None
        if isinstance(payload, dict) and payload.get("kind") in ("done", "error"):
            done.set()

    values = [float(v) if "." in v else int(v) for v in args.values]
    labels = [s for s in args.labels if s]
    if args.neighborhood:
        anchor = values[0]
        anchor_kind = args.encodings[0] if args.encodings else "float32"
        siblings = [
            {"value": v, "kinds": args.encodings or ["float32", "int32"]}
            for v in values[1:]
        ]
        prelude = (
            "(function (ANCHOR, ANCHOR_KIND, SIBLINGS, WINDOW) {\n"
            f"const __anchor = {json.dumps(anchor)};\n"
            f"const __anchorKind = {json.dumps(anchor_kind)};\n"
            f"const __siblings = {json.dumps(siblings)};\n"
            f"const __window = {json.dumps(args.window)};\n"
        )
        body = NEIGHBORHOOD.read_text(encoding="utf-8")
        # The file's own setTimeout call runs after loading; rebind its
        # identifiers to the wrapped constants.
        invoke = (
            "})("
            f"{json.dumps(anchor)}, {json.dumps(anchor_kind)}, "
            f"{json.dumps(siblings)}, {json.dumps(args.window)});"
        )
    else:
        specs = []
        for value in values:
            for kind in args.encodings:
                if kind.startswith("float"):
                    specs.append({"value": value, "raw": value, "kind": kind})
                else:
                    for scale in args.scales:
                        scaled = value * scale
                        if float(scaled).is_integer() and abs(scaled) < 2 ** 31:
                            specs.append({"value": value, "raw": int(scaled), "kind": kind, "scale": scale})
        invoke = (
            f"runPanelHunt({json.dumps(args.phase)}, "
            f"{json.dumps(values)}, {json.dumps(labels, ensure_ascii=False)}, "
            f"{json.dumps(specs)});"
        )
        body = SCRIPT.read_text(encoding="utf-8")
        prelude = ""
    source = prelude + body + "\n" + invoke + "\n"
    script = session.create_script(source)
    script.on("message", on_message)
    script.load()
    if not done.wait(args.wait or 120):
        messages.append({"type": "driver", "payload": {"kind": "timeout", "waited": args.wait or 120}})
    time.sleep(0.5)
    session.detach()

    text = json.dumps(messages, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}: {len(messages)} messages")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
