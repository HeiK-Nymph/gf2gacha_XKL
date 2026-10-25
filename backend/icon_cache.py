#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""五星图标的内存 + 磁盘缓存（分享截图用）

为什么必须要 Python 下载图标：
    图床 static.gf2gacha-xkl.uk **不带 CORS 响应头**，所以页面里的 <img> 不能
    直接画进 canvas（会污染画布，toBlob 直接抛 SecurityError），html2canvas 只能
    处理同源的 data URI。这就是分享前必须把每张图标转成 base64 的原因，
    「直接用浏览器已经加载好的图」这条路走不通。

那为什么慢：每分享一次都要重新下载一百多张（实测单张 1.6s 左右，TLS 握手占大头），
而且 Python 的 requests 完全绕过浏览器缓存。所以这里做两层缓存：

    1. 内存缓存：同一次运行里同一 URL 只读一次；
    2. 磁盘缓存：<程序目录>/cache/icons/，下次启动也直接命中；
    3. TTL 跟随响应里的 Cache-Control max-age，统一限制为最多 24 小时。

另外所有请求都关掉 trust_env：本工具会把系统代理指向自己的 mitmproxy，而
requests 会读 Windows 注册表代理，不关的话自己的图片下载会绕经自己的代理，
既慢（多层加解密）又依赖代理进程活着。
"""
from __future__ import annotations

import base64
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha1
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

CACHE_ROOT = Path(__file__).resolve().parent.parent / "cache" / "icons"
DEFAULT_TTL = 24 * 3600          # 角色/武器图标默认缓存 24 小时
MAX_TTL = 24 * 3600              # 强制最多缓存 24 小时

_mem: dict[str, str] = {}
_lock = threading.Lock()
_session = None
_session_lock = threading.Lock()


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                s = requests.Session()
                s.trust_env = False          # 不要走系统/注册表代理（见模块说明）
                adapter = HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=1)
                s.mount("https://", adapter)
                s.mount("http://", adapter)
                _session = s
    return _session


def _key(url: str) -> str:
    return sha1(url.encode("utf-8")).hexdigest()


def _paths(url: str):
    key = _key(url)
    return CACHE_ROOT / f"{key}.png", CACHE_ROOT / f"{key}.json"


def _read_disk(url: str) -> str | None:
    data_path, meta_path = _paths(url)
    try:
        if not data_path.exists() or not meta_path.exists():
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        age = time.time() - float(meta.get("ts", 0))
        ttl = min(float(meta.get("ttl", DEFAULT_TTL)), MAX_TTL)
        if age > ttl:
            return None
        raw = data_path.read_bytes()
        if not raw:
            return None
        content_type = meta.get("content_type") or "image/png"
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:{content_type};base64,{b64}"
    except Exception as exc:
        print(f"[icon-cache] 读缓存失败 {url}: {exc}")
        return None


def _write_disk(url: str, raw: bytes, content_type: str, ttl: float):
    data_path, meta_path = _paths(url)
    try:
        CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        tmp = data_path.with_suffix(".tmp")
        tmp.write_bytes(raw)
        os.replace(tmp, data_path)
        meta_path.write_text(
            json.dumps({"url": url, "ts": time.time(), "ttl": ttl, "content_type": content_type}),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[icon-cache] 写缓存失败 {url}: {exc}")


def _parse_ttl(response) -> float:
    raw = (response.headers.get("Cache-Control") or "").lower()
    for part in raw.split(","):
        part = part.strip()
        if part.startswith("max-age="):
            try:
                return float(part.split("=", 1)[1])
            except ValueError:
                break
    return DEFAULT_TTL


def is_cached(url: str) -> bool:
    """只查缓存、不下载（用于统计命中率）"""
    if not url or url.startswith("data:"):
        return True
    with _lock:
        if url in _mem:
            return True
    return _read_disk(url) is not None


def get_data_uri(url: str, *, download: bool = True) -> str | None:
    """拿到图标的 data URI（内存 → 磁盘 → 网络，命中就返回）"""
    if not url or url.startswith("data:"):
        return url or None

    with _lock:
        cached = _mem.get(url)
    if cached:
        return cached

    cached = _read_disk(url)
    if cached:
        with _lock:
            _mem[url] = cached
        return cached

    if not download:
        return None

    try:
        response = _get_session().get(url, timeout=20, verify=False)
        if response.status_code != 200 or not response.content:
            print(f"[icon-cache] 下载失败 HTTP {response.status_code}: {url}")
            return None
        content_type = response.headers.get("Content-Type", "image/png")
        if "image" not in content_type:
            content_type = "image/png"
        ttl = _parse_ttl(response)
        _write_disk(url, response.content, content_type, ttl)
        b64 = base64.b64encode(response.content).decode("ascii")
        data_uri = f"data:{content_type};base64,{b64}"
        with _lock:
            _mem[url] = data_uri
        return data_uri
    except Exception as exc:
        print(f"[icon-cache] 下载异常 {url}: {exc}")
        return None


def prefetch(urls, workers: int = 8) -> dict:
    """预热缓存（在后台线程里调用），返回统计信息

    返回 {"total": n, "hit": 命中, "downloaded": 新下载, "failed": 失败, "seconds": 用时}
    """
    unique = [u for u in dict.fromkeys(urls) if u and not u.startswith("data:")]
    if not unique:
        return {"total": 0, "hit": 0, "downloaded": 0, "failed": 0, "seconds": 0.0}

    started = time.time()
    hit = 0
    downloaded = 0
    failed = 0

    def load(url: str):
        with _lock:
            if url in _mem:
                return "hit"
        if _read_disk(url):
            return "hit"
        return "ok" if get_data_uri(url) else "fail"

    workers = max(1, min(workers, len(unique)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for result in executor.map(load, unique):
            if result == "hit":
                hit += 1
            elif result == "ok":
                downloaded += 1
            else:
                failed += 1

    stats = {
        "total": len(unique),
        "hit": hit,
        "downloaded": downloaded,
        "failed": failed,
        "seconds": round(time.time() - started, 2),
    }
    print(f"[icon-cache] 预热完成: {stats}")
    return stats


def get_data_uris(urls, workers: int = 8) -> dict[str, str]:
    """批量取得图标 data URI（用于主页/分享图，磁盘命中时无需联网）。"""
    unique = [u for u in dict.fromkeys(urls) if isinstance(u, str) and u.startswith("http")]
    unique = unique[:500]
    if not unique:
        return {}
    prefetch(unique, workers=workers)
    result = {}
    for url in unique:
        data_uri = get_data_uri(url, download=False)
        if data_uri:
            result[url] = data_uri
    return result

def purge_expired(max_age_seconds: float = DEFAULT_TTL) -> dict:
    """删除超过有效期的磁盘缓存，返回清理统计。

    只处理缓存目录中的图片及其元数据：
    - 有元数据时以写入时间为准；
    - 元数据缺失或损坏时以文件修改时间为准；
    - 清理失败只记录，不影响程序退出或启动。
    """
    started = time.time()
    stats = {"removed": 0, "freed_bytes": 0, "failed": 0, "seconds": 0.0}
    if not CACHE_ROOT.exists():
        return stats

    try:
        max_age = max(0.0, float(max_age_seconds))
    except (TypeError, ValueError):
        max_age = float(DEFAULT_TTL)
    now = time.time()
    paths: set[Path] = set()
    expired_urls: set[str] = set()

    def is_expired(path: Path) -> bool:
        try:
            return now - path.stat().st_mtime > max_age
        except OSError:
            return False

    meta_paths = set(CACHE_ROOT.glob("*.json"))
    for meta_path in meta_paths:
        data_path = meta_path.with_suffix(".png")
        meta = {}
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass

        try:
            timestamp = float(meta.get("ts", 0))
        except (TypeError, ValueError, AttributeError):
            timestamp = 0
        try:
            if timestamp <= 0:
                timestamp = data_path.stat().st_mtime if data_path.exists() else meta_path.stat().st_mtime
        except OSError:
            continue

        if now - timestamp <= max_age:
            continue
        paths.add(meta_path)
        if data_path.exists():
            paths.add(data_path)
        if isinstance(meta, dict) and isinstance(meta.get("url"), str):
            expired_urls.add(meta["url"])

    # 清理没有元数据的孤立图片；它们无法再被命中，只会占用磁盘。
    for data_path in CACHE_ROOT.glob("*.png"):
        if data_path.with_suffix(".json") not in meta_paths:
            if is_expired(data_path):
                paths.add(data_path)

    for path in paths:
        try:
            size = path.stat().st_size
            path.unlink()
            stats["removed"] += 1
            stats["freed_bytes"] += size
        except FileNotFoundError:
            continue
        except OSError as exc:
            stats["failed"] += 1
            print(f"[icon-cache] 清理失败 {path.name}: {exc}")

    if expired_urls:
        with _lock:
            for url in expired_urls:
                _mem.pop(url, None)

    stats["seconds"] = round(time.time() - started, 3)
    return stats


def clear() -> int:
    """清空磁盘缓存，返回删除的文件数"""
    removed = 0
    try:
        for path in CACHE_ROOT.glob("*"):
            path.unlink()
            removed += 1
    except Exception as exc:
        print(f"[icon-cache] 清空缓存失败: {exc}")
    with _lock:
        _mem.clear()
    return removed
