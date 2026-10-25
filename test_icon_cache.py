#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""icon_cache 单元测试：内存命中 / 磁盘命中 / TTL 过期 / 下载失败 / 预热统计

不联网：把 requests.Session 换成假的。
运行：python test_icon_cache.py
"""
import json
import os
import sys
import tempfile
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import backend.icon_cache as icon_cache  # noqa: E402


class _FakeResponse:
    def __init__(self, status=200, content=b"\x89PNG\r\n\x1a\n", headers=None):
        self.status_code = status
        self.content = content
        self.headers = headers or {"Content-Type": "image/png", "Cache-Control": "max-age=86400"}


class _FakeSession:
    def __init__(self, response=None, fail=False):
        self.calls = 0
        self.response = response or _FakeResponse()
        self.fail = fail

    def get(self, url, timeout=None, verify=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError("network down")
        return self.response


def _reset(tmpdir, session):
    icon_cache.CACHE_ROOT = Path(tmpdir) / "icons"
    icon_cache._mem.clear()
    icon_cache._session = session


def check(label, condition, detail=""):
    if condition:
        print(f"  PASS {label}")
        return 0
    print(f"  FAIL {label} {detail}")
    return 1


def main():
    failures = 0
    url = "https://static.gf2gacha-xkl.uk/images/character/1015.png"

    with tempfile.TemporaryDirectory() as tmp:
        print("[测试] 首次下载 + 内存命中")
        session = _FakeSession()
        _reset(tmp, session)
        first = icon_cache.get_data_uri(url)
        failures += check("首次能取到 data URI", bool(first and first.startswith("data:image/png;base64,")))
        second = icon_cache.get_data_uri(url)
        failures += check("第二次命中内存（不再请求）", session.calls == 1, f"calls={session.calls}")
        failures += check("两次结果一致", first == second)
        failures += check("is_cached 为真", icon_cache.is_cached(url) is True)

        print("[测试] 跨进程：内存清空后命中磁盘")
        session2 = _FakeSession()
        icon_cache._mem.clear()
        icon_cache._session = session2
        third = icon_cache.get_data_uri(url)
        failures += check("磁盘命中（0 次网络请求）", session2.calls == 0, f"calls={session2.calls}")
        failures += check("磁盘结果与内存一致", third == first)

        print("[测试] TTL 过期后重新下载")
        meta_path = next(Path(icon_cache.CACHE_ROOT).glob("*.json"))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["ts"] = time.time() - 10 * 24 * 3600      # 10 天前
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        session3 = _FakeSession()
        icon_cache._mem.clear()
        icon_cache._session = session3
        icon_cache.get_data_uri(url)
        failures += check("过期后触发下载", session3.calls == 1, f"calls={session3.calls}")

        print("[测试] 下载失败时返回 None（不写坏缓存）")
        session4 = _FakeSession(fail=True)
        icon_cache._mem.clear()
        icon_cache._session = session4
        icon_cache.CACHE_ROOT = Path(tmp) / "icons2"
        failures += check("失败返回 None", icon_cache.get_data_uri(url) is None)
        failures += check("失败不产生缓存文件", not list(Path(icon_cache.CACHE_ROOT).glob("*.png")))

        print("[测试] 预热统计")
        session5 = _FakeSession()
        icon_cache.CACHE_ROOT = Path(tmp) / "icons"   # 回到已有缓存的那个目录
        icon_cache._mem.clear()                       # 清内存，验证走的是磁盘缓存
        icon_cache._session = session5
        stats = icon_cache.prefetch([url], workers=2)
        failures += check("预热统计字段齐全",
                          set(stats) >= {"total", "hit", "downloaded", "failed", "seconds"}, stats)
        failures += check("磁盘已有 -> 记为 hit（不再下载）",
                          stats["downloaded"] == 0 and stats["hit"] == 1 and session5.calls == 0, stats)

    print("[测试] 启动/退出时清理超过 24 小时的缓存")
    with tempfile.TemporaryDirectory() as tmp:
        session6 = _FakeSession()
        _reset(tmp, session6)
        expired_url = "https://static.gf2gacha-xkl.uk/images/character/expired.png"
        fresh_url = "https://static.gf2gacha-xkl.uk/images/weapon/fresh.png"
        icon_cache.get_data_uri(expired_url)
        icon_cache.get_data_uri(fresh_url)

        expired_meta = None
        for meta_path in Path(icon_cache.CACHE_ROOT).glob("*.json"):
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("url") == expired_url:
                meta["ts"] = time.time() - icon_cache.DEFAULT_TTL - 60
                meta_path.write_text(json.dumps(meta), encoding="utf-8")
                expired_meta = meta_path
                break
        failures += check("找到过期缓存元数据", expired_meta is not None)

        orphan_old = Path(icon_cache.CACHE_ROOT) / "orphan-old.png"
        orphan_fresh = Path(icon_cache.CACHE_ROOT) / "orphan-fresh.png"
        orphan_old.write_bytes(b"old")
        orphan_fresh.write_bytes(b"fresh")
        old_time = time.time() - icon_cache.DEFAULT_TTL - 60
        os.utime(orphan_old, (old_time, old_time))

        purge_stats = icon_cache.purge_expired()
        failures += check("删除过期图片、元数据和孤立旧图", purge_stats["removed"] == 3, purge_stats)
        failures += check("统计释放空间", purge_stats["freed_bytes"] > 0, purge_stats)
        failures += check("24 小时内缓存保留",
                          (Path(icon_cache.CACHE_ROOT) / f"{icon_cache._key(fresh_url)}.png").exists(),
                          purge_stats)
        failures += check("未过期孤立图片保留", orphan_fresh.exists())
        failures += check("过期 URL 移出内存", expired_url not in icon_cache._mem)
        failures += check("新鲜 URL 仍在内存", fresh_url in icon_cache._mem)

    print("=" * 60)
    if failures:
        print(f"失败 {failures} 项")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
