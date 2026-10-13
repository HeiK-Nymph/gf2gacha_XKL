#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""更新器演练测试（本地模拟，不碰线上、不碰真实安装目录）

做法：
  * 用合成包（几百 KB，不是真的 80MB）当"新版本"，打成 zip 用本地 HTTP 服务器发出去；
  * 造一个假的安装目录（含 records/certs/logs/旧版本文件）；
  * 以子进程方式运行真实的 updater.py，把 GF2XKL_APP_ROOT 指向假安装目录；
  * 逐场景断言：安装目录有没有被误改、状态文件写了什么、日志里有没有证据。

覆盖场景：
  1. 正常更新（sha256/size 都对）
  2. sha256 不匹配            -> 必须拒绝，且安装目录一字不动
  3. 包结构不合格（缺前端）    -> 必须拒绝，且安装目录一字不动
  4. 包内版本与远端声明不一致  -> 必须拒绝
  5. 下载 404                 -> 必须失败且不动安装目录
  6. 远端没给 sha256          -> 打警告但继续（过渡期兼容）
  7. 用户数据保留             -> records / certs / logs 更新后仍在

运行：python test_updater_flow.py
"""
import hashlib
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UPDATER = ROOT / "updater.py"
NEW_VERSION = "1.9.9"
OLD_VERSION = "1.0.0"

failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  PASS {label}")
    else:
        failures.append(label)
        print(f"  FAIL {label} {detail}")


def write(path: Path, text: str = "x", size: int = 0):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (text * (size // len(text) + 1)).encode("utf-8")[:size] if size else text.encode("utf-8")
    path.write_bytes(data)


def build_package(tmp: Path, version=NEW_VERSION, with_frontend=True) -> Path:
    pkg = tmp / "pkg" / "gf2gacha_XKL"
    if pkg.exists():
        shutil.rmtree(pkg)
    write(pkg / "gf2gacha_XKL.exe", "MZ", 5 * 1024 * 1024)
    write(pkg / "updater.exe", "MZ", 1024)                       # 新布局：顶层
    write(pkg / "_internal" / "version.json", json.dumps(
        {"current_version": version, "version_url": "http://127.0.0.1/version.json",
         "download_url": "http://127.0.0.1/gf2gacha_XKL.zip"}))
    write(pkg / "_internal" / "backend" / "proxy.py", "print('new backend')")
    write(pkg / "_internal" / "python311.dll", "dll")
    write(pkg / "_internal" / "base_library.zip", "zip")
    write(pkg / "_internal" / "marker_new.txt", "新版本文件")
    if with_frontend:
        write(pkg / "_internal" / "frontend" / "dist" / "index.html", "<html>new</html>")
    return pkg


def make_zip(pkg: Path, zip_path: Path):
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(pkg.rglob("*")):
            if path.is_file():
                zf.write(path, Path("gf2gacha_XKL") / path.relative_to(pkg))
    return zip_path


def build_install(tmp: Path) -> Path:
    install = tmp / "install"
    if install.exists():
        shutil.rmtree(install)
    write(install / "gf2gacha_XKL.exe", "MZ", 5 * 1024 * 1024)
    write(install / "_internal" / "version.json", json.dumps(
        {"current_version": OLD_VERSION, "version_url": "http://127.0.0.1/version.json",
         "download_url": "http://127.0.0.1/gf2gacha_XKL.zip"}))
    write(install / "_internal" / "backend" / "proxy.py", "print('old backend')")
    write(install / "_internal" / "records" / "test.json", '{"keep": true}')
    write(install / "_internal" / "certs" / "mitmproxy-ca.pem", "cert")
    write(install / "_internal" / "logs" / "app.log", "old log line")
    write(install / "_internal" / "cache" / "icons" / "a.png", "icon")
    write(install / "_internal" / "old_only.txt", "旧版本独有文件")
    # 根目录：一个旧构建产物（应被清理）+ 一个用户自己的文件（必须保留）
    write(install / "old_stale.exe", "旧构建产物")
    write(install / "我的说明.txt", "用户自己的文件")
    return install


def write_intent(install: Path, url: str, sha256: str = "", size=None, to=NEW_VERSION):
    state = {"phase": "starting", "from": OLD_VERSION, "to": to,
             "download_url": url, "sha256": sha256, "size": size or 0, "error": ""}
    path = install / "_internal" / "logs" / "update_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def read_state(install: Path) -> dict:
    try:
        return json.loads((install / "_internal" / "logs" / "update_state.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_updater_log(install: Path) -> str:
    try:
        return (install / "_internal" / "logs" / "updater.log").read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def run_updater(install: Path, skip_launch: bool = True, extra_args=None):
    env = dict(os.environ)
    env.update({
        "GF2XKL_APP_ROOT": str(install),
        "GF2XKL_MIN_FILES": "5",
        "GF2XKL_MIN_INTERNAL_MB": "0",
        "GF2XKL_WATCHDOG_SECONDS": "8",
        "PYTHONIOENCODING": "utf-8",
    })
    if skip_launch:
        env["GF2XKL_SKIP_LAUNCH"] = "1"
    else:
        env.pop("GF2XKL_SKIP_LAUNCH", None)
    proc = subprocess.run(
        [sys.executable, str(UPDATER)] + list(extra_args or []),
        input="\n", capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(ROOT), timeout=180,
    )
    return proc


class _Server:
    """把 serve 目录用本地 HTTP 发出去"""

    def __init__(self, serve_dir: Path):
        self.dir = serve_dir
        outer = self

        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def __init__(self, *a, **k):
                super().__init__(*a, directory=str(outer.dir), **k)

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self):
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def install_snapshot(install: Path) -> dict:
    """安装目录里"业务文件"的快照，用来判断有没有被误改"""
    snap = {}
    for rel in ("_internal/version.json", "_internal/backend/proxy.py",
                "_internal/records/test.json", "_internal/certs/mitmproxy-ca.pem",
                "_internal/logs/app.log", "_internal/old_only.txt"):
        path = install / rel
        snap[rel] = path.read_text(encoding="utf-8", errors="replace") if path.exists() else None
    return snap


def test_path_detection(tmp: Path):
    """更新器在根目录 / 在 _internal 两种布局都要能认出安装根目录"""
    print("\n[场景0] 路径推断（新旧两种布局）")
    sys.path.insert(0, str(ROOT))
    import importlib

    import updater as updater_module
    updater_module = importlib.reload(updater_module)

    old_exec, old_frozen = sys.executable, getattr(sys, "frozen", None)
    old_env = os.environ.pop("GF2XKL_APP_ROOT", None)
    try:
        # 新布局：<root>/updater.exe + <root>/_internal/
        install = tmp / "layout_new"
        (install / "_internal").mkdir(parents=True, exist_ok=True)
        fake_exe = install / "updater.exe"
        fake_exe.write_bytes(b"MZ")
        sys.frozen = True                      # type: ignore[attr-defined]
        sys.executable = str(fake_exe)
        check("新布局（更新器在根目录）", updater_module.get_app_root_path() == install,
              updater_module.get_app_root_path())

        # 老布局：<root>/_internal/updater.exe
        install2 = tmp / "layout_old"
        (install2 / "_internal").mkdir(parents=True, exist_ok=True)
        fake_exe2 = install2 / "_internal" / "updater.exe"
        fake_exe2.write_bytes(b"MZ")
        sys.executable = str(fake_exe2)
        check("老布局（更新器在 _internal）", updater_module.get_app_root_path() == install2,
              updater_module.get_app_root_path())
    finally:
        sys.executable = old_exec
        if old_frozen is None:
            try:
                del sys.frozen                # type: ignore[attr-defined]
            except AttributeError:
                pass
        else:
            sys.frozen = old_frozen            # type: ignore[attr-defined]
        if old_env is not None:
            os.environ["GF2XKL_APP_ROOT"] = old_env


def main():
    tmp = Path(tempfile.mkdtemp(prefix="xkl_update_sim_"))
    test_path_detection(tmp)
    serve = tmp / "serve"
    serve.mkdir(parents=True, exist_ok=True)

    print("[准备] 构建合成包")
    pkg = build_package(tmp)
    zip_path = make_zip(pkg, serve / "gf2gacha_XKL.zip")
    data = zip_path.read_bytes()
    good_sha = hashlib.sha256(data).hexdigest()
    good_size = len(data)
    print(f"       包大小 {good_size} 字节，sha256 {good_sha[:12]}…")

    # 缺前端的坏包
    bad_pkg = build_package(tmp / "badpkg", with_frontend=False)
    bad_zip = make_zip(bad_pkg, serve / "no_frontend.zip")

    server = _Server(serve)
    try:
        # ---------------- 场景 1：正常更新 ----------------
        print("\n[场景1] 正常更新（sha256/size 都对）")
        install = build_install(tmp / "s1")
        before = install_snapshot(install)
        write_intent(install, f"{server.base}/gf2gacha_XKL.zip", good_sha, good_size)
        proc = run_updater(install)
        state = read_state(install)
        log_text = read_updater_log(install)
        new_version = json.loads((install / "_internal" / "version.json").read_text(encoding="utf-8"))["current_version"]
        check("版本已更新到 " + NEW_VERSION, new_version == NEW_VERSION, new_version)
        check("新版本文件已落地", (install / "_internal" / "marker_new.txt").exists())
        check("state = switched", state.get("phase") == "switched", state)
        check("记录了 sha256 校验通过", "sha256 校验通过" in log_text)
        check("临时目录已清理", not (install / "_update_tmp").exists())
        check("抽卡记录保留", (install / "_internal" / "records" / "test.json").read_text(encoding="utf-8") == before["_internal/records/test.json"])
        check("证书保留", (install / "_internal" / "certs" / "mitmproxy-ca.pem").exists())
        check("日志保留", (install / "_internal" / "logs" / "app.log").read_text(encoding="utf-8") == before["_internal/logs/app.log"])
        check("updater.log 已生成", "开始执行更新" in log_text)

        # ---------------- 场景 2：sha256 不匹配 ----------------
        print("\n[场景2] sha256 不匹配 -> 必须拒绝且不动安装目录")
        install = build_install(tmp / "s2")
        before = install_snapshot(install)
        write_intent(install, f"{server.base}/gf2gacha_XKL.zip", "0" * 64, good_size)
        run_updater(install)
        check("安装目录一字未改", install_snapshot(install) == before)
        check("state = failed", read_state(install).get("phase") == "failed", read_state(install))
        check("日志记录 sha256 失败", "sha256 校验失败" in read_updater_log(install))
        check("临时目录已清理", not (install / "_update_tmp").exists())

        # ---------------- 场景 3：包结构不合格 ----------------
        print("\n[场景3] 缺前端 dist 的包 -> 必须拒绝")
        install = build_install(tmp / "s3")
        before = install_snapshot(install)
        bad_data = bad_zip.read_bytes()
        write_intent(install, f"{server.base}/no_frontend.zip",
                     hashlib.sha256(bad_data).hexdigest(), len(bad_data))
        run_updater(install)
        check("安装目录一字未改", install_snapshot(install) == before)
        state = read_state(install)
        check("state = failed", state.get("phase") == "failed", state)
        check("原因里点出前端没构建", "前端没构建" in (state.get("error") or ""), state.get("error"))

        # ---------------- 场景 4：包内版本与远端不一致 ----------------
        print("\n[场景4] 包内版本与远端声明不一致 -> 必须拒绝")
        install = build_install(tmp / "s4")
        before = install_snapshot(install)
        write_intent(install, f"{server.base}/gf2gacha_XKL.zip", good_sha, good_size, to="2.0.0")
        run_updater(install)
        check("安装目录一字未改", install_snapshot(install) == before)
        check("state = failed", read_state(install).get("phase") == "failed", read_state(install))

        # ---------------- 场景 5：下载 404 ----------------
        print("\n[场景5] 下载地址 404 -> 失败但不动安装目录")
        install = build_install(tmp / "s5")
        before = install_snapshot(install)
        write_intent(install, f"{server.base}/not_exists.zip")
        run_updater(install)
        check("安装目录一字未改", install_snapshot(install) == before)
        check("state = failed", read_state(install).get("phase") == "failed", read_state(install))

        # ---------------- 场景 6：远端没给 sha256 ----------------
        print("\n[场景6] 没有 sha256（过渡期）-> 警告但继续")
        install = build_install(tmp / "s6")
        write_intent(install, f"{server.base}/gf2gacha_XKL.zip")
        run_updater(install)
        log_text = read_updater_log(install)
        new_version = json.loads((install / "_internal" / "version.json").read_text(encoding="utf-8"))["current_version"]
        check("仍然完成更新", new_version == NEW_VERSION, new_version)
        check("日志里有跳过校验的警告", "跳过完整性校验" in log_text)
        # ---------------- 场景7：原子切换 + 保留数据 + 孤儿清理 ----------------
        print("\n[场景7] 原子切换（跳过启动，只验证切换本身）")
        install = build_install(tmp / "s7")
        write_intent(install, f"{server.base}/gf2gacha_XKL.zip", good_sha, good_size)
        run_updater(install)
        if read_state(install).get("phase") == "failed":
            served = (serve / "gf2gacha_XKL.zip").read_bytes()
            print(f"    [诊断] 期望 sha={good_sha[:16]} size={good_size}")
            print(f"    [诊断] 实际 zip sha={hashlib.sha256(served).hexdigest()[:16]} size={len(served)}")
            for line in read_updater_log(install).splitlines()[-12:]:
                print("      ", line)
        log_text = read_updater_log(install)
        new_version = json.loads((install / "_internal" / "version.json").read_text(encoding="utf-8"))["current_version"]
        check("新版已就位", new_version == NEW_VERSION, new_version)
        check("回滚备份 _internal_old 存在", (install / "_internal_old").exists())
        check("旧版独有文件进了备份", (install / "_internal_old" / "old_only.txt").exists())
        check("新版独有文件在新目录", (install / "_internal" / "marker_new.txt").exists())
        check("抽卡记录被搬到新目录", (install / "_internal" / "records" / "test.json").exists()
              and (install / "_internal" / "records" / "test.json").read_text(encoding="utf-8") == '{"keep": true}')
        check("证书被搬到新目录", (install / "_internal" / "certs" / "mitmproxy-ca.pem").exists())
        check("日志被搬到新目录", (install / "_internal" / "logs" / "app.log").read_text(encoding="utf-8") == "old log line")
        check("图标缓存被搬到新目录", (install / "_internal" / "cache" / "icons" / "a.png").exists())
        check("state = switched", read_state(install).get("phase") == "switched", read_state(install))
        check("根目录旧构建产物被清理", not (install / "old_stale.exe").exists())
        check("用户自己的文件保留", (install / "我的说明.txt").exists())
        check("日志里说明了清理动作", "已清理根目录里新包不需要的旧文件" in log_text)
        check("临时目录已清理", not (install / "_update_tmp").exists())

        # ---------------- 场景8：看门狗自动回滚（新版启动失败） ----------------
        print("\n[场景8] 新版启动失败 -> 看门狗自动回滚")
        install = build_install(tmp / "s8")
        write_intent(install, f"{server.base}/gf2gacha_XKL.zip", good_sha, good_size)
        run_updater(install, skip_launch=False)   # 让 updater 真的去启动（dummy exe 会启动失败）
        state = read_state(install)
        check("已回到旧版本", json.loads((install / "_internal" / "version.json").read_text(encoding="utf-8"))["current_version"] == OLD_VERSION)
        check("state = rolled_back", state.get("phase") == "rolled_back", state)
        check("回滚备份已用掉", not (install / "_internal_old").exists())
        check("没有留下 broken 目录", not (install / "_internal_broken").exists())
        check("用户数据仍在", (install / "_internal" / "records" / "test.json").exists())
        check("旧版独有文件回来了", (install / "_internal" / "old_only.txt").exists())
        check("日志记录了自动回滚", "自动回滚" in read_updater_log(install))

        # ---------------- 场景9：--rollback 显式回滚 ----------------
        print("\n[场景9] updater --rollback 显式回滚")
        install = build_install(tmp / "s9")
        write_intent(install, f"{server.base}/gf2gacha_XKL.zip", good_sha, good_size)
        run_updater(install)                      # 先切到新版（state=switched，备份还在）
        check("先切到新版", json.loads((install / "_internal" / "version.json").read_text(encoding="utf-8"))["current_version"] == NEW_VERSION)
        run_updater(install, extra_args=["--rollback", "--reason", "演练手动回滚"])
        state = read_state(install)
        check("回到旧版本", json.loads((install / "_internal" / "version.json").read_text(encoding="utf-8"))["current_version"] == OLD_VERSION)
        check("state = rolled_back", state.get("phase") == "rolled_back", state)
        check("记录回滚原因", "演练手动回滚" in (state.get("error") or ""), state.get("error"))
        check("用户数据仍在", (install / "_internal" / "records" / "test.json").exists())

        # ---------------- 场景10：看门狗判定（纯函数） ----------------
        print("\n[场景10] 看门狗判定逻辑")
        import importlib

        import updater as up
        up = importlib.reload(up)
        check("写了 ok -> 成功", up.watchdog_should_rollback("ok", True, 1, 90) == "ok")
        check("进程已退出 -> 回滚", up.watchdog_should_rollback("switched", False, 1, 90).startswith("rollback:"))
        check("超时未 ok -> 回滚", up.watchdog_should_rollback("switched", True, 100, 90).startswith("rollback:"))
        check("还在等 -> 不回滚", up.watchdog_should_rollback("switched", True, 5, 90) == "")

    finally:
        server.stop()
        shutil.rmtree(tmp, ignore_errors=True)

    print("=" * 60)
    if failures:
        print(f"失败 {len(failures)} 项: {failures}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
