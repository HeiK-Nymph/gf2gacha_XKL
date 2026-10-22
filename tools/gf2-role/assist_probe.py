"""Replay a captured GF2 login and issue one read-only assist query.

The login payload comes from a local capture and is never printed or written
to output. One attempt only: no retry loop, no game UI interaction.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import socket
import struct
import time
from pathlib import Path

_spec = importlib.util.spec_from_file_location("wire", Path(__file__).with_name("wire.py"))
wire = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wire)


def encode_varint(n: int) -> bytes:
    out = bytearray()
    while n > 127:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


def message(sequence: int, command: int, payload: bytes) -> bytes:
    body = struct.pack("<HH", command, len(payload)) + payload
    return sequence.to_bytes(3, "little") + struct.pack("<H", len(body)) + body


def receive(sock: socket.socket, want: set[int], timeout: float) -> list[tuple[int, int, bytes]]:
    """Read frames until every wanted command is seen or the timeout expires."""
    buffer = b""
    seen: list[tuple[int, int, bytes]] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sock.settimeout(max(0.2, deadline - time.monotonic()))
        try:
            chunk = sock.recv(65536)
        except socket.timeout:
            break
        if not chunk:
            break
        buffer += chunk
        try:
            _, messages = wire.frames(buffer)
        except wire.WireError:
            continue
        if messages:
            seen = messages
        if want and want.issubset({c for _, c, _ in messages}):
            break
    return seen


def run(args) -> dict:
    client = Path(args.login_stream).read_bytes()
    _, login_messages = wire.frames(client)
    login = next((p for _, c, p in login_messages if c == 10001), None)
    if login is None:
        raise SystemExit("no 10001 message in login stream")

    report: dict = {"loginSent": False, "loginConfirmed": False, "querySent": False,
                    "responseReceived": False}
    with socket.create_connection((args.host, args.port), timeout=15) as sock:
        sock.sendall(message(381, 10001, login))
        report["loginSent"] = True
        first = receive(sock, {10002, 19900}, 15)
        report["loginCommands"] = [c for _, c, _ in first]
        login_ok = any(c == 10002 for _, c, _ in first)
        report["loginConfirmed"] = login_ok
        if report.get("errorCommand") or not login_ok:
            notice = next((p for _, c, p in first if c == 19900), None)
            if notice is not None:
                report["noticeFields"] = [
                    {"field": n, "wire": w, **({"integer": v} if w == 0 else {"bytes": len(v)})}
                    for n, w, v in wire.protobuf(notice) if w != 2 or len(v) < 256
                ]
            return report
        payload = encode_varint((1 << 3) | 0) + encode_varint(args.uid)
        sock.sendall(message(394, 10428, payload))
        report["querySent"] = True
        second = receive(sock, {10429}, 20)
        report["queryCommands"] = [c for _, c, _ in second]
        for _, command, payload in second:
            if command != 10429:
                continue
            report["responseReceived"] = True
            target = wire.scalar(wire.protobuf(payload), 1)
            report["responseUid"] = target
            report["uidMatches"] = target == args.uid
            if args.snapshot_out:
                Path(args.snapshot_out).write_bytes(message(0, 10429, payload))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--login-stream", required=True)
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, default=7001)
    ap.add_argument("--uid", type=int, required=True)
    ap.add_argument("--out")
    ap.add_argument("--snapshot-out")
    args = ap.parse_args()
    report = run(args)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
