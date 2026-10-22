#!/usr/bin/env python3
"""Validate and upload the R2 announcement folder.

Local layout is mirrored exactly under the bucket:
  announcements/manifest.json
  announcements/images/*.png|jpg|jpeg|webp

Usage:
  python tools/upload_announcements.py
  python tools/upload_announcements.py --publish

Credentials come from R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY / R2_ENDPOINT /
R2_BUCKET. The existing gf2-gacha-manager r2_upload module is reused so signing
behaviour stays identical to the other release tools.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ANNOUNCEMENT_DIR = ROOT / "announcements"
MANIFEST_PATH = ANNOUNCEMENT_DIR / "manifest.json"
PUBLIC_BASE = "https://r2.gf2gacha-xkl.uk"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def _manager_dir() -> Path:
    configured = os.environ.get("GF2_GACHA_MANAGER_DIR", "").strip()
    candidates = [
        Path(configured) if configured else None,
        Path(r"D:\myproject\McpAndSkill\mcp\gf2-gacha-manager"),
    ]
    for candidate in candidates:
        if candidate and (candidate / "r2_upload.py").is_file():
            return candidate
    raise SystemExit(
        "找不到 gf2-gacha-manager；请设置 GF2_GACHA_MANAGER_DIR 指向包含 r2_upload.py 的目录"
    )


def _relative_key(path: Path) -> str:
    rel = path.relative_to(ANNOUNCEMENT_DIR).as_posix()
    return "announcements/" + rel


def _load_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        raise SystemExit(f"公告清单不存在：{MANIFEST_PATH}")
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"公告清单 JSON 无效：{exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("announcements"), list):
        raise SystemExit("公告清单必须包含 announcements 数组")
    return data


def _validate(data: dict) -> list[Path]:
    seen: set[str] = set()
    images: list[Path] = []
    for index, item in enumerate(data["announcements"]):
        label = f"announcements[{index}]"
        if not isinstance(item, dict):
            raise SystemExit(f"{label} 必须是对象")
        for field in ("id", "title", "body"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                raise SystemExit(f"{label}.{field} 不能为空")
        item_id = item["id"].strip()
        if item_id in seen:
            raise SystemExit(f"公告 ID 重复：{item_id}")
        seen.add(item_id)

        for image in item.get("images", []):
            if not isinstance(image, str) or not image.strip():
                raise SystemExit(f"{label}.images 含空路径")
            parsed = urlparse(image)
            if parsed.scheme in ("http", "https"):
                continue
            rel = image.strip().lstrip("/")
            if rel.startswith("announcements/"):
                rel = rel[len("announcements/"):]
            local = (ANNOUNCEMENT_DIR / rel).resolve()
            try:
                local.relative_to(ANNOUNCEMENT_DIR.resolve())
            except ValueError:
                raise SystemExit(f"图片路径越界：{image}") from None
            if local.suffix.lower() not in IMAGE_SUFFIXES:
                raise SystemExit(f"不支持的图片格式：{image}")
            if not local.is_file():
                raise SystemExit(f"图片不存在：{image}")
            images.append(local)

    # Upload every local image, including ones staged for the next announcement.
    for path in sorted((ANNOUNCEMENT_DIR / "images").rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES and path not in images:
            images.append(path)
    return sorted(set(images))


def main() -> int:
    parser = argparse.ArgumentParser(description="上传 R2 公告资源")
    parser.add_argument("--publish", action="store_true", help="实际上传；缺省只校验并预览")
    args = parser.parse_args()

    data = _load_manifest()
    images = _validate(data)
    all_files = images + [MANIFEST_PATH]

    print(f"公告目录：{ANNOUNCEMENT_DIR}")
    print(f"清单 URL：{PUBLIC_BASE}/announcements/manifest.json")
    print(f"图片数量：{len(images)}")
    for path in all_files:
        print(f"  {PUBLIC_BASE}/{_relative_key(path)}  ({path.stat().st_size} bytes)")

    if not args.publish:
        print("预览完成；加 --publish 才会写入 R2。")
        return 0

    sys.path.insert(0, str(_manager_dir()))
    from r2_upload import R2Config, content_already_matches, put_object  # type: ignore

    config = R2Config.from_env()
    uploaded = 0
    skipped = 0
    for path in all_files:
        payload = path.read_bytes()
        key = _relative_key(path)
        match = content_already_matches(key, payload, config)
        if match.get("same"):
            skipped += 1
            print(f"跳过（内容一致）：{key}")
            continue
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        cache = (
            "no-cache, max-age=60"
            if path == MANIFEST_PATH
            else "public, max-age=86400"
        )
        result = put_object(key, payload, content_type=content_type, cache_control=cache, config=config)
        uploaded += 1
        print(f"已上传：{key}  etag={result.get('etag', '')[:12]}")

    print(f"完成：上传 {uploaded}，跳过 {skipped}；清单最后上传，顺序安全。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
