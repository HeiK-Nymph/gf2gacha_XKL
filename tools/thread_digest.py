"""Compact digest of a Codex rollout JSONL transcript.

Usage:
  python tools/thread_digest.py <rollout.jsonl> [--max-text N] [--out FILE]

Emits one line per notable event (user/assistant messages, tool calls,
tool results, errors) with truncated bodies, so a huge transcript can be
scanned without loading raw base64 payloads.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def clip(text, limit: int) -> str:
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[:limit] + f" ...[+{len(text) - limit} chars]"
    return text


def walk_text(node, out: list[str]) -> None:
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for key in ("text", "content", "output", "input"):
            if key in node:
                walk_text(node[key], out)
        if not out and "arguments" in node:
            walk_text(node["arguments"], out)
    elif isinstance(node, list):
        for item in node:
            walk_text(item, out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--max-text", type=int, default=500)
    ap.add_argument("--max-output", type=int, default=350)
    ap.add_argument("--out")
    args = ap.parse_args()

    lines: list[str] = []
    counts: dict[str, int] = {}

    with Path(args.path).open(encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            rtype = rec.get("type", "?")
            counts[rtype] = counts.get(rtype, 0) + 1
            ts = (rec.get("timestamp") or "")[11:19]
            payload = rec.get("payload") or {}

            if rtype == "session_meta" or rtype == "turn_context":
                continue

            if rtype == "response_item":
                ptype = payload.get("type")
                role = payload.get("role", "")
                if ptype == "message":
                    parts: list[str] = []
                    walk_text(payload.get("content"), parts)
                    body = clip("\n".join(parts), args.max_text)
                    if body:
                        lines.append(f"[{ts}] MSG {role}: {body}")
                elif ptype == "function_call":
                    name = payload.get("name", "?")
                    args_raw = payload.get("arguments") or ""
                    if isinstance(args_raw, dict):
                        args_raw = json.dumps(args_raw, ensure_ascii=False)
                    lines.append(f"[{ts}] CALL {name}: {clip(args_raw, args.max_text)}")
                elif ptype == "custom_tool_call":
                    name = payload.get("name", "?")
                    lines.append(f"[{ts}] CALL {name}: {clip(payload.get('input') or '', args.max_text)}")
                elif ptype == "function_call_output":
                    body = clip(payload.get("output") or "", args.max_output)
                    lines.append(f"[{ts}] RESULT: {body}")
                elif ptype == "custom_tool_call_output":
                    body = clip(payload.get("output") or "", args.max_output)
                    lines.append(f"[{ts}] RESULT: {body}")
                elif ptype == "reasoning":
                    parts = []
                    walk_text(payload.get("summary"), parts)
                    body = clip("\n".join(parts), 260)
                    if body:
                        lines.append(f"[{ts}] THINK: {body}")
                continue

            if rtype == "event_msg":
                etype = payload.get("type")
                if etype == "user_message":
                    lines.append(f"[{ts}] USER: {clip(payload.get('message') or '', args.max_text)}")
                elif etype in ("agent_message", "agent_reasoning"):
                    body = payload.get("message") or payload.get("text") or ""
                    lines.append(f"[{ts}] AGENT({etype}): {clip(body, args.max_text)}")
                elif etype in ("error", "stream_error"):
                    lines.append(f"[{ts}] ERROR: {clip(json.dumps(payload, ensure_ascii=False), args.max_output)}")

    header = f"# digest {args.path}\n# counts: {json.dumps(counts, ensure_ascii=False)}\n"
    text = header + "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}: {len(lines)} events, {len(text)} chars")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
