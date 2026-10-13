#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""mitmproxy addon：抓取游戏发往抽卡记录接口的请求并落盘

这是整条链路的第一环 —— 抓不到，后面「更新记录」一定失败。
旧版有三个问题，这里一并修掉：

    1. `return True` 写在事件回调之前，回调是死代码（界面永远收不到通知）；
    2. 只认 urlencoded 表单，哪天接口换成 JSON body 会静默存成空 body；
    3. 同域名下任何请求都会覆盖捕获文件，包括不带 Authorization 的那些，
       一旦被覆盖，「更新记录」就会莫名失败（现在由 capture.save_capture 兜底）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import mitmproxy.http

# addons 被 mitmproxy 以顶层模块名 import；这里对 backend 包做一次路径兜底
try:
    from backend.capture import save_capture
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from backend.capture import save_capture

# 抽卡记录接口所在域名（见 XKL_java/JAVA_BACKEND_SYSTEM_ANALYSIS.md）
TARGET_DOMAIN = "gf2-gacha-record.sunborngame.com"

_event_handler = None


def set_event_handler(handler):
    """注册捕获回调（主程序传进来，用于把状态推给界面）"""
    global _event_handler
    _event_handler = handler


def _parse_body(request) -> tuple[dict, str]:
    """把请求体解析成字典，返回 (body, raw_preview)

    raw_preview 只用于日志/排障，不参与重放，避免污染 body。
    """
    content_type = str(request.headers.get("Content-Type") or "").lower()

    if "json" in content_type:
        try:
            data = request.json
            if isinstance(data, dict):
                return data, ""
        except Exception as exc:
            print(f"[addon] JSON 请求体解析失败: {exc}")

    try:
        form = dict(request.urlencoded_form or {})
        if form:
            return form, ""
    except Exception as exc:
        print(f"[addon] 表单请求体解析失败: {exc}")

    try:
        multipart = dict(request.multipart_form or {})
        if multipart:
            return {k: str(v) for k, v in multipart.items()}, ""
    except Exception as exc:
        print(f"[addon] multipart 请求体解析失败: {exc}")

    raw = ""
    try:
        raw = (request.get_text(strict=False) or "")[:2000]
    except Exception as exc:
        print(f"[addon] 读取原始请求体失败: {exc}")
    return {}, raw


class getGF2Req:
    def __init__(self):
        self.target_domain = TARGET_DOMAIN

    def request(self, flow: mitmproxy.http.HTTPFlow):
        url = flow.request.url
        if self.target_domain not in url:
            return

        body, raw_preview = _parse_body(flow.request)
        request_data = {
            "url": url,
            "method": flow.request.method,
            "headers": {k: v for k, v in flow.request.headers.items()},
            "body": body,
            "params": dict(flow.request.query),
        }
        if raw_preview:
            request_data["raw_body_preview"] = raw_preview

        result = save_capture(request_data, source="mitmproxy")
        if not result.get("saved"):
            print(f"[addon] 忽略 {url} -> {result.get('reason')}")
            return

        authorization = request_data["headers"].get("Authorization") or request_data["headers"].get("authorization")
        print(
            f"[addon] 已捕获游戏请求: {url} "
            f"(body字段={list(body.keys())}, 带Authorization={bool(authorization)})"
        )

        if _event_handler is not None and hasattr(_event_handler, "on_request"):
            try:
                _event_handler.on_request(request_data)
            except Exception as exc:
                print(f"[addon] 通知主程序失败: {exc}")


addons = [
    getGF2Req()
]
