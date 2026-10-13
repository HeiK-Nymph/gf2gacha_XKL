#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""捕获链路测试：addons 抓包 -> capture 落盘 -> getGacha 重放

本机（开发机）不一定装了 mitmproxy / aiohttp，所以这里用轻量 stub 顶替这两个
第三方依赖，只验证「我们自己写的逻辑」：请求体解析、不可重放请求不覆盖旧捕获、
分页、以及各类失败能不能映射成明确的原因。

运行：python test_capture_flow.py
"""
import asyncio
import contextlib
import io
import json
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


# ---------------------------------------------------------------- stubs
def _install_mitmproxy_stub():
    """顶替 mitmproxy.http（addons.py 只需要它来写类型注解）"""
    module_name = "mitmproxy"
    if module_name not in sys.modules:
        mitmproxy = types.ModuleType(module_name)
        http = types.ModuleType("mitmproxy.http")

        class HTTPFlow:  # noqa: D401 - 仅用于注解
            pass

        http.HTTPFlow = HTTPFlow
        mitmproxy.http = http
        sys.modules[module_name] = mitmproxy
        sys.modules["mitmproxy.http"] = http


def _install_aiohttp_stub(responses):
    """顶替 aiohttp.ClientSession

    responses: 可调用对象 (url, params, data, headers) -> (status, text)
    """
    module_name = "aiohttp"
    aiohttp = sys.modules.get(module_name)
    if aiohttp is None:
        aiohttp = types.ModuleType(module_name)
        sys.modules[module_name] = aiohttp
    aiohttp.__version__ = "stub"

    calls = []

    class _FakeResponse:
        def __init__(self, status, text):
            self.status = status
            self._text = text

        async def text(self):
            return self._text

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class ClientSession:
        def __init__(self, *args, **kwargs):
            pass

        def post(self, url, params=None, data=None, headers=None, ssl=None, allow_redirects=None):
            # 真实 aiohttp 里 post() 是同步方法，返回一个可用 async with 的上下文管理器
            calls.append({"url": url, "params": params, "data": dict(data or {}), "headers": headers})
            status, text = responses(url, params, dict(data or {}), headers or {})
            response = _FakeResponse(status, text)
            return response

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    aiohttp.ClientSession = ClientSession
    aiohttp.calls = calls
    sys.modules[module_name] = aiohttp
    return calls


def _capture(func):
    """执行 func，顺手把它 print 出来的日志也抓回来（用于断言日志内容）"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = func()
    return result, buf.getvalue()


class _FakeRequest:
    def __init__(self, url, method="POST", headers=None, query=None, form=None, json_body=None, text=""):
        self.url = url
        self.method = method
        self.headers = headers or {}
        self.query = dict(query or {})
        self.urlencoded_form = dict(form or {})
        self.multipart_form = {}
        self._json = json_body
        self._text = text

    @property
    def json(self):
        if self._json is None:
            raise ValueError("no json body")
        return self._json

    def get_text(self, strict=False):
        return self._text


class _FakeFlow:
    def __init__(self, request):
        self.request = request


GAME_URL = "https://gf2-gacha-record.sunborngame.com/list?lang=cn"


def _game_request(token="tok-1234"):
    return _FakeRequest(
        GAME_URL,
        headers={"Authorization": token, "Content-Type": "application/x-www-form-urlencoded"},
        query={"lang": "cn"},
        form={"type_id": "3", "page": "1"},
    )


# ---------------------------------------------------------------- tests
def test_missing_capture(tmpdir, capture):
    capture.CAPTURE_PATH = tmpdir / "latest_request.json"
    info = capture.describe_capture()
    assert info["exists"] is False, info
    assert info["replayable"] is False, info
    assert capture.load_capture() is None
    print("  PASS 没有捕获文件时状态为「未捕获」且不可重放")


def test_addon_saves_urlencoded(tmpdir, capture, addons):
    capture.CAPTURE_PATH = tmpdir / "latest_request.json"
    addon = addons.addons[0]
    addon.request(_FakeFlow(_game_request()))

    info = capture.describe_capture()
    assert info["exists"] and info["size"] > 0, info
    assert info["replayable"] is True, info
    assert info["has_authorization"] is True, info
    assert info["captured_at"], info
    assert info["age_seconds"] is not None and info["age_seconds"] < 60, info
    data = capture.load_capture()
    assert data["body"]["type_id"] == "3", data
    assert data["params"] == {"lang": "cn"}, data
    print("  PASS 带 Authorization 的表单请求被正确捕获并落盘")


