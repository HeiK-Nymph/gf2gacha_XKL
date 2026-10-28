#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""抓包进程的崩溃看门狗入口。

与产品里 main.py --proxy-watchdog 是同一套实现（backend/proxy_watchdog.py），
只是这里用独立脚本启动，避免为了抓包去跑 main.py（main.py 会接管系统代理）。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.proxy_watchdog import run_watchdog  # noqa: E402


def main() -> int:
    if len(sys.argv) != 5:
        print("usage: watchdog_entry.py <parent_pid> <snapshot> <ready> <stop>", file=sys.stderr)
        return 2
    return run_watchdog(int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4])


if __name__ == "__main__":
    raise SystemExit(main())
