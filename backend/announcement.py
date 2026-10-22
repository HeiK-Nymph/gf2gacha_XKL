from __future__ import annotations

"""R2 公告中心：与安卓端共用 announcements/manifest.json。"""

import json
import os
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


BASE_URL = "https://r2.gf2gacha-xkl.uk"
MANIFEST_URL = BASE_URL + "/announcements/manifest.json"
CACHE_TTL_SECONDS = 10 * 60
MAX_IMAGES = 6


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def image_url(raw):
    """把清单里的相对图片路径转换成 R2 公网地址。"""
    value = str(raw or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme:
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return value
        return ""
    path = value.lstrip("/")
    if path.startswith("announcements/"):
        return BASE_URL + "/" + path
    return BASE_URL + "/announcements/" + path


def parse_manifest(payload, now=None):
    """校验并整理公告清单；格式异常时抛 ValueError。"""
    data = payload if isinstance(payload, dict) else json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("公告清单必须是 JSON 对象")
    raw_items = data.get("announcements")
    if not isinstance(raw_items, list):
        raise ValueError("公告清单缺少 announcements 数组")

    current = int(time.time() if now is None else now)
    items = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue

        active = raw.get("active", True)
        if isinstance(active, str):
            active = active.strip().lower() not in ("0", "false", "no", "off")
        if not active:
            continue

        item_id = str(raw.get("id") or "").strip()
        title = str(raw.get("title") or "").strip()
        body = str(raw.get("body") or "").strip()
        if not item_id or not title:
            continue

        expires_at = _as_int(raw.get("expires_at"), 0)
        if expires_at > 0 and expires_at <= current:
            continue

        images = []
        raw_images = raw.get("images")
        if isinstance(raw_images, list):
            for raw_image in raw_images:
                normalized = image_url(raw_image)
                if normalized:
                    images.append(normalized)
                if len(images) >= MAX_IMAGES:
                    break

        if not body and not images:
            continue

        items.append({
            "id": item_id,
            "title": title,
            "body": body,
            "images": images,
            "published_at": _as_int(raw.get("published_at"), 0),
            "expires_at": expires_at,
        })

    items.sort(key=lambda item: (item["published_at"], item["id"]), reverse=True)
    return {
        "schema": _as_int(data.get("schema"), 1),
        "updated_at": _as_int(data.get("updated_at"), 0),
        "announcements": items,
    }


def fetch_manifest(url=MANIFEST_URL, timeout=(5, 12)):
    """绕过系统环境代理直接读取 R2，避免代理异常时公告也跟着失效。"""
    session = requests.Session()
    session.trust_env = False
    try:
        response = session.get(
            url,
            headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
            timeout=timeout,
        )
        response.raise_for_status()
        return parse_manifest(response.text)
    finally:
        session.close()


def _app_data_dir():
    app_data = os.environ.get("GF2XKL_APP_DATA_DIR", "").strip()
    if not app_data:
        local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
        app_data = str(Path(local_appdata) / "gf2gacha_XKL") if local_appdata else str(Path.home() / ".gf2gacha_XKL")
    return Path(app_data)


def default_state_path():
    override = os.environ.get("GF2XKL_ANNOUNCEMENT_STATE_PATH", "").strip()
    return Path(override) if override else _app_data_dir() / "announcement_state.json"


def default_cache_path():
    override = os.environ.get("GF2XKL_ANNOUNCEMENT_CACHE_PATH", "").strip()
    return Path(override) if override else _app_data_dir() / "announcement_cache.json"


class AnnouncementService:
    """带 10 分钟持久化缓存、断网回退和本机已读状态的公告服务。"""

    def __init__(self, fetch_fn=None, state_path=None, cache_path=None, now_fn=None,
                 monotonic_fn=None, cache_ttl=CACHE_TTL_SECONDS):
        self._fetch = fetch_fn or fetch_manifest
        self._state_path = Path(state_path) if state_path else None
        self._cache_path = Path(cache_path) if cache_path else None
        self._now = now_fn or time.time
        self._cache_ttl = max(0.0, float(cache_ttl))
        self._lock = threading.RLock()
        self._feed = None
        self._fetched_at = 0
        self._cache_loaded = False

    def _state_file(self):
        return self._state_path or default_state_path()

    def _cache_file(self):
        return self._cache_path or default_cache_path()

    def _load_cache_if_needed(self):
        if self._cache_loaded:
            return
        self._cache_loaded = True
        try:
            data = json.loads(self._cache_file().read_text(encoding="utf-8"))
            feed = data.get("feed") if isinstance(data, dict) else None
            fetched_at = _as_int(data.get("fetched_at"), 0) if isinstance(data, dict) else 0
            if isinstance(feed, dict) and isinstance(feed.get("announcements"), list):
                self._feed = feed
                self._fetched_at = fetched_at
        except Exception:
            pass

    def _write_cache(self, feed, fetched_at):
        try:
            path = self._cache_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(json.dumps({
                "fetched_at": int(fetched_at),
                "feed": feed,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, path)
        except Exception as exc:
            print(f"[WARNING] 写入公告缓存失败: {exc}")

    def _last_seen_id(self):
        try:
            data = json.loads(self._state_file().read_text(encoding="utf-8"))
            return str(data.get("last_seen_id") or "") if isinstance(data, dict) else ""
        except Exception:
            return ""

    def mark_seen(self, announcement_id):
        item_id = str(announcement_id or "").strip()
        if not item_id or len(item_id) > 256:
            return {"status": "error", "message": "公告 ID 无效"}
        path = self._state_file()
        try:
            with self._lock:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_name(path.name + ".tmp")
                tmp.write_text(json.dumps({
                    "last_seen_id": item_id,
                    "updated_at": int(self._now()),
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(tmp, path)
            return {"status": "success", "last_seen_id": item_id}
        except Exception as exc:
            return {"status": "error", "message": f"保存公告已读状态失败：{exc}"}

    def latest(self, force=False):
        with self._lock:
            self._load_cache_if_needed()
            now = int(self._now())
            age = max(0, now - self._fetched_at) if self._fetched_at else None
            fresh = age is not None and age <= self._cache_ttl
            stale = False
            warning = ""
            from_cache = bool(self._feed is not None and fresh and not force)

            if not from_cache:
                try:
                    self._feed = self._fetch()
                    self._fetched_at = now
                    self._write_cache(self._feed, now)
                    age = 0
                except Exception as exc:
                    if self._feed is None:
                        return {
                            "status": "error",
                            "message": f"公告获取失败：{exc}",
                            "checked_at": now,
                        }
                    stale = True
                    from_cache = True
                    warning = f"公告更新失败，已显示上次获取的内容：{exc}"

            feed = self._feed or {"updated_at": 0, "announcements": []}
            announcements = feed.get("announcements") if isinstance(feed, dict) else []
            latest = announcements[0] if isinstance(announcements, list) and announcements else None
            unread = bool(latest and self._last_seen_id() != latest.get("id"))
            return {
                "status": "success",
                "announcement": latest,
                "unread": unread,
                "stale": stale,
                "cached": from_cache,
                "age_seconds": age,
                "warning": warning,
                "checked_at": now,
                "updated_at": _as_int(feed.get("updated_at"), 0) if isinstance(feed, dict) else 0,
            }
