#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""抽卡请求捕获文件（json/latest_request.json）的统一读写

工具的工作方式：
    1. 内置 mitmproxy 拦截游戏发往 gf2-gacha-record.sunborngame.com 的请求；
    2. 把这条请求（headers / body / params）落盘成 json/latest_request.json；
    3. 「更新记录」按钮只是把这份请求原样重放一遍（见 backend/api/getGacha.py）。

所以这个文件的状态直接决定用户能不能用：
    - 用户没在游戏里打开过「招募 · 访问详情」页面 -> 文件不存在或为空 -> 必然失败；
    - 抓到的是同域名的其它请求（没有 Authorization）-> 重放必然失败；
    - 抓到的请求太旧 -> Authorization 可能已过期。

以前 main.py / addons.py / api/getGacha.py 各自拼路径、各自判断，口径不一致，
导致「没抓到」和「网络失败」对用户显示成同一句话。这里集中管理这些判断。
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

# 与 main.py 的 Path(__file__).parent / "json" 指向同一个文件
CAPTURE_PATH = Path(__file__).resolve().parent.parent / "json" / "latest_request.json"

# 超过这个时间没有重新捕获，就认为 token 大概率已经过期（仅用于提示，不阻断）
STALE_AFTER_SECONDS = 30 * 60

# 给用户看的标准引导语，前后端共用一套口径
HINT_OPEN_GACHA_PAGE = (
    "请先打开游戏 → 进入「招募 · 访问详情」页面（进入这一页才会发出抽卡请求），"
    "再点『更新记录』。"
)

_lock = threading.RLock()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _get_header(headers: dict, name: str) -> str:
    """大小写不敏感地取 header"""
    if not isinstance(headers, dict):
        return ""
    if name in headers:
        return str(headers.get(name) or "")
    lowered = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lowered:
            return str(value or "")
    return ""


def has_authorization(data: dict) -> bool:
    return bool(_get_header((data or {}).get("headers") or {}, "Authorization").strip())


def is_replayable(data: dict) -> bool:
    """这份捕获能不能拿去重放：必须有 Authorization，且 body/params 结构正常"""
    if not isinstance(data, dict):
        return False
    if not has_authorization(data):
        return False
    if not isinstance(data.get("body"), dict) or not data.get("body"):
        return False
    params = data.get("params")
    return params is None or isinstance(params, dict)


def _read_text_unlocked() -> str:
    try:
        return CAPTURE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except Exception as exc:  # 编码异常 / 权限问题
        print(f"[capture] 读取捕获文件失败: {exc}")
        return ""


def _load_unlocked() -> dict | None:
    text = _read_text_unlocked().strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except Exception as exc:
        print(f"[capture] 捕获文件不是合法 JSON: {exc}")
        return None
    return data if isinstance(data, dict) else None


def _write_unlocked(data: dict) -> None:
    CAPTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 原子写入：避免 addon 写一半时被「更新记录」读到半个文件
    fd, tmp_path = tempfile.mkstemp(
        prefix="latest_request_", suffix=".json", dir=str(CAPTURE_PATH.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=4)
        os.replace(tmp_path, CAPTURE_PATH)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def save_capture(data: dict, *, source: str = "mitmproxy") -> dict:
    """保存一条捕获到的请求（原子写入）

    返回 {"saved": bool, "reason": str, "path": str}

    重要行为：如果本地已经有一条「可重放」的捕获，而新来的这条不可重放
    （例如同域名下不带 Authorization 的其它接口），则保留旧的、丢弃新的。
    否则用户的记录会被一条无关请求覆盖，接着「更新记录」就莫名其妙失败。
    """
    if not isinstance(data, dict):
        return {"saved": False, "reason": "数据不是字典", "path": str(CAPTURE_PATH)}

    payload = dict(data)
    payload.setdefault("headers", {})
    payload.setdefault("body", {})
    payload.setdefault("params", {})
    payload["captured_at"] = _now_iso()
    payload["captured_ts"] = time.time()
    payload["capture_source"] = source

    try:
        with _lock:
            old = _load_unlocked()
            if old and is_replayable(old) and not is_replayable(payload):
                return {
                    "saved": False,
                    "reason": "新请求不可重放（缺少 Authorization / body），保留已有的捕获",
                    "path": str(CAPTURE_PATH),
                }
            _write_unlocked(payload)
    except Exception as exc:
        return {"saved": False, "reason": f"写入失败: {exc}", "path": str(CAPTURE_PATH)}

    return {"saved": True, "reason": "", "path": str(CAPTURE_PATH)}


def load_capture() -> dict | None:
    """读取捕获文件，不存在 / 空 / 坏 JSON 都返回 None"""
    with _lock:
        return _load_unlocked()


def clear_capture() -> dict:
    """清空捕获文件（隐私考虑：文件里有 Authorization，用户可能想手动抹掉）"""
    try:
        with _lock:
            CAPTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CAPTURE_PATH.write_text("", encoding="utf-8")
    except Exception as exc:
        return {"status": "error", "msg": f"清除捕获失败: {exc}"}
    print("[capture] 已清空捕获文件")
    return {"status": "success", "msg": "已清除捕获的游戏请求"}


def _human_age(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds} 秒前"
    if seconds < 3600:
        return f"{seconds // 60} 分钟前"
    if seconds < 86400:
        return f"{seconds // 3600} 小时前"
    return f"{seconds // 86400} 天前"


def describe_capture() -> dict:
    """给界面 / 日志用的捕获状态描述（不抛异常）"""
    try:
        exists = CAPTURE_PATH.exists()
        size = CAPTURE_PATH.stat().st_size if exists else 0
    except OSError:
        exists, size = False, 0

    data = None
    if exists and size > 0:
        with _lock:
            data = _load_unlocked()

    captured_ts = None
    captured_at = None
    if isinstance(data, dict):
        captured_at = data.get("captured_at")
        raw_ts = data.get("captured_ts")
        if isinstance(raw_ts, (int, float)):
            captured_ts = float(raw_ts)
        elif isinstance(captured_at, str) and captured_at:
            try:
                captured_ts = datetime.fromisoformat(captured_at).timestamp()
            except ValueError:
                captured_ts = None

    age_seconds = None
    if captured_ts is not None:
        age_seconds = max(0.0, time.time() - captured_ts)

    return {
        "path": str(CAPTURE_PATH),
        "exists": exists,
        "size": size,
        "empty": size == 0,
        "parsed": data is not None,
        "has_authorization": has_authorization(data or {}),
        "replayable": is_replayable(data or {}),
        "captured_at": captured_at,
        "age_seconds": None if age_seconds is None else int(age_seconds),
        "age_text": _human_age(age_seconds),
        "stale": bool(age_seconds is not None and age_seconds > STALE_AFTER_SECONDS),
        "type_id": ((data or {}).get("body") or {}).get("type_id"),
        "url": (data or {}).get("url"),
    }
