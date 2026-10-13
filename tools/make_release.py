#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""发布助手：把构建产物打成发布包，并生成带 sha256 的 version.json

为什么需要它：客户端现在会校验 sha256，如果发布时忘了更新 version.json 里的
sha256，所有用户的自动更新都会失败；手工算 hash 又容易出错，所以做成一条命令。

用法（在仓库根目录执行）：
    python tools/make_release.py --version 1.1.5
    python tools/make_release.py --version 1.1.5 --notes "新增分享多选；修复日志噪声"

默认：
    源目录   dist/gf2gacha_XKL        （PyInstaller 的 COLLECT 输出）
    输出目录 release/                 （把这两个文件传到 R2 即可）

产出：
    release/gf2gacha_XKL.zip          发布包（内部顶层目录为 gf2gacha_XKL/）
    release/version.json              客户端"检查更新"读的文件，含 sha256 / size

上传顺序很重要：**先传 zip，最后传 version.json**。
否则用户在 zip 还没上传完时就会读到新版本号，下载 404 / 校验失败。
"""
import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(msg: str):
    print(f"[FAIL] {msg}")
    sys.exit(1)


def relocate_updater(source: Path):
    """确保 updater.exe 在包顶层

    更新器必须放在被替换的目录之外（也就是包顶层），否则它自己就锁着
    _internal，没法原子替换这个目录。不同 PyInstaller 版本放置位置不同：
      * 放进 _internal 的  -> 挪到顶层
      * 放在 dist\ 根目录的 -> 复制进包顶层
    """
    root_updater = source / "updater.exe"
    internal_updater = source / "_internal" / "updater.exe"
    sibling_updater = source.parent / "updater.exe"

    if internal_updater.exists() and not root_updater.exists():
        shutil.move(str(internal_updater), str(root_updater))
        print("[OK] 已把 updater.exe 从 _internal 移到包顶层（否则更新时无法原子替换 _internal）")
    elif not root_updater.exists() and sibling_updater.exists() and sibling_updater != root_updater:
        shutil.copy2(str(sibling_updater), str(root_updater))
        print("[OK] 已把 dist\\updater.exe 复制进包顶层（更新器必须在包顶层）")


def check_payload(source: Path, version: str):
    """发布前自检：漏构建前端 / updater 放错位置，都在这里拦下来"""
    problems = []
    exe = source / "gf2gacha_XKL.exe"
    if not exe.exists():
        problems.append("缺少 gf2gacha_XKL.exe（还没构建？）")
    elif exe.stat().st_size < 5 * 1024 * 1024:
        problems.append(f"gf2gacha_XKL.exe 只有 {exe.stat().st_size} 字节，构建不完整")

    internal = source / "_internal"
    if not (internal / "frontend" / "dist" / "index.html").exists():
        problems.append("缺少 _internal/frontend/dist/index.html —— 前端没构建（先 cd frontend && npm run build）")
    backend_dir = internal / "backend"
    if not backend_dir.is_dir() or not list(backend_dir.glob("*.py")):
        problems.append("缺少 _internal/backend/*.py")

    if not (source / "updater.exe").exists():
        if (internal / "updater.exe").exists():
            problems.append("updater.exe 被放进了 _internal —— 必须放在包顶层（否则更新时无法原子替换 _internal）")
        else:
            problems.append("缺少 updater.exe")

    built_version = None
    version_file = internal / "version.json"
    if version_file.exists():
        try:
            built_version = json.loads(version_file.read_text(encoding="utf-8")).get("current_version")
        except Exception as exc:
            problems.append(f"_internal/version.json 解析失败: {exc}")
    else:
        problems.append("缺少 _internal/version.json")

    if built_version and version and built_version != version:
        problems.append(f"构建产物的版本是 {built_version}，但命令行传的是 {version}（先改 version.json 再构建）")

    if problems:
        print("[FAIL] 发布前自检没通过：")
        for item in problems:
            print(f"       - {item}")
        sys.exit(1)


def make_zip(source: Path, zip_path: Path) -> tuple[int, str]:
    if zip_path.exists():
        zip_path.unlink()
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                # 顶层目录名固定为 gf2gacha_XKL（更新器按这个名字找包根）
                zf.write(path, Path("gf2gacha_XKL") / path.relative_to(source))
                count += 1
    size = zip_path.stat().st_size
    digest = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    print(f"[OK] 打包 {count} 个文件 -> {zip_path} ({size / 1024 / 1024:.1f} MB)")
    return size, digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="gf2gacha_XKL 发布助手")
    parser.add_argument("--version", required=True, help="要发布的版本号，例如 1.1.5")
    parser.add_argument("--dist", default=str(ROOT / "dist" / "gf2gacha_XKL"), help="构建产物目录")
    parser.add_argument("--out", default=str(ROOT / "release"), help="输出目录")
    parser.add_argument("--notes", default="", help="更新说明（会写进 version.json 的 update_info，客户端弹窗里展示）")
    args = parser.parse_args()

    source = Path(args.dist)
    if not source.is_dir():
        fail(f"找不到构建产物目录: {source}")

    print(f"[1/3] 自检构建产物: {source}")
    relocate_updater(source)
    check_payload(source, args.version)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[2/3] 打包并计算 sha256 ...")
    size, sha256 = make_zip(source, out_dir / "gf2gacha_XKL.zip")

    print("[3/3] 生成 version.json ...")
    base = {"version_url": "", "download_url": "https://r2.gf2gacha-xkl.uk/gf2gacha_XKL.zip"}
    built_version_file = source / "_internal" / "version.json"
    if built_version_file.exists():
        try:
            base.update(json.loads(built_version_file.read_text(encoding="utf-8")))
        except Exception:
            pass
    remote = {
        "current_version": args.version,
        "version_url": base.get("version_url") or "https://r2.gf2gacha-xkl.uk/version.json",
        "download_url": base.get("download_url") or "https://r2.gf2gacha-xkl.uk/gf2gacha_XKL.zip",
        "sha256": sha256,
        "size": size,
    }
    if args.notes:
        remote["update_info"] = args.notes
    (out_dir / "version.json").write_text(json.dumps(remote, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n完成，待上传文件：")
    print(f"  {out_dir / 'gf2gacha_XKL.zip'}")
    print(f"  {out_dir / 'version.json'}")
    print(f"\n  sha256 = {sha256}")
    print(f"  size   = {size} 字节")
    print("\n上传顺序：先传 zip，最后传 version.json（否则用户可能读到新版本号却下不到包）")


if __name__ == "__main__":
    main()
