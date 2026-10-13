#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""main.py 冒烟测试：不需要显示器 / 不需要装 pywebview

开发机上往往没装 pywebview（那是给打包环境用的），所以这里把 webview 换成 stub，
只验证我们自己新写的逻辑：日志初始化、未捕获时的错误码、错误提示措辞、
状态接口在依赖缺失时不会抛异常。

运行：python test_main_smoke.py
"""
import json
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ---- 用 stub 顶掉 pywebview（main.py 顶层就 import 它）----
if "webview" not in sys.modules:
    webview = types.ModuleType("webview")
    webview.create_window = lambda *a, **k: None
    webview.start = lambda *a, **k: None
    sys.modules["webview"] = webview

# ---- 没有 mitmproxy 时 backend.proxy 也 import 不了，一并 stub ----
if "backend.proxy" not in sys.modules:
    try:
        import mitmproxy  # noqa: F401
    except ImportError:
        proxy_stub = types.ModuleType("backend.proxy")
        proxy_stub.actual_port = None
        proxy_stub.set_proxy = lambda *a, **k: None
        proxy_stub.close_proxy = lambda *a, **k: None
        proxy_stub.get_proxy_status = lambda: {"port": None, "ready": False, "error": "stub"}
        proxy_stub.run_proxy = lambda *a, **k: None
        sys.modules["backend.proxy"] = proxy_stub


def test_logging(log_dir, failures):
    """日志：正常落盘 + 噪声过滤 + 重复合并 + 超长截断"""
    import importlib

    import backend.applog as applog

    applog = importlib.reload(applog)

    class _Sink:
        def write(self, text):
            return len(text)

        def flush(self):
            pass

    def check(label, condition, detail=""):
        if condition:
            print(f"  PASS {label}")
        else:
            failures.append(label)
            print(f"  FAIL {label} {detail}")

    original_out, original_err = sys.stdout, sys.stderr
    sys.stdout = _Sink()
    sys.stderr = _Sink()
    try:
        log_path = applog.setup_logging(log_dir=Path(log_dir) / "logs")
        print("测试写入日志")
        # 用户抱怨的噪声：mitmproxy 连接日志 / flow 行 / pywebview 反射告警
        print("server connect config.edge.skype.com:443 (52.123.254.209:443)")
        print("client connect 127.0.0.1:5000")
        print("GET https://example.com/ HTTP/2")
        print("Error while processing window.native.ControlCollection.__abstractmethods__: __abstractmethods__")
        print("[pywebview] Error while processing window.native.X.Empty.Empty.Empty.Empty.Empty.__abstractmethods__")
        # 重复行与超长行
        for _ in range(5):
            print("[INFO] 周期性心跳")
        print("[INFO] 超长行 " + "x" * 3000)
    finally:
        sys.stdout, sys.stderr = original_out, original_err
        applog._sink.flush()

    content = log_path.read_text(encoding="utf-8")

    check("日志文件已创建", log_path.exists(), log_path)
    check("正常日志写入", "测试写入日志" in content)
    check("过滤 mitmproxy 连接日志", "server connect" not in content)
    check("过滤 client connect", "client connect" not in content)
    check("过滤 mitmproxy flow 行", "GET https://example.com" not in content)
    check("过滤 pywebview 反射告警", "Error while processing" not in content)
    check(
        "重复行合并为一条",
        content.count("[INFO] 周期性心跳") == 1 and "上一行重复 4 次" in content,
        f"出现 {content.count('[INFO] 周期性心跳')} 次",
    )
    check("超长行被截断", "已截断" in content and "x" * 1500 not in content)
    check("有过滤数量汇报", "已过滤" in content)
    check("文件体积可控", log_path.stat().st_size < 5000, log_path.stat().st_size)


def main():
    import main as main_module

    failures = []

    def check(label, condition, detail=""):
        if condition:
            print(f"  PASS {label}")
        else:
            failures.append(label)
            print(f"  FAIL {label} {detail}")

    print("[测试] 模块导入与日志初始化")
    log_path = main_module._init_logging()
    check("_init_logging 返回路径", isinstance(log_path, Path), log_path)
    check("日志文件已创建", Path(log_path).exists(), log_path)

    print("[测试] 单实例检查")
    first = main_module.check_single_instance()
    second = main_module.check_single_instance()
    check("同一进程内重复调用不再误判", second is True, second)
    print(f"  INFO 首次调用返回 {first}（False 表示本机确实已有另一个实例在运行，属正常）")

    print("[测试] 未捕获时的错误码")
    app = main_module.GachaApp()
    with tempfile.TemporaryDirectory() as tmp:
        import backend.capture as capture
        original = capture.CAPTURE_PATH
        capture.CAPTURE_PATH = Path(tmp) / "latest_request.json"
        try:
            res = app.get_gacha()
            check("status=error", res["status"] == "error", res)
            check("code=no_capture", res.get("code") == "no_capture", res)
            check("提示里包含操作引导（招募 · 访问详情）", "招募 · 访问详情" in res["msg"], res["msg"])
            check("不返回成功数据", "data" not in res, res)

            # 有一份可重放捕获时，错误提示要按失败类型给出对应建议
            capture.save_capture({
                "headers": {"Authorization": "tok"},
                "body": {"type_id": "3"},
                "params": {},
            })
            info = capture.describe_capture()
            check("可重放判定", info["replayable"] is True, info)

            hint = app._describe_replay_error({"kind": "api", "msg": "接口返回 code=1001", "pool": "角色池"}, info)
            check("api 错误提示含池子名", "角色池" in hint, hint)
            check("api 错误提示提醒刷新 token", "Authorization" in hint or "token" in hint, hint)

            hint = app._describe_replay_error({"kind": "network", "msg": "请求失败: timeout"}, info)
            check("network 错误提示提到网络", "网络" in hint, hint)

            hint = app._describe_replay_error(
                {"kind": "http", "msg": "服务器返回 HTTP 502", "pool": "角色池", "page": 128, "ok_pages": 127},
                info,
            )
            check("错误提示带中断页", "第 128 页" in hint and "127" in hint, hint)

            status = app.get_capture_status()
            check("状态接口 status=success", status["status"] == "success", status)
            check("状态里带捕获信息", "replayable" in status["capture"], status["capture"])
            check("状态里带日志路径", str(status["log_path"]).endswith("app.log"), status["log_path"])
        finally:
            capture.CAPTURE_PATH = original

    print("[测试] 五星数据来源（决定提示颜色）")
    import backend.ssr_parser as ssr_parser

    fake_proto = {"version": "local-proto", "SSR_character": {"1": "甲"}, "SSR_weapon": {}, "SSR_permanent": {}}
    fake_remote = {"version": "r2", "SSR_character": {"2": "乙"}, "SSR_weapon": {}, "SSR_permanent": {}}

    with mock.patch.object(ssr_parser, "load_ssr_from_local", lambda: fake_proto):
        res = app.load_ssr_data()
        check("本地游戏数据 -> source=local-proto（绿色「正在使用最新五星数据」）",
              res["source"] == "local-proto" and res["status"] == "success", res["source"])

    with mock.patch.object(ssr_parser, "load_ssr_from_local", lambda: None), \
         mock.patch.object(main_module.GachaApp, "_fetch_remote_ssr", lambda self, timeout=5: dict(fake_remote)):
        res = app.load_ssr_data()
        check("R2 远端 -> source=remote（绿色「正在使用远端五星数据」）",
              res["source"] == "remote", res["source"])

    with mock.patch.object(ssr_parser, "load_ssr_from_local", lambda: None), \
         mock.patch.object(main_module.GachaApp, "_fetch_remote_ssr", lambda self, timeout=5: None):
        res = app.load_ssr_data()
        check("内置 json -> source=local-json（黄色「可能不是最新」）",
              res["source"] == "local-json", res["source"])

    print("[测试] 更新状态：读取 / 收尾 / 忽略")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "_internal" / "logs").mkdir(parents=True, exist_ok=True)
        state_file = root / "_internal" / "logs" / "update_state.json"
        os.environ["GF2XKL_APP_ROOT"] = str(root)
        try:
            check("没有状态文件时不提示", app.get_update_status()["needs_attention"] is False)

            state_file.write_text(json.dumps(
                {"phase": "switched", "from": "1.1.4", "to": "1.1.5", "error": ""}), encoding="utf-8")
            st = app.get_update_status()
            check("更新没走完时提示用户", st["needs_attention"] is True, st)
            check("带上 from/to 版本号", st["from"] == "1.1.4" and st["to"] == "1.1.5", st)

            (root / "_update_tmp").mkdir()
            (root / "_internal_old").mkdir()
            res = app.mark_update_ok()
            check("收尾后 phase=ok", main_module._read_update_state().get("phase") == "ok")
            check("残留的临时目录/回滚备份被清理",
                  not (root / "_update_tmp").exists() and not (root / "_internal_old").exists(), res)

            state_file.write_text(json.dumps({"phase": "failed", "error": "sha256 校验失败"}), encoding="utf-8")
            st = app.get_update_status()
            check("失败状态要提示", st["needs_attention"] is True, st)
            check("把原因带出来", st["error"] == "sha256 校验失败", st)
            app.dismiss_update_status()
            check("用户点过我知道了就不再提示", app.get_update_status()["needs_attention"] is False)
        finally:
            os.environ.pop("GF2XKL_APP_ROOT", None)

    print("[测试] 系统代理未就绪时不应乱设（避免用户断网）")
    with mock.patch.object(main_module.GachaApp, "start_proxy", lambda self: False):
        ok = app.enable_system_proxy()
        check("代理未就绪时返回 False", ok is False, ok)

    # 日志文件句柄会一直开到进程结束，所以这里用不自动清理的目录
    log_root = tempfile.mkdtemp(prefix="xkl_logs_")
    print("[测试] 日志落盘与噪声过滤")
    try:
        test_logging(log_root, failures)
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
