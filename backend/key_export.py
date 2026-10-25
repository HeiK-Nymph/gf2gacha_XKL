#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""小程序导入钥匙（XKL1）的编码、核验与导出

协议契约（不要在这里发明新字段）：
    - 消费端权威文档：XKL_WeChat/docs/IMPORT_KEY_PROTOCOL.md
    - 参考实现：XKL_android/app/src/main/java/uk/gf2gacha/xkl/data/MiniProgramKey.kt（编码）
      以及 ui/MainActivity.kt 的 verifyExportAccount / copyMiniProgramKey（导出流程）

与安卓端流程一一对应，改动前先读 MainActivity.verifyExportAccount：
    1. 核验凭证必须走「记录接口」第一页，而不是 account/info —— 账号接口只校验签名，
       access_token 过期后照样返回 uid，只看它会导出死钥匙（安卓踩过的坑，提交 4ac803d）；
    2. 官服（渠道 5）再调 account/info 核对 UID 一致；B服（渠道 6）记录接口通过即可 ——
       B服令牌不被 account/info 接受。UID 来源：安卓端来自 B站登录结果，PC 端没有登录
       能力、令牌 payload 里也没有 uid（GF2_SMS_LOGIN_PROTOCOL.md §6 只有
       openid/expires/is_guest/tinx），所以渠道 6 必须由用户补填游戏 UID；
    3. 核验期间捕获文件被新请求覆盖（用户在游戏里切了账号）时必须放弃导出，
       对应安卓的 matchingAccount 防串号；
    4. 钥匙只在「复制」动作里现算现发剪贴板：不落盘、不进日志、不返回给前端 JS，
       异常信息只带类型与接口文案，绝不回显凭证。

