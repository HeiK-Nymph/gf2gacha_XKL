"""桌面端公告：清单校验、R2 请求、缓存、断网回退与已读状态。"""
import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.announcement import (
    BASE_URL,
    AnnouncementService,
    fetch_manifest,
    image_url,
    parse_manifest,
)
from tools.announcement_preview import build_preview_data, render_html


class ManifestTests(unittest.TestCase):
    def test_parse_sorts_filters_and_normalizes_images(self):
        payload = {
            "schema": 1,
            "updated_at": 123,
            "announcements": [
                {"id": "old", "title": "旧", "body": "旧内容", "published_at": 10},
                {"id": "expired", "title": "过期", "body": "不显示", "published_at": 99, "expires_at": 90},
                {"id": "hidden", "title": "隐藏", "body": "不显示", "active": False, "published_at": 100},
                {"id": "bad", "title": "", "body": "缺标题", "published_at": 100},
                {
                    "id": "new",
                    "title": " 新公告 ",
                    "body": " 第一行\n第二行 ",
                    "published_at": 20,
                    "images": ["images/a.png", "/announcements/images/b.png", "https://cdn.example/c.png"]
                    + [f"images/{index}.png" for index in range(8)],
                },
            ],
        }
        feed = parse_manifest(payload, now=100)
        self.assertEqual([item["id"] for item in feed["announcements"]], ["new", "old"])
        latest = feed["announcements"][0]
        self.assertEqual(latest["title"], "新公告")
        self.assertEqual(latest["body"], "第一行\n第二行")
        self.assertEqual(len(latest["images"]), 6)
        self.assertEqual(latest["images"][0], BASE_URL + "/announcements/images/a.png")
        self.assertEqual(latest["images"][1], BASE_URL + "/announcements/images/b.png")
        self.assertEqual(latest["images"][2], "https://cdn.example/c.png")

    def test_parse_allows_image_only_announcements(self):
        payload = {
            "schema": 1,
            "announcements": [{
                "id": "image-only",
                "title": "图片公告",
                "body": "",
                "images": ["images/demo.png"],
                "published_at": 20,
            }],
        }
        feed = parse_manifest(payload, now=100)
        self.assertEqual(len(feed["announcements"]), 1)
        self.assertEqual(feed["announcements"][0]["body"], "")
        self.assertEqual(feed["announcements"][0]["images"], [BASE_URL + "/announcements/images/demo.png"])

    def test_image_url_rejects_unsafe_schemes(self):
        self.assertEqual(image_url("javascript:alert(1)"), "")
        self.assertEqual(image_url("images/demo.png"), BASE_URL + "/announcements/images/demo.png")

    def test_parse_rejects_missing_array(self):
        with self.assertRaises(ValueError):
            parse_manifest({"schema": 1})

    def test_fetch_bypasses_environment_proxy_and_sends_no_cache_headers(self):
        response = unittest.mock.Mock()
        response.text = json.dumps({"announcements": []})
        response.raise_for_status.return_value = None
        with patch("backend.announcement.requests.Session") as session_cls:
            session = session_cls.return_value
            session.get.return_value = response
            result = fetch_manifest()
        self.assertFalse(session.trust_env)
        self.assertEqual(result["announcements"], [])
        headers = session.get.call_args.kwargs["headers"]
        self.assertEqual(headers["Cache-Control"], "no-cache")
        session.close.assert_called_once()


class OpenOnlyContractTests(unittest.TestCase):
    def test_clients_do_not_poll_announcements_while_open(self):
        root = Path(__file__).resolve().parent
        desktop = (root / "frontend" / "src" / "App.vue").read_text(encoding="utf-8")
        android = (root / "XKL_android" / "app" / "src" / "main" / "java" / "uk" / "gf2gacha" / "xkl" / "ui" / "MainActivity.kt").read_text(encoding="utf-8")
        self.assertNotIn("announcementTimer", desktop)
        self.assertNotIn("5 * 60 * 1000", desktop)
        self.assertNotIn("lastAnnouncementCheckAt", android)
        self.assertNotIn("ANNOUNCEMENT_CHECK_INTERVAL_MS", android)