def test_unrelated_request_does_not_overwrite(tmpdir, capture, addons):
    capture.CAPTURE_PATH = tmpdir / "latest_request.json"
    addon = addons.addons[0]
    addon.request(_FakeFlow(_game_request()))
    before = capture.load_capture()["headers"]["Authorization"]

    # 同域名下、不带 Authorization 的其它接口
    addon.request(_FakeFlow(_FakeRequest(
        "https://gf2-gacha-record.sunborngame.com/notice",
        headers={"Content-Type": "application/json"},
        json_body={"a": 1},
    )))

    after = capture.load_capture()
    assert after["headers"]["Authorization"] == before, after
    assert capture.describe_capture()["replayable"] is True
    print("  PASS 不带 Authorization 的同类请求不会覆盖已有捕获")


def test_addon_parses_json_body(tmpdir, capture, addons):
    capture.CAPTURE_PATH = tmpdir / "latest_request.json"
    addon = addons.addons[0]
    addon.request(_FakeFlow(_FakeRequest(
        GAME_URL,
        headers={"Authorization": "tok-json", "Content-Type": "application/json"},
        json_body={"type_id": "1"},
    )))
    data = capture.load_capture()
    assert data["body"] == {"type_id": "1"}, data
    print("  PASS 接口若改成 JSON 请求体也能解析（旧版会存成空 body）")


def test_addon_notifies_handler(tmpdir, capture, addons):
    capture.CAPTURE_PATH = tmpdir / "latest_request.json"
    seen = []

    class Handler:
        def on_request(self, data):
            seen.append(data)

    addons.set_event_handler(Handler())
    try:
        addons.addons[0].request(_FakeFlow(_game_request()))
    finally:
        addons.set_event_handler(None)
    assert seen and seen[0]["body"]["type_id"] == "3", seen
    print("  PASS 捕获到请求时会回调主程序（旧版这段是死代码）")


def test_clear_capture(tmpdir, capture, addons):
    capture.CAPTURE_PATH = tmpdir / "latest_request.json"
    addons.addons[0].request(_FakeFlow(_game_request()))
    assert capture.clear_capture()["status"] == "success"
    info = capture.describe_capture()
    assert info["exists"] and info["size"] == 0 and info["replayable"] is False, info
    print("  PASS 清除捕获后回到「未捕获」状态")


def _page(next_value, records=1):
    return json.dumps({
        "code": 0,
        "msg": "ok",
        "data": {"next": next_value, "list": [{"id": i} for i in range(records)]},
    })


def test_replay_success(tmpdir, capture):
    def responder(url, params, data, headers):
        assert url.startswith("https://gf2-gacha-record.sunborngame.com/list"), url
        assert headers.get("Content-Length"), headers
        return 200, _page("" if "next" in data else "p2")

    _install_aiohttp_stub(responder)
    capture.CAPTURE_PATH = tmpdir / "latest_request.json"
    capture.save_capture({
        "url": GAME_URL,
        "headers": {"Authorization": "tok-1234", "Content-Type": "application/x-www-form-urlencoded"},
        "body": {"type_id": "3"},
        "params": {"lang": "cn"},
    })

    import backend.api.getGacha as getGacha

    outcome, logged = _capture(getGacha.get_gacha_data_all_ex)
    assert outcome["ok"] is True, outcome
    # 逐页日志必须消失，只保留每个池子一行汇总
    assert "第2页数据获取成功" not in logged, logged
    assert "第1页数据成功" not in logged, logged
    assert "角色池完成：2 页 / 2 条记录" in logged, logged
    assert set(outcome["data"]) == {
        "permanent_pool", "character_pool", "weapon_pool",
        "custom_character_pool", "custom_weapon_pool",
    }, outcome["data"]
    assert len(outcome["data"]["character_pool"]) == 2, outcome["data"]["character_pool"]
    print("  PASS 五个池子并行重放 + 分页翻页正确")


def test_replay_api_error(tmpdir, capture):
    def responder(url, params, data, headers):
        if data.get("type_id") == "3":
            return 200, json.dumps({"code": 1001, "msg": "token invalid"})
        return 200, _page("")

    _install_aiohttp_stub(responder)
    capture.CAPTURE_PATH = tmpdir / "latest_request.json"
    capture.save_capture({
        "url": GAME_URL,
        "headers": {"Authorization": "tok-1234"},
        "body": {"type_id": "3"},
        "params": {},
    })

    import backend.api.getGacha as getGacha

    outcome, logged = _capture(getGacha.get_gacha_data_all_ex)
    assert outcome["ok"] is False, outcome
    assert outcome["error"]["kind"] == "api", outcome
    assert outcome["error"]["code"] == 1001, outcome
    assert outcome["error"]["pool"] == "角色池", outcome
    assert outcome["error"]["page"] == 1, outcome
    assert "中断" in logged, logged
    print("  PASS 接口业务错误能带出 code / msg / 具体池子")


