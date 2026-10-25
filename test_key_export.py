#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""小程序钥匙导出链路测试：编码 -> 过期解析 -> 记录接口核验 -> UID 核对 -> 防串号 -> 剪贴板

官方接口用轻量 stub 顶替 requests（只验证我们自己写的逻辑，绝不发真实请求）。
主流程测试使用剪贴板 stub；另有一条 Windows 真实剪贴板回归测试，结束后恢复原文本。
捕获文件重定向到临时目录，不碰 json/latest_request.json。

注意：requests stub 必须在 import backend.key_export 之前装好，否则模块绑定的是真实
requests，测试会打出真实网络请求（第一次跑就犯过这个错）。

运行：python test_key_export.py
"""
import base64
import contextlib
import io
import json
import os
import sys
import tempfile
import time
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

# 协议文档 IMPORT_KEY_PROTOCOL.md 里的示例向量（仅用于协议测试）
PROTOCOL_VECTOR = (
    "XKL1.eyJ2ZXJzaW9uIjoxLCJ1aWQiOiIxMjM0NTY3ODkiLCJjcmVkZW50aWFsIjoiZGVtbyIs"
    "ImdhbWVfY2hhbm5lbF9pZCI6NX0"
)
UID = "123456789"
UID_ALT = "987654321"


# ---------------------------------------------------------------- requests stub
class _FakeResponse:
    def __init__(self, status, text):
        self.status_code = status
        self._text = text

    @property
    def text(self):
        return self._text

    def json(self):
        return json.loads(self._text)


_HANDLER = {"current": lambda call: (200, json.dumps({"code": 0, "message": "OK"}))}
CALLS = []


def _set_handler(handler):
    """每个用例开始时设置自己的接口行为，并清空调用记录"""
    _HANDLER["current"] = handler
    CALLS.clear()


def _install_requests_stub():
    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, params=None, data=None, json=None, headers=None, timeout=None, verify=None):
            call = {"url": url, "params": params, "data": data, "json": json, "headers": headers}
            CALLS.append(call)
            status, text = _HANDLER["current"](call)
            return _FakeResponse(status, text)

    module = types.ModuleType("requests")
    module.Session = _FakeSession
    sys.modules["requests"] = module


def _official_handler(*, record_ok=True, account_uid=UID):
    """官服双接口的默认 handler：记录接口 + account/info"""
    def handler(call):
        if "gacha-record" in call["url"]:
            body = (
                {"code": 0, "message": "OK", "data": {"list": [], "next": ""}}
                if record_ok else {"code": -1, "message": "token err"}
            )
            return 200, json.dumps(body)
        return 200, json.dumps({"code": 0, "message": "OK", "data": {"uid": account_uid}})
    return handler


# ---------------------------------------------------------------- fixtures
def _credential(*, openid="open-demo", expires=None):
    """造一个 <base64 payload>.<32位签名> 形状的假凭证（payload 结构见协议文档 §6）"""
    payload = {"openid": openid, "expires": expires, "is_guest": 0, "tinx": 9}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).rstrip(b"=").decode("ascii")
    return f"{encoded}.{'x' * 32}"


def _write_capture(capture, tmpdir, *, authorization, channel="5"):
    capture.CAPTURE_PATH = Path(tmpdir) / "latest_request.json"
    capture.CAPTURE_PATH.write_text(json.dumps({
        "url": f"https://gf2-gacha-record.sunborngame.com/list?game_channel_id={channel}&type_id=3",
        "params": {"game_channel_id": channel, "type_id": "3"},
        "headers": {"Authorization": authorization, "User-Agent": "UnityPlayer/test"},
        "body": {"type_id": "3"},
        "captured_at": "2026-10-25T00:00:00+08:00",
    }, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- 用例
def test_encode_matches_protocol_vector(key_export):
    key = key_export.encode_key(UID, "demo", 5)
    assert key == PROTOCOL_VECTOR, f"与协议文档示例向量不一致: {key}"
    payload = json.loads(base64.urlsafe_b64decode(key[len("XKL1."):] + "===").decode("utf-8"))
    assert payload == {"version": 1, "uid": UID, "credential": "demo", "game_channel_id": 5}
    print("  PASS 编码与协议文档示例向量逐字节一致")


def test_encode_rejects_bad_input(key_export):
    bad_cases = [
        ("123", "demo", 5),          # UID 太短
        ("12345678a", "demo", 5),    # UID 带字母
        (UID, "", 5),                # 空凭证
        (UID, "a" * 4097, 5),        # 凭证超长
        (UID, "abc\ndef", 5),        # 凭证带换行
        (UID, "demo", 7),            # 渠道不合法
    ]
    for uid, credential, channel in bad_cases:
        try:
            key_export.encode_key(uid, credential, channel)
        except ValueError:
            continue
        raise AssertionError(f"应当拒绝: uid={uid!r} credential_len={len(credential)} channel={channel}")
    print("  PASS 非法输入全部被拒绝")


def test_expiry_describe(key_export):
    future = key_export.describe_expiry(_credential(expires=time.time() + 2 * 3600))
    assert future["expired"] is False and "小时" in future["remaining_text"], future
    past = key_export.describe_expiry(_credential(expires=time.time() - 60))
    assert past["expired"] is True and past["remaining_text"] == "已过期", past
    none_case = key_export.describe_expiry("not-a-token")
    assert none_case["expires_at"] is None, none_case
    print("  PASS 过期时间解析与文案")


def test_detect_channel(key_export):
    assert key_export.detect_channel({"params": {"game_channel_id": "6"}}) == 6
    assert key_export.detect_channel({"params": {"game_channel_id": 5}}) == 5
    assert key_export.detect_channel({"body": {"game_channel_id": "6"}}) == 6  # params 缺失时看 body
    assert key_export.detect_channel({}) == 5                                  # 认不出按官服
    assert key_export.detect_channel({"params": {"game_channel_id": "99"}}) == 5
    print("  PASS 渠道识别")


def test_verify_credential(key_export):
    _set_handler(_official_handler(record_ok=False))
    result = key_export.verify_credential(_credential(expires=time.time() + 3600), 5)
    assert not result["ok"] and result["error"]["kind"] == "token", result
    # 与安卓 Gf2Api 同参：query 带 game_channel_id/type_id=3，body 是角色池第一页 limit=20
    assert CALLS[0]["params"]["game_channel_id"] == "5", CALLS[0]
    assert CALLS[0]["data"] == {"type_id": "3", "limit": "20"}, CALLS[0]

    # HTTP 401 同样归为凭证失效（对齐安卓 isTokenError 的 code==401）
    _set_handler(lambda call: (401, "unauthorized"))
    result = key_export.verify_credential(_credential(expires=time.time() + 3600), 5)
    assert not result["ok"] and result["error"]["kind"] == "token", result

    _set_handler(_official_handler(record_ok=True))
    result = key_export.verify_credential(_credential(expires=time.time() + 3600), 5)
    assert result["ok"], result
    print("  PASS 记录接口核验：token err / HTTP 401 归类、请求参数与安卓同参")


def test_start_official_happy_path(key_export, capture):
    credential = _credential(expires=time.time() + 3 * 86400)
    _set_handler(_official_handler(account_uid=UID))
    key_export._stash.clear()

    with tempfile.TemporaryDirectory() as tmp:
        _write_capture(capture, tmp, authorization=credential, channel="5")
        result = key_export.start_key_export()

        assert result["ok"], result
        assert result["uid"] == UID and result["channel_label"] == "官服", result
        assert result["needs_manual_uid"] is False and result["expired"] is False, result
        assert len([c for c in CALLS if "gacha-record" in c["url"]]) == 1, CALLS
        assert len([c for c in CALLS if "zoneinfo" in c["url"]]) == 1, CALLS

        # 复制：不再发请求，剪贴板内容可回解，且钥匙/凭证绝不进日志
        copied = {}

        def _fake_clipboard(text):
            copied["text"] = text
            return True

        buffer = io.StringIO()
        with patch.object(key_export, 'copy_text_to_clipboard', side_effect=_fake_clipboard), \
             contextlib.redirect_stdout(buffer):
            result = key_export.copy_key_to_clipboard()
        assert result["ok"] and result["uid"] == UID, result
        assert copied["text"] == key_export.encode_key(UID, credential, 5)
        logs = buffer.getvalue()
        assert credential not in logs and copied["text"] not in logs, "钥匙/凭证泄漏进日志"
    print("  PASS 官服导出：核验+UID 核对+复制，日志零泄漏")


def test_start_official_uid_mismatch(key_export, capture):
    _set_handler(_official_handler(account_uid=UID))
    key_export._stash.clear()
    with tempfile.TemporaryDirectory() as tmp:
        _write_capture(capture, tmp, authorization=_credential(expires=time.time() + 3600))
        result = key_export.start_key_export(UID_ALT)
    assert not result["ok"] and result["error"]["kind"] == "uid_mismatch", result
    print("  PASS 官服 UID 不一致被拦截")


def test_start_bili_requires_manual_uid(key_export, capture):
    _set_handler(_official_handler())
    key_export._stash.clear()
    with tempfile.TemporaryDirectory() as tmp:
        _write_capture(capture, tmp, authorization=_credential(expires=time.time() + 3600), channel="6")
        missing = key_export.start_key_export()
        assert not missing["ok"] and missing["error"]["kind"] == "uid_required", missing

        ok = key_export.start_key_export(UID)
    assert ok["ok"], ok
    assert ok["channel_id"] == 6 and ok["needs_manual_uid"] is True, ok
    # B服不调 account/info（B服令牌不被它接受）
    assert not [c for c in CALLS if "zoneinfo" in c["url"]], CALLS
    print("  PASS B服导出：记录接口核验、跳过 account/info、UID 必须补填")


def test_start_capture_states(key_export, capture):
    _set_handler(_official_handler())
    key_export._stash.clear()
    with tempfile.TemporaryDirectory() as tmp:
        # 没有捕获文件
        capture.CAPTURE_PATH = Path(tmp) / "latest_request.json"
        result = key_export.start_key_export()
        assert not result["ok"] and result["error"]["kind"] == "no_capture", result
        # 捕获缺 Authorization
        _write_capture(capture, tmp, authorization="", channel="5")
        result = key_export.start_key_export()
        assert not result["ok"] and result["error"]["kind"] == "bad_capture", result
    print("  PASS 无捕获 / 缺凭证的引导口径")


def test_capture_changed_during_verify(key_export, capture):
    key_export._stash.clear()
    credential_a = _credential(openid="account-a", expires=time.time() + 3600)
    credential_b = _credential(openid="account-b", expires=time.time() + 3600)

    with tempfile.TemporaryDirectory() as tmp:
        def handler(call):
            if "gacha-record" not in call["url"]:
                return 200, json.dumps({"code": 0, "message": "OK", "data": {"uid": UID}})
            # 核验请求在途时，游戏侧重新抓包覆盖了捕获文件（用户切了账号）
            _write_capture(capture, tmp, authorization=credential_b)
            return 200, json.dumps({"code": 0, "message": "OK", "data": {"list": [], "next": ""}})

        _set_handler(handler)
        _write_capture(capture, tmp, authorization=credential_a)
        result = key_export.start_key_export()
    assert not result["ok"] and result["error"]["kind"] == "capture_changed", result
    print("  PASS 核验期间捕获被覆盖 -> 防串号放弃导出")


def test_copy_requires_verified_stash(key_export, capture):
    _set_handler(_official_handler())
    key_export._stash.clear()
    result = key_export.copy_key_to_clipboard()
    assert not result["ok"] and result["error"]["kind"] == "no_verified", result
    print("  PASS 未核验先复制 -> 明确报错")


def _read_windows_clipboard_text():
    """读取当前 Unicode 文本；用于真实剪贴板回归测试的原值恢复。"""
    if os.name != 'nt':
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL('user32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    opened = False
    for _ in range(10):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.02)
    if not opened:
        return None
    try:
        handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
        if not handle:
            return None
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return None
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def test_windows_clipboard_roundtrip(key_export):
    """真实 Win32 剪贴板写入：防止 ctypes 64 位句柄截断回归。"""
    if os.name != 'nt':
        print('  SKIP 非 Windows 环境')
        return
    token = 'XKL_CLIPBOARD_REGRESSION_20261025'
    previous = _read_windows_clipboard_text()
    try:
        assert key_export.copy_text_to_clipboard(token) is True
        assert _read_windows_clipboard_text() == token
    finally:
        if previous is not None:
            key_export.copy_text_to_clipboard(previous)
    print('  PASS 真实 Win32 剪贴板可正确写入并读回')


def test_status_preview(key_export, capture):
    _set_handler(_official_handler())
    key_export._stash.clear()
    with tempfile.TemporaryDirectory() as tmp:
        capture.CAPTURE_PATH = Path(tmp) / "latest_request.json"  # 不存在
        status = key_export.get_key_export_status()
        assert status["has_credential"] is False and status["capture"]["exists"] is False, status

        _write_capture(capture, tmp, authorization=_credential(expires=time.time() + 3600), channel="5")
        status = key_export.get_key_export_status()
        assert status["has_credential"] is True and status["channel_label"] == "官服", status
        assert status["needs_manual_uid"] is False and status["remaining_text"], status
    print("  PASS 无网络预览：捕获状态 / 渠道 / 过期提示")


# ---------------------------------------------------------------- runner
def main():
    _install_requests_stub()  # 必须先于 backend.key_export 的导入
    import backend.capture as capture
    import backend.key_export as key_export

    tests = [
        ("编码协议向量", test_encode_matches_protocol_vector, (key_export,)),
        ("编码拒绝非法输入", test_encode_rejects_bad_input, (key_export,)),
        ("过期解析", test_expiry_describe, (key_export,)),
        ("渠道识别", test_detect_channel, (key_export,)),
        ("记录接口核验", test_verify_credential, (key_export,)),
        ("官服导出全链路", test_start_official_happy_path, (key_export, capture)),
        ("官服 UID 不一致", test_start_official_uid_mismatch, (key_export, capture)),
        ("B服补填 UID", test_start_bili_requires_manual_uid, (key_export, capture)),
        ("无捕获/缺凭证", test_start_capture_states, (key_export, capture)),
        ("核验中捕获被覆盖", test_capture_changed_during_verify, (key_export, capture)),
        ("未核验先复制", test_copy_requires_verified_stash, (key_export, capture)),
        ("真实 Win32 剪贴板", test_windows_clipboard_roundtrip, (key_export,)),
        ("无网络预览", test_status_preview, (key_export, capture)),
    ]

    failures = []
    for name, func, args in tests:
        print(f"[测试] {name}")
        try:
            func(*args)
        except AssertionError as exc:
            failures.append(name)
            print(f"  FAIL {exc}")
        except Exception as exc:  # noqa: BLE001
            import traceback

            failures.append(name)
            traceback.print_exc()

    print("=" * 60)
    if failures:
        print(f"失败 {len(failures)} 项: {failures}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