class PreviewToolTests(unittest.TestCase):
    def test_preview_embeds_local_images_and_reports_manifest_states(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image_dir = root / "images"
            image_dir.mkdir()
            (image_dir / "demo.png").write_bytes(base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nK0AAAAASUVORK5CYII="
            ))
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "schema": 1,
                "updated_at": 100,
                "announcements": [
                    {"id": "active", "title": "当前", "body": "正文", "images": ["images/demo.png"], "published_at": 20},
                    {"id": "inactive", "title": "停用", "body": "正文", "active": False, "published_at": 10},
                    {"id": "expired", "title": "过期", "body": "正文", "expires_at": 90, "published_at": 30},
                ],
            }, ensure_ascii=False), encoding="utf-8")

            data = build_preview_data(manifest, now=100)
            self.assertEqual(data["latestId"], "active")
            self.assertEqual([item["status"] for item in data["items"]], ["expired", "active", "inactive"])
            self.assertEqual(data["items"][1]["images"][0]["kind"], "local")
            rendered = render_html(data)
            self.assertIn("公告显示测试台", rendered)
            self.assertIn("data:image/png;base64,", rendered)
            self.assertIn("LOCAL ONLY", rendered)
            self.assertIn("body::-webkit-scrollbar", rendered)
            self.assertIn(".announcement-dialog-content::-webkit-scrollbar", rendered)
            self.assertIn("-webkit-overflow-scrolling:touch", rendered)

    def test_preview_accepts_image_only_announcement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image_dir = root / "images"
            image_dir.mkdir()
            (image_dir / "demo.png").write_bytes(base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nK0AAAAASUVORK5CYII="
            ))
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "announcements": [{
                    "id": "image-only", "title": "图片公告", "body": "",
                    "images": ["images/demo.png"], "published_at": 1,
                }],
            }, ensure_ascii=False), encoding="utf-8")
            data = build_preview_data(manifest, now=100)
            self.assertEqual(data["latestId"], "image-only")
            self.assertEqual(data["items"][0]["status"], "active")
            self.assertEqual(data["warnings"], [])

    def test_preview_marks_missing_images_without_network_access(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp) / "manifest.json"
            manifest.write_text(json.dumps({
                "announcements": [{
                    "id": "missing", "title": "缺图", "body": "正文",
                    "images": ["images/nope.png", "https://cdn.example/demo.png"],
                    "published_at": 1,
                }],
            }, ensure_ascii=False), encoding="utf-8")
            data = build_preview_data(manifest, now=100)
            self.assertEqual(data["items"][0]["images"][0]["kind"], "missing")
            self.assertEqual(data["items"][0]["images"][1]["kind"], "remote")
            self.assertEqual(len(data["warnings"]), 1)

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / "announcement_state.json"
        self.cache = Path(self.temp.name) / "announcement_cache.json"
        self.now = [100]
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def service(self, fetch):
        def tracked():
            self.calls.append(1)
            return fetch(len(self.calls))

        return AnnouncementService(
            fetch_fn=tracked,
            state_path=self.state,
            cache_path=self.cache,
            now_fn=lambda: self.now[0],
            cache_ttl=600,
        )

    @staticmethod
    def feed(item_id, published_at=1):
        return {
            "schema": 1,
            "updated_at": published_at,
            "announcements": [{
                "id": item_id,
                "title": "公告 " + item_id,
                "body": "正文",
                "images": [],
                "published_at": published_at,
                "expires_at": 0,
            }],
        }

    def test_cache_and_seen_state_avoid_redundant_fetches(self):
        service = self.service(lambda index: self.feed(f"id-{index}"))
        first = service.latest()
        self.assertEqual(first["announcement"]["id"], "id-1")
        self.assertTrue(first["unread"])
        self.assertEqual(service.mark_seen("id-1")["status"], "success")

        cached = service.latest()
        self.assertEqual(cached["announcement"]["id"], "id-1")
        self.assertFalse(cached["unread"])
        self.assertEqual(len(self.calls), 1)

        self.now[0] += 601
        refreshed = service.latest()
        self.assertEqual(refreshed["announcement"]["id"], "id-2")
        self.assertTrue(refreshed["unread"])
        self.assertEqual(len(self.calls), 2)

    def test_force_refreshes_and_stale_cache_survives_network_failure(self):
        service = self.service(lambda index: self.feed(f"id-{index}"))
        service.latest()
        forced = service.latest(force=True)
        self.assertEqual(forced["announcement"]["id"], "id-2")

        def fail():
            raise RuntimeError("offline")

        empty_cache = Path(self.temp.name) / "empty_cache.json"
        failing = AnnouncementService(
            fetch_fn=fail,
            state_path=self.state,
            cache_path=empty_cache,
            now_fn=lambda: self.now[0],
        )
        self.assertEqual(failing.latest()["status"], "error")

        stale_cache = Path(self.temp.name) / "stale_cache.json"
        cache_service = AnnouncementService(
            fetch_fn=lambda: self.feed("cached"),
            state_path=self.state,
            cache_path=stale_cache,
            now_fn=lambda: self.now[0],
        )
        cache_service.latest()
        cache_service._fetch = fail
        stale = cache_service.latest(force=True)
        self.assertEqual(stale["status"], "success")
        self.assertTrue(stale["stale"])
        self.assertEqual(stale["announcement"]["id"], "cached")
        self.assertIn("上次获取", stale["warning"])

    def test_cache_survives_restart_and_avoids_network(self):
        first = self.service(lambda index: self.feed("cached-id"))
        result = first.latest()
        self.assertEqual(result["announcement"]["id"], "cached-id")
        self.assertFalse(result["cached"])
        self.assertTrue(self.cache.is_file())

        calls = []

        def must_not_fetch():
            calls.append(1)
            raise RuntimeError("should not fetch")

        second = AnnouncementService(
            fetch_fn=must_not_fetch,
            state_path=self.state,
            cache_path=self.cache,
            now_fn=lambda: self.now[0],
            cache_ttl=600,
        )
        restored = second.latest()
        self.assertEqual(restored["status"], "success")
        self.assertEqual(restored["announcement"]["id"], "cached-id")
        self.assertTrue(restored["cached"])
        self.assertEqual(calls, [])

    def test_seen_state_is_written_atomically(self):
        service = self.service(lambda index: self.feed("id-1"))
        result = service.mark_seen("id-1")
        self.assertEqual(result["status"], "success")
        saved = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(saved["last_seen_id"], "id-1")
        self.assertEqual(saved["updated_at"], 100)
        self.assertFalse((self.state.parent / "announcement_state.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