令牌是单会话的（协议文档 §7.2）：同账号在别处重新登录会立刻作废旧令牌，
token err 的正确处理是引导重新抓包，而不是当成网络故障。
"""
from __future__ import annotations

import base64
import json
import re
import threading
import time
from pathlib import Path

import requests

try:
    from backend.capture import HINT_OPEN_GACHA_PAGE, describe_capture, load_capture
except ImportError:  # 兼容只把 backend 目录加进 sys.path 的调用方式
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from backend.capture import HINT_OPEN_GACHA_PAGE, describe_capture, load_capture

try:  # verify=False 会刷 InsecureRequestWarning，这里和 main.py::_fetch_uid 一样静默
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

KEY_PREFIX = "XKL1."
CHANNEL_OFFICIAL = 5
CHANNEL_BILIBILI = 6
CHANNEL_LABELS = {CHANNEL_OFFICIAL: "官服", CHANNEL_BILIBILI: "B服"}

LIST_URL = "https://gf2-gacha-record.sunborngame.com/list"
ACCOUNT_URL = "https://gf2-zoneinfo.sunborngame.com/account/info"

# 与安卓 Gf2Api.verifyCredential 完全同参：角色池第一页，limit 顶格 20
VERIFY_POOL_TYPE_ID = "3"
PAGE_SIZE = "20"

USER_AGENT = "UnityPlayer/2019.4.40f1 (UnityWebRequest/1.0, libcurl/7.80.0-DEV)"
UNITY_VERSION = "2019.4.40f1"
REQUEST_TIMEOUT = 10

_UID_RE = re.compile(r"^[0-9]{4,32}$")
# 与安卓 Gf2Api.isTokenError 同口径：401 / message 带 token / 「登录|凭证…过期|失效」
_TOKEN_MSG_RE = re.compile(r"(登录|凭证).*(过期|失效)")

# 核验通过后的短时暂存：复制动作不再发网络请求（对应安卓「框里的复制不发请求」）。
# 只存内存，程序退出即消失。
_stash: dict = {}
_stash_lock = threading.Lock()


def _error(kind: str, msg: str, *, code=None) -> dict:
    return {"kind": kind, "msg": msg, "code": code}


# ---------------------------------------------------------------- 编码与解析

def _validate_uid(uid: str) -> str:
    if not isinstance(uid, str) or not _UID_RE.match(uid):
        raise ValueError("UID 格式不正确（应为 4-32 位数字）")
    return uid


def _validate_credential(credential: str) -> str:
    if (
        not isinstance(credential, str)
        or not credential.strip()
        or len(credential) > 4096
        or "\r" in credential
        or "\n" in credential
    ):
        raise ValueError("凭证格式不正确")
    return credential


def encode_key(uid: str, credential: str, channel_id: int) -> str:
    """XKL1. + base64url(JSON)。字段顺序与 IMPORT_KEY_PROTOCOL.md 的示例向量一致。"""
    _validate_uid(uid)
    _validate_credential(credential)
    if channel_id not in CHANNEL_LABELS:
        raise ValueError("游戏渠道不正确")
    payload = json.dumps(
        {"version": 1, "uid": uid, "credential": credential, "game_channel_id": channel_id},
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    return KEY_PREFIX + encoded


def decode_token_payload(credential: str) -> dict | None:
    """解出 access_token 的 payload（<base64 payload>.<签名> 的前半段）。失败返回 None。"""
    if not isinstance(credential, str) or "." not in credential:
        return None
    part = credential.split(".", 1)[0]
    padded = part + "=" * (-len(part) % 4)
    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            data = json.loads(decoder(padded).decode("utf-8"))
        except Exception:
            continue
        return data if isinstance(data, dict) else None
    return None


def token_expires_at(credential: str) -> int | None:
    payload = decode_token_payload(credential)
    expires = (payload or {}).get("expires")
    if isinstance(expires, (int, float)) and expires > 0:
        return int(expires)
    return None


def describe_expiry(credential: str, now: float | None = None) -> dict:
    """给界面展示的过期信息（纯本地解码，不发网络请求）"""
    expires_at = token_expires_at(credential)
    if expires_at is None:
        return {"expires_at": None, "expired": None, "remaining_text": None}
    now = time.time() if now is None else now
    remaining = int(expires_at - now)
    if remaining <= 0:
        text = "已过期"
    elif remaining < 3600:
        text = f"约 {max(1, remaining // 60)} 分钟后过期"
    elif remaining < 86400:
        text = f"约 {remaining // 3600} 小时后过期"
    else:
        text = f"约 {remaining // 86400} 天后过期"
    return {"expires_at": expires_at, "expired": remaining <= 0, "remaining_text": text}


def _get_header(headers: dict, name: str) -> str:
    if not isinstance(headers, dict):
        return ""
    if name in headers:
        return str(headers.get(name) or "")
    lowered = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lowered:
            return str(value or "")
    return ""


def detect_channel(capture: dict) -> int:
    """从捕获请求里识别渠道：官方客户端把 game_channel_id 放在 URL query（capture.params）。

    认不出来就按官服处理 —— 官服用户占绝大多数，误判成 B服 会直接要求补填 UID，
    比误判成官服更打扰。
    """
    for source in ((capture or {}).get("params"), (capture or {}).get("body")):
        if isinstance(source, dict):
            raw = _get_header(source, "game_channel_id")
            try:
                value = int(str(raw).strip())
            except (TypeError, ValueError):
                continue
            if value in CHANNEL_LABELS:
                return value
    return CHANNEL_OFFICIAL


# ---------------------------------------------------------------- 官方接口

def _record_page(authorization: str, channel_id: int) -> dict:
    """请求记录接口第一页（只验证、不翻页、不落盘），返回 {"ok": True, ...} 或 {"ok": False, "error": ...}"""
    params = {"game_channel_id": str(channel_id), "type_id": "3"}
    body = {"type_id": VERIFY_POOL_TYPE_ID, "limit": PAGE_SIZE}
    headers = {
        "User-Agent": USER_AGENT,
        "X-Unity-Version": UNITY_VERSION,
        "Accept": "*/*",
        "Authorization": authorization,
    }
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.post(
                LIST_URL, params=params, data=body, headers=headers,
                timeout=REQUEST_TIMEOUT, verify=False,
            )
    except Exception as exc:
        return {"ok": False, "error": _error("network", f"请求失败: {exc}")}
    return _parse_official_response(response)


def _parse_official_response(response) -> dict:
    if response.status_code != 200:
        preview = (response.text or "").strip().replace("\n", " ")[:120]
        # HTTP 401 与安卓 isTokenError 的 code==401 同口径：也是凭证失效
        kind = "token" if response.status_code == 401 else "http"
        return {"ok": False, "error": _error(kind, f"服务器返回 HTTP {response.status_code} {preview}", code=response.status_code)}
    try:
        payload = response.json()
    except Exception:
        preview = (response.text or "").strip().replace("\n", " ")[:120]
        return {"ok": False, "error": _error("parse", f"返回内容不是 JSON: {preview}")}
    if not isinstance(payload, dict):
        return {"ok": False, "error": _error("parse", "返回内容结构异常")}
    code = payload.get("code")
    if code != 0:
        detail = payload.get("msg") or payload.get("message") or f"接口返回 code={code}"
        kind = "api"
        if code == 401 or "token" in str(detail).lower() or _TOKEN_MSG_RE.search(str(detail)):
            kind = "token"
        return {"ok": False, "error": _error(kind, str(detail), code=code)}
    return {"ok": True, "json": payload}


def verify_credential(authorization: str, channel_id: int) -> dict:
    """按「刷新」同一条链路核验凭证是否真的还能用（安卓 Gf2Api.verifyCredential 的 PC 版）"""
    return _record_page(authorization, channel_id)


def fetch_account_uid(authorization: str, channel_id: int = CHANNEL_OFFICIAL) -> dict:
    """向账号接口要凭证对应的 UID。仅限官服：B服令牌不被该接口接受。"""
    params = {"game_channel_id": str(channel_id), "type_id": "3"}
    headers = {
        "User-Agent": USER_AGENT,
        "X-Unity-Version": UNITY_VERSION,
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Authorization": authorization,
    }
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.post(ACCOUNT_URL, params=params, json={}, headers=headers, timeout=REQUEST_TIMEOUT, verify=False)
    except Exception as exc:
        return {"ok": False, "error": _error("network", f"请求失败: {exc}")}
    result = _parse_official_response(response)
    if not result.get("ok"):
        return result
    uid = ((result.get("json") or {}).get("data") or {}).get("uid")
    uid = str(uid or "")
    if not _UID_RE.match(uid):
        return {"ok": False, "error": _error("parse", "官方返回的 UID 不合法")}
    return {"ok": True, "uid": uid}


# ---------------------------------------------------------------- 剪贴板

def copy_text_to_clipboard(text: str) -> bool:
    """Win32 剪贴板写入（CF_UNICODETEXT）。不依赖第三方库，失败返回 False。

    必须显式声明 64 位 HANDLE/指针签名。ctypes 默认把返回值当 32 位 int，
    GlobalAlloc 返回的高位句柄会被截断，随后 GlobalLock / SetClipboardData
    会稳定失败。剪贴板也可能被其他程序短暂占用，因此 OpenClipboard 允许短重试。
    """
    if text == "" or not text:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002

        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.EmptyClipboard.argtypes = []
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalFree.restype = wintypes.HGLOBAL

        opened = False
        for _ in range(10):
            if user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.02)
        if not opened:
            print(f"[ERROR] 写入剪贴板失败: OpenClipboard Win32={ctypes.get_last_error()}")
            return False

        data = text.encode("utf-16-le") + b"\x00\x00"
        try:
            if not user32.EmptyClipboard():
                print(f"[ERROR] 写入剪贴板失败: EmptyClipboard Win32={ctypes.get_last_error()}")
                return False
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            if not handle:
                print(f"[ERROR] 写入剪贴板失败: GlobalAlloc Win32={ctypes.get_last_error()}")
                return False
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                error_code = ctypes.get_last_error()
                kernel32.GlobalFree(handle)
                print(f"[ERROR] 写入剪贴板失败: GlobalLock Win32={error_code}")
                return False
            try:
                ctypes.memmove(pointer, data, len(data))
            finally:
                kernel32.GlobalUnlock(handle)
            # 成功后内存归系统所有，不能再 GlobalFree
            if not user32.SetClipboardData(CF_UNICODETEXT, handle):
                error_code = ctypes.get_last_error()
                kernel32.GlobalFree(handle)
                print(f"[ERROR] 写入剪贴板失败: SetClipboardData Win32={error_code}")
                return False
            return True
        finally:
            user32.CloseClipboard()
    except Exception as exc:
        print(f"[ERROR] 写入剪贴板失败: {type(exc).__name__}")
        return False


# ---------------------------------------------------------------- 对外主流程

def get_key_export_status() -> dict:
    """无网络预览：捕获状态 + 渠道 + 凭证过期时间。给界面决定怎么引导用户。"""
    info = describe_capture()
    data = load_capture() or {}
    authorization = _get_header(data.get("headers") or {}, "Authorization").strip()
    channel_id = detect_channel(data)
    status = {
        "ok": True,
        "capture": {
            "exists": info.get("exists"),
            "replayable": info.get("replayable"),
            "has_authorization": info.get("has_authorization"),
            "age_text": info.get("age_text"),
            "stale": info.get("stale"),
        },
        "has_credential": bool(authorization),
        "channel_id": channel_id,
        "channel_label": CHANNEL_LABELS[channel_id],
        # B服令牌在 PC 端拿不到 UID（payload 没有该字段、account/info 不认），需要用户补填
        "needs_manual_uid": channel_id == CHANNEL_BILIBILI,
        "verified": False,
    }
    if authorization:
        status.update(describe_expiry(authorization))
    return status


def start_key_export(uid_override: str | None = None) -> dict:
    """核验捕获的凭证并暂存结果（不生成钥匙、不写剪贴板）。

    官服：记录接口核验 -> account/info 取 UID（用户填了 UID 则要求一致）。
    B服：记录接口核验 -> UID 必须由用户补填。
    """
    data = load_capture()
    if not data:
        return {"ok": False, "error": _error("no_capture", "还没有捕获到游戏请求。" + HINT_OPEN_GACHA_PAGE)}
    if not (data.get("headers") and _get_header(data.get("headers") or {}, "Authorization").strip()):
        return {"ok": False, "error": _error("bad_capture", "捕获异常：缺少 Authorization，请重新在游戏里打开「招募 · 访问详情」页面")}

    authorization = _get_header(data.get("headers") or {}, "Authorization").strip()
    try:
        _validate_credential(authorization)
    except ValueError as exc:
        return {"ok": False, "error": _error("bad_capture", f"捕获的凭证不可用：{exc}")}

    if uid_override is not None:
        uid_override = str(uid_override).strip() or None  # 前端可能传空字符串表示「没填」
    if uid_override is not None:
        try:
            _validate_uid(uid_override)
        except ValueError as exc:
            return {"ok": False, "error": _error("format", str(exc))}

    channel_id = detect_channel(data)
    verified = verify_credential(authorization, channel_id)
    if not verified.get("ok"):
        error = dict(verified.get("error") or _error("unknown", "未知错误"))
        print(f"[ERROR] 钥匙导出核验失败: kind={error.get('kind')} code={error.get('code')}")
        return {"ok": False, "error": error}

    if channel_id == CHANNEL_OFFICIAL:
        account = fetch_account_uid(authorization, channel_id)
        if not account.get("ok"):
            return {"ok": False, "error": dict(account.get("error") or _error("unknown", "获取 UID 失败"))}
        uid = account["uid"]
        if uid_override is not None and uid_override != uid:
            return {"ok": False, "error": _error("uid_mismatch", f"填写的 UID（{uid_override}）与凭证对应的账号（{uid}）不一致")}
    else:
        if not uid_override:
            return {"ok": False, "error": _error("uid_required", "B服钥匙需要填写游戏 UID（游戏内个人信息页可见）后才能导出")}
        uid = uid_override

    # 防串号：核验期间捕获被新请求覆盖（用户切号/重抓）就不能把旧凭证的钥匙发出去
    fresh = load_capture()
    fresh_authorization = _get_header((fresh or {}).get("headers") or {}, "Authorization").strip()
    if not fresh or fresh_authorization != authorization:
        return {"ok": False, "error": _error("capture_changed", "核验期间捕获到新的游戏请求（可能在游戏里切换了账号），已放弃本次导出，请重试")}

    expiry = describe_expiry(authorization)
    with _stash_lock:
        _stash.clear()
        _stash.update({
            "uid": uid,
            "credential": authorization,
            "channel_id": channel_id,
        })
    print(f"[OK] 钥匙导出核验通过 uid={uid} 渠道={CHANNEL_LABELS[channel_id]}")
    return {
        "ok": True,
        "uid": uid,
        "channel_id": channel_id,
        "channel_label": CHANNEL_LABELS[channel_id],
        "needs_manual_uid": channel_id == CHANNEL_BILIBILI,
        **expiry,
    }


def copy_key_to_clipboard() -> dict:
    """把已核验的钥匙写进剪贴板。不再发任何网络请求（对应安卓 showExportKeyDialog 的「复制」）。"""
    with _stash_lock:
        stash = dict(_stash)
    if not stash:
        return {"ok": False, "error": _error("no_verified", "还没有完成核验，请先点「生成导出钥匙」")}

    fresh = load_capture() or {}
    fresh_authorization = _get_header(fresh.get("headers") or {}, "Authorization").strip()
    if fresh_authorization != stash["credential"]:
        with _stash_lock:
            _stash.clear()
        return {"ok": False, "error": _error("capture_changed", "捕获已被新的游戏请求覆盖（可能切换了账号），请重新导出")}

    try:
        key = encode_key(stash["uid"], stash["credential"], stash["channel_id"])
    except ValueError as exc:
        return {"ok": False, "error": _error("format", str(exc))}

    if not copy_text_to_clipboard(key):
        return {"ok": False, "error": _error("clipboard", "写入剪贴板失败，请重试")}
    print(f"[OK] 小程序钥匙已复制到剪贴板 uid={stash['uid']} 渠道={CHANNEL_LABELS[stash['channel_id']]}")
    return {
        "ok": True,
        "uid": stash["uid"],
        "channel_label": CHANNEL_LABELS[stash["channel_id"]],
    }