def test_replay_http_and_parse_error(tmpdir, capture):
    capture.CAPTURE_PATH = tmpdir / "latest_request.json"
    capture.save_capture({
        "url": GAME_URL,
        "headers": {"Authorization": "tok-1234"},
        "body": {"type_id": "3"},
        "params": {},
    })
    import backend.api.getGacha as getGacha

    _install_aiohttp_stub(lambda u, p, d, h: (502, "<html>bad gateway</html>"))
    outcome = getGacha.get_gacha_data_all_ex()
    assert outcome["error"]["kind"] == "http", outcome
    assert outcome["error"]["status"] == 502, outcome

    _install_aiohttp_stub(lambda u, p, d, h: (200, "<html>login</html>"))
    outcome = getGacha.get_gacha_data_all_ex()
    assert outcome["error"]["kind"] == "parse", outcome
    print("  PASS HTTP 异常 / 非 JSON 返回都能区分出来")


def test_replay_breaks_midway(tmpdir, capture):
    """翻页到一半失败：要能记录断在第几页、之前成功了几页"""

    def responder(url, params, data, headers):
        if "next" in data:
            return 502, "<html>bad gateway</html>"
        return 200, _page("p2")

    _install_aiohttp_stub(responder)
    capture.CAPTURE_PATH = tmpdir / "latest_request.json"
    capture.save_capture({
        "url": GAME_URL,
        "headers": {"Authorization": "tok-1234"},
        "body": {"type_id": "3"},
        "params": {},
    })

    import backend.api.getGacha as getGacha

    outcome, logged = _capture(getGacha.get_gacha_data_all_ex)
    assert outcome["ok"] is False, outcome
    error = outcome["error"]
    assert error["kind"] == "http", error
    assert error["page"] == 2 and error["ok_pages"] == 1, error
    assert "中断" in logged and "第 2 页" in logged, logged
    print("  PASS 翻页中途失败会记录断在第几页（第 2 页 / 已成功 1 页）")


def test_no_capture_error(tmpdir, capture):
    capture.CAPTURE_PATH = tmpdir / "latest_request.json"
    import backend.api.getGacha as getGacha

    outcome = getGacha.get_gacha_data_all_ex()
    assert outcome["ok"] is False and outcome["error"]["kind"] == "no_capture", outcome
    print("  PASS 没有捕获时重放直接给出 no_capture 原因")


def test_logging(log_dir):
    sys.path.insert(0, str(ROOT / "backend"))
    import importlib
    import backend.applog as applog

    applog = importlib.reload(applog)

    class _Sink:
        def write(self, text):
            return len(text)

        def flush(self):
            pass

    original_out, original_err = sys.stdout, sys.stderr
    sys.stdout = _Sink()
    sys.stderr = _Sink()
    try:
        log_path = applog.setup_logging(log_dir=Path(log_dir) / "logs")
        print("测试写入日志")
    finally:
        sys.stdout, sys.stderr = original_out, original_err

    assert log_path.exists(), log_path
    assert "测试写入日志" in log_path.read_text(encoding="utf-8")
    print(f"  PASS 日志写入 {log_path.name}")


def main():
    _install_mitmproxy_stub()
    sys.path.insert(0, str(ROOT / "backend"))
    import backend.capture as capture
    import backend.addons.addons as addons

    tests = [
        ("未捕获状态", test_missing_capture, (capture,)),
        ("addon 抓包", test_addon_saves_urlencoded, (capture, addons)),
        ("不覆盖已有捕获", test_unrelated_request_does_not_overwrite, (capture, addons)),
        ("JSON 请求体", test_addon_parses_json_body, (capture, addons)),
        ("捕获回调", test_addon_notifies_handler, (capture, addons)),
        ("清除捕获", test_clear_capture, (capture, addons)),
        ("重放成功", test_replay_success, (capture,)),
        ("重放业务错误", test_replay_api_error, (capture,)),
        ("重放 HTTP/格式错误", test_replay_http_and_parse_error, (capture,)),
        ("翻页中途中断", test_replay_breaks_midway, (capture,)),
        ("无捕获时重放", test_no_capture_error, (capture,)),
    ]

    failures = []
    for name, func, extra in tests:
        with tempfile.TemporaryDirectory() as tmp:
            print(f"[测试] {name}")
            try:
                func(Path(tmp), *extra)
            except AssertionError as exc:
                failures.append(name)
                print(f"  FAIL {exc}")
            except Exception as exc:  # noqa: BLE001
                import traceback
                failures.append(name)
                traceback.print_exc()

    # 日志文件句柄会一直开到进程结束，所以这里用不自动清理的目录
    log_root = tempfile.mkdtemp(prefix="xkl_logs_")
    print("[测试] 日志落盘")
    try:
        test_logging(log_root)
    except AssertionError as exc:
        failures.append("日志落盘")
        print(f"  FAIL {exc}")

    print("=" * 60)
    if failures:
        print(f"失败 {len(failures)} 项: {failures}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
