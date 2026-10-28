#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""全局抓包 addon：把经过 mitmproxy 的每一条流量落盘成 JSONL。

用途只有两个：逆向「社区签到 / 兑换」协议时看真实请求；不进产品代码。
产品里的抓包走 backend/addons/addons.py（只认抽卡域名，只存一条可重放请求）。

落盘策略（有意为之）：
    * 不是目标类主机（deepseek / openai / microsoft / google 等）只留元信息，
      不留 header 和 body，避免把无关服务的凭证写进取证文件；
    * 图片 / 字体 / 音视频 / css / js 一律不落 body，只留一条元信息；
    * 文本类 body 截断到 256 KB，二进制 body 只留 32 KB 的 base64；
    * 每条写完立即 flush，抓包进程被强杀也不丢已抓到的部分。
"""
from __future__ import annotations

import base64
import json
import re
import threading
import time
from pathlib import Path

import mitmproxy.http

# 这些主机的 body / header 没有分析价值，不落盘（元信息保留，便于判断是谁在说话）
NO_BODY_HOST_RE = re.compile(
    r"(?:^|\.)("
    r"deepseek\.(?:com|ai)|openai\.com|anthropic\.com|"
    r"microsoft\.com|windowsupdate\.com|msftncsi\.com|msedge\.net|live\.com|bing\.com|"
    r"google\.com|googleapis\.com|gstatic\.com|googleusercontent\.com|"
    r"mozilla\.(?:org|net|com)|firefox\.com|apple\.com|icloud\.com"
    r")$",
    re.IGNORECASE,
)

TEXT_TYPE_HINTS = ("json", "text/", "xml", "javascript", "x-www-form-urlencoded")
BINARY_TYPE_HINTS = ("protobuf", "octet-stream", "msgpack", "grpc")

STATIC_TYPE_HINTS = (
    "image/", "font/", "audio/", "video/", "text/css", "text/javascript",
    "application/javascript", "application/x-javascript", "application/font",
)

MAX_TEXT = 256 * 1024
MAX_BINARY = 32 * 1024


def _content_type(headers) -> str:
    return str(headers.get("content-type") or "").lower()


def _is_noise(type_hint: str) -> bool:
    return any(hint in type_hint for hint in STATIC_TYPE_HINTS)


def _decode_text(data: bytes) -> str:
    for enc in ("utf-8", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def _body_payload(data: bytes, type_hint: str) -> dict:
    """把 body 变成可读的 JSON 字段：文本给 text，二进制给 base64 + 摘要。"""
    if not data:
        return {}
    if _is_noise(type_hint):
        return {"skipped": "static"}

    if any(hint in type_hint for hint in BINARY_TYPE_HINTS) and not any(
        hint in type_hint for hint in TEXT_TYPE_HINTS
    ):
        if len(data) <= MAX_BINARY:
            return {"base64": base64.b64encode(data).decode("ascii"), "bytes": len(data)}
        return {"skipped": "binary-too-large", "bytes": len(data)}

    if any(hint in type_hint for hint in TEXT_TYPE_HINTS) or len(data) <= 64 * 1024:
        text = _decode_text(data[:MAX_TEXT])
        payload = {"text": text, "bytes": len(data)}
        if len(data) > MAX_TEXT:
            payload["truncated"] = True
        return payload

    return {"skipped": "unknown-binary", "bytes": len(data)}


class GlobalRecorder:
    """mitmproxy addon：所有响应落一行 JSON。"""

    def __init__(self, out_dir: Path | str):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.flows_path = self.out_dir / "flows.jsonl"
        self.hosts_path = self.out_dir / "hosts.json"
        self._lock = threading.Lock()
        self._seq = 0
        self._fh = None
        self.started_at = time.time()
        self.host_counter: dict[str, int] = {}
        self.flow_count = 0

    # ---- 落盘 ----
    def _append(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            if self._fh is None:
                self._fh = open(self.flows_path, "a", encoding="utf-8", buffering=1)
            self._fh.write(line + "\n")
            self._seq += 1

    def _flush_hosts(self) -> None:
        with self._lock:
            snapshot = dict(self.host_counter)
        try:
            self.hosts_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    # ---- mitmproxy hooks ----
    def http_connect(self, flow: mitmproxy.http.HTTPFlow) -> None:
        # 出问题时（例如客户端做了证书固定）至少能知道它想连哪里
        self._record_meta(flow, kind="connect")

    def error(self, flow: mitmproxy.http.HTTPFlow) -> None:
        self._record_meta(flow, kind="error", error=str(flow.error))

    def response(self, flow: mitmproxy.http.HTTPFlow) -> None:
        self._record_meta(flow, kind="flow")

    def _record_meta(self, flow, kind: str, error: str = "") -> None:
        req = flow.request
        host = req.pretty_host
        with self._lock:
            self.host_counter[host] = self.host_counter.get(host, 0) + 1
            self.flow_count += 1
            total = self.flow_count
        if total % 25 == 0:
            self._flush_hosts()

        record: dict = {
            "seq": self._seq + 1,
            "t": time.time(),
            "kind": kind,
            "method": req.method,
            "host": host,
            "port": req.port,
            "path": req.path,
            "url": req.url,
        }
        if flow.response is not None:
            record["status"] = flow.response.status_code
            record["reason"] = flow.response.reason
            record["content_type"] = _content_type(flow.response.headers)
            record["resp_bytes"] = len(flow.response.raw_content or b"")
        if error:
            record["error"] = error

        full = not NO_BODY_HOST_RE.search(host)

        if full:
            record["req_headers"] = dict(req.headers.items())
            record["query"] = dict(req.query)
            if flow.response is not None:
                record["resp_headers"] = dict(flow.response.headers.items())

            try:
                req_body = req.get_content(strict=False) or b""
            except Exception:
                req_body = b""
            if req_body:
                record["req_body"] = _body_payload(req_body, _content_type(req.headers))

            if flow.response is not None:
                try:
                    resp_body = flow.response.get_content(strict=False) or b""
                except Exception:
                    resp_body = b""
                if resp_body and kind == "flow":
                    record["resp_body"] = _body_payload(resp_body, record.get("content_type", ""))

        self._append(record)

    def done(self) -> None:
        self._flush_hosts()
        with self._lock:
            if self._fh is not None:
                self._fh.flush()
                self._fh.close()
                self._fh = None

    def summary(self) -> dict:
        return {
            "started_at": self.started_at,
            "flows": self.flow_count,
            "hosts": dict(sorted(self.host_counter.items(), key=lambda kv: -kv[1])),
        }
