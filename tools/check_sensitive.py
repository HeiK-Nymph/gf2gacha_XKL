#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""发布前敏感信息扫描（git 跟踪范围内的文件）。

为什么需要它：`json/latest_request.json` 抓包后会带 `Authorization`（游戏 access_token），
测试时还可能在源码或文档里留下真实 JWT、手机号、API key。发布前统一扫一遍，
发现问题直接非 0 退出，避免把用户凭证带进 git / GitHub。

用法：
    python tools/check_sensitive.py          # 扫描 git 已跟踪文件
    python tools/check_sensitive.py --all    # 连同未跟踪的普通文件一起扫（排除 .gitignore 命中的）
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 阻断级：出现即失败
BLOCKING = [
    ("JWT", re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("私钥", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("OpenAI/SK key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("AWS key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("游戏 Authorization 字段", re.compile(r'"Authorization"\s*:\s*"[^"]{20,}"')),
    ("access_token 字段", re.compile(r'"access_token"\s*:\s*"[^"]{20,}"')),
]

# 提醒级：只提示不拦截（示例号码、文档里的占位号很常见）
WARN = [
    ("手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
]

TEXT_SUFFIXES = {
    ".py", ".kt", ".java", ".js", ".ts", ".vue", ".json", ".md", ".txt", ".xml",
    ".yml", ".yaml", ".html", ".css", ".bat", ".ps1", ".mjs", ".cjs", ".gradle", ".kts",
}

# 文档/注释里的占位符不算泄露（例如 "access_token":"<base64 payload>.签名"）
PLACEHOLDER_HINTS = ("<", ">", "…", "...", "xxx", "xxx", "****", "your_", "placeholder", "示例", "占位")

MAX_BYTES = 2 * 1024 * 1024


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(hint in lowered for hint in PLACEHOLDER_HINTS)


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout
    return [ROOT / name for name in out.decode("utf-8", "replace").split("\0") if name]


def untracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-o", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    return [ROOT / name for name in out.decode("utf-8", "replace").split("\0") if name]


def scan(paths: list[Path]) -> tuple[list[str], list[str]]:
    blocking_hits: list[str] = []
    warn_hits: list[str] = []
    for path in paths:
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(ROOT)
        for line_no, line in enumerate(text.splitlines(), 1):
            for label, pattern in BLOCKING:
                match = pattern.search(line)
                if not match:
                    continue
                if _is_placeholder(match.group(0)):
                    break
                blocking_hits.append(f"{rel}:{line_no}  [{label}]  {line.strip()[:120]}")
                break
            else:
                for label, pattern in WARN:
                    if pattern.search(line):
                        warn_hits.append(f"{rel}:{line_no}  [{label}]  {line.strip()[:120]}")
                        break
    return blocking_hits, warn_hits


def main() -> int:
    parser = argparse.ArgumentParser(description="发布前敏感信息扫描")
    parser.add_argument("--all", action="store_true", help="同时扫描未跟踪文件")
    args = parser.parse_args()

    paths = tracked_files()
    if args.all:
        paths += untracked_files()

    blocking, warn = scan(paths)

    print(f"扫描 {len(paths)} 个文件")
    if warn:
        print(f"\n[提醒] {len(warn)} 处疑似手机号（示例/占位可忽略）：")
        for item in warn[:10]:
            print("  " + item)
        if len(warn) > 10:
            print(f"  ... 共 {len(warn)} 处")

    if blocking:
        print(f"\n[FAIL] 发现 {len(blocking)} 处真实凭证/密钥，发布中止：")
        for item in blocking[:20]:
            print("  " + item)
        if len(blocking) > 20:
            print(f"  ... 共 {len(blocking)} 处")
        print("\n处理办法：从文件里删掉、或把该文件加进 .gitignore 并 git rm --cached。")
        return 1

    print("\n[OK] 未发现凭证/密钥")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
