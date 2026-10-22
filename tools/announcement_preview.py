#!/usr/bin/env python3
"""Generate a local-only announcement layout preview for desktop and Android.

The preview reads announcements/manifest.json, embeds local images as data URLs,
and writes one standalone HTML file. It never contacts R2 and never uploads.

Usage:
  python tools/announcement_preview.py
  python tools/announcement_preview.py --no-open
  python tools/announcement_preview.py --manifest announcements/manifest.json
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "announcements" / "manifest.json"
DEFAULT_OUTPUT = ROOT / "test" / "announcement-preview" / "index.html"
MAX_IMAGES = 6
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no", "off", "")
    return bool(value)


def _mime_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _data_uri(path: Path) -> str:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{_mime_type(path)};base64,{payload}"


def _resolve_local_image(base_dir: Path, raw: str) -> tuple[Path | None, str]:
    value = raw.strip().lstrip("/")
    if value.startswith("announcements/"):
        value = value[len("announcements/"):]
    candidate = (base_dir / value).resolve()
    try:
        candidate.relative_to(base_dir.resolve())
    except ValueError:
        return None, "图片路径越界"
    if candidate.suffix.lower() not in IMAGE_SUFFIXES:
        return None, "不支持的图片格式"
    if not candidate.is_file():
        return None, "本地图片不存在"
    return candidate, ""


def build_preview_data(manifest_path: Path, now: int | None = None) -> dict:
    """Load and validate a local manifest without network access."""
    manifest_path = Path(manifest_path).resolve()
    if not manifest_path.is_file():
        raise ValueError(f"公告清单不存在：{manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"公告清单 JSON 无效：{exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("announcements"), list):
        raise ValueError("公告清单必须包含 announcements 数组")

    current = int(time.time() if now is None else now)
    base_dir = manifest_path.parent
    warnings: list[str] = []
    seen_ids: set[str] = set()
    items: list[dict] = []

    for index, raw in enumerate(payload["announcements"]):
        label = f"announcements[{index}]"
        if not isinstance(raw, dict):
            warnings.append(f"{label} 不是对象，已跳过")
            continue

        item_id = str(raw.get("id") or "").strip()
        title = str(raw.get("title") or "").strip()
        body = str(raw.get("body") or "").strip()
        active = _as_bool(raw.get("active", True), True)
        published_at = _as_int(raw.get("published_at"), 0)
        expires_at = _as_int(raw.get("expires_at"), 0)
        duplicate = bool(item_id and item_id in seen_ids)
        if item_id:
            seen_ids.add(item_id)

        missing = [name for name, value in (("id", item_id), ("title", title)) if not value]

        raw_images = raw.get("images")
        if raw_images is None:
            raw_images = []
        if not isinstance(raw_images, list):
            warnings.append(f"{label}.images 不是数组，两端会忽略")
            raw_images = []
        if len(raw_images) > MAX_IMAGES:
            warnings.append(f"{label} 有 {len(raw_images)} 张图片，两端只展示前 {MAX_IMAGES} 张")

        images: list[dict] = []
        for image_index, raw_image in enumerate(raw_images[:MAX_IMAGES]):
            image_text = str(raw_image or "").strip()
            image_label = f"{label}.images[{image_index}]"
            if not image_text:
                warnings.append(f"{image_label} 为空，两端会忽略")
                continue
            parsed = urlparse(image_text)
            if parsed.scheme:
                if parsed.scheme in ("http", "https") and parsed.netloc:
                    images.append({"kind": "remote", "src": "", "label": image_text, "note": "远程图片，本地预览不会访问"})
                else:
                    warnings.append(f"{image_label} 使用了不支持的地址：{image_text}")
                    images.append({"kind": "missing", "src": "", "label": image_text, "note": "不支持的图片地址"})
                continue

            local_path, error = _resolve_local_image(base_dir, image_text)
            if local_path is None:
                warnings.append(f"{image_label} {error}：{image_text}")
                images.append({"kind": "missing", "src": "", "label": image_text, "note": error})
                continue
            images.append({
                "kind": "local",
                "src": _data_uri(local_path),
                "label": image_text,
                "note": f"{local_path.stat().st_size} bytes",
            })

        has_image_ref = any(str(image or "").strip() for image in raw_images[:MAX_IMAGES])
        if missing:
            status, status_label = "invalid", "字段缺失"
            warnings.append(f"{label} 缺少 {', '.join(missing)}，两端会跳过")
        elif duplicate:
            status, status_label = "invalid", "ID 重复"
            warnings.append(f"{label}.id 重复：{item_id}，上传脚本会拒绝")
        elif not body and not has_image_ref:
            status, status_label = "invalid", "内容为空"
            warnings.append(f"{label} 的正文和图片不能同时为空，两端会跳过")
        elif not active:
            status, status_label = "inactive", "已停用"
        elif expires_at > 0 and expires_at <= current:
            status, status_label = "expired", "已过期"
        else:
            status, status_label = "active", "启用中"

        items.append({
            "id": item_id,
            "title": title,
            "body": body,
            "active": active,
            "publishedAt": published_at,
            "expiresAt": expires_at,
            "status": status,
            "statusLabel": status_label,
            "images": images,
            "imageTotal": len(raw_images),
            "bodyLength": len(body),
        })

    items.sort(key=lambda item: (item["publishedAt"], item["id"]), reverse=True)
    latest = next((item for item in items if item["status"] == "active"), None)
    return {
        "manifestPath": str(manifest_path),
        "generatedAt": current,
        "items": items,
        "latestId": latest["id"] if latest else "",
        "warnings": warnings,
        "updatedAt": _as_int(payload.get("updated_at"), 0),
    }


def _script_json(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


HTML_TEMPLATE = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>公告显示测试台</title>
  <style>
    :root { --ink:#2f392c; --muted:#7b8475; --paper:#f4f5f0; --paper2:#fbfaf6; --line:#d8c6a2; --gold:#d9a441; --goldsoft:#f0e5cd; --abg:#0e0e11; --acard:#17171c; --aline:#2a2a32; --agold:#e8c170; --atext:#f2f2f5; --adim:#8e8e99; }
    * { box-sizing:border-box; }
    html, body { scrollbar-width:none; -ms-overflow-style:none; }
    html::-webkit-scrollbar, body::-webkit-scrollbar { display:none; width:0; height:0; }
    body { margin:0; background:#e9ebe4; color:var(--ink); font-family:"Microsoft YaHei UI","Segoe UI",sans-serif; }
    code { font-family:Consolas,monospace; }
    .lab-header { display:flex; align-items:flex-end; justify-content:space-between; gap:24px; padding:28px 36px 20px; border-bottom:1px solid #cbd0c2; background:#f8f9f4; }
    .lab-kicker { color:#9a7b48; font:12px/1.4 Consolas,monospace; letter-spacing:2px; }
    h1 { margin:8px 0 4px; font-size:30px; letter-spacing:1px; }
    .lab-sub { margin:0; color:var(--muted); font-size:13px; line-height:1.7; }
    .lab-summary { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:8px; max-width:620px; }
    .chip { padding:7px 10px; border:1px solid #cbd0c2; border-radius:999px; background:#fff; color:#586451; font-size:12px; white-space:nowrap; }
    .chip strong { color:#34402f; }
    .chip.warn { border-color:#e0b46e; background:#fff5df; color:#8b6221; }
    .controls { position:sticky; top:0; z-index:20; display:flex; align-items:center; flex-wrap:wrap; gap:12px; padding:14px 36px; border-bottom:1px solid #cbd0c2; background:rgba(248,249,244,.96); backdrop-filter:blur(8px); }
    .controls label { display:flex; align-items:center; gap:8px; color:#586451; font-size:13px; }
    select, button { min-height:36px; padding:7px 12px; border:1px solid #b9c0af; border-radius:4px; background:#fff; color:#34402f; font:13px "Microsoft YaHei UI","Segoe UI",sans-serif; }
    select { max-width:420px; }
    button { cursor:pointer; }
    button:hover { background:#eef0e8; }
    .control-note { margin-left:auto; color:var(--muted); font-size:12px; }
    .selection-note { display:none; width:100%; padding:9px 12px; border-left:4px solid var(--gold); background:#fff5df; color:#7a5a21; font-size:12px; line-height:1.6; }
    .selection-note.on { display:block; }
    .stage { display:grid; grid-template-columns:minmax(680px,1.45fr) minmax(380px,.75fr); gap:24px; align-items:start; padding:24px 36px 10px; }
    .preview-card { min-width:0; }
    .preview-head { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:10px; }
    .preview-title { font-size:14px; font-weight:800; letter-spacing:1px; }
    .preview-sub { color:var(--muted); font-size:11px; }
    .state-chips { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:6px; }
    .state-chip { padding:4px 8px; border-radius:999px; background:#dfe3d8; color:#586451; font-size:11px; }
    .state-chip.new { background:#f4dfb4; color:#79531a; }
    .state-chip.cache { background:#f7e9c9; color:#805b1f; }
    .state-chip.off { background:#e3e5df; color:#858b80; }
    .desktop-window { position:relative; overflow:hidden; width:100%; height:680px; border:1px solid #c7cbbf; border-radius:10px; background:var(--paper); box-shadow:0 22px 55px rgba(38,46,35,.15); }
    .desktop-top { display:flex; align-items:center; justify-content:space-between; gap:18px; padding:18px 22px; border-bottom:1px solid #d7dccf; background:#f8f9f4; }
    .brand { display:flex; align-items:center; gap:10px; font-weight:800; }
    .brand-mark { width:10px; height:10px; background:var(--gold); }
    .desktop-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
    .fake-el-button { display:inline-flex; align-items:center; gap:5px; padding:9px 13px; border:1px solid #c7cbbf; border-radius:4px; background:#f4f5f0; color:#4b5547; font-size:12px; white-space:nowrap; }
    .fake-el-button.primary { border-color:var(--gold); background:var(--gold); color:var(--ink); }
    .fake-el-button.new { border-color:#c58c2d; background:#f6e4bd; color:#6f4d18; font-weight:700; }
    .version { color:#8b927f; font:11px Consolas,monospace; }
    .desktop-main { padding:22px; }
    .desktop-main-title { font-size:16px; font-weight:800; }
    .desktop-main-sub { margin-top:5px; color:var(--muted); font-size:12px; }
    .desktop-cards { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-top:18px; }
    .desktop-card { height:115px; padding:14px; border:1px solid #d8ddcf; border-radius:6px; background:#fbfcf8; }
    .desktop-card b { display:block; font-size:13px; }
    .desktop-card span { display:block; margin-top:34px; color:#a3aa9b; font-size:11px; }
    .desktop-overlay { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; padding:22px; background:rgba(34,39,31,.58); }
    .desktop-overlay.hidden, .android-overlay.hidden, .desktop-toast.hidden, .android-toast.hidden { display:none; }
    .announcement-dialog { overflow:hidden; width:720px; max-width:100%; max-height:620px; border:1px solid var(--line); border-radius:8px; background:var(--paper2); box-shadow:0 28px 90px rgba(35,31,22,.28); }
    .announcement-dialog-header { position:relative; padding:24px 68px 20px 30px; border-top:5px solid var(--gold); background:linear-gradient(115deg,var(--goldsoft) 0%,var(--paper2) 70%); }
    .announcement-kicker { display:flex; align-items:center; gap:9px; color:#9b7b43; font:11px/1.4 Consolas,monospace; letter-spacing:2px; }
    .announcement-kicker-line { width:7px; height:7px; background:var(--gold); }
    .announcement-close { position:absolute; top:18px; right:20px; width:34px; height:34px; padding:0; border:0; background:transparent; color:#8a7c66; font-size:27px; line-height:32px; }
    .announcement-dialog-title { margin-top:13px; color:var(--ink); font-size:27px; font-weight:800; letter-spacing:1px; line-height:1.35; }
    .announcement-dialog-meta { margin-top:7px; color:#958b7a; font:11px Consolas,monospace; }
    .announcement-dialog-content { max-height:390px; overflow-y:auto; padding:20px 30px 4px; scrollbar-width:none; -ms-overflow-style:none; overscroll-behavior:contain; }
    .announcement-dialog-content::-webkit-scrollbar { display:none; width:0; height:0; }
    .announcement-copy { color:#4c5548; font-size:14px; line-height:1.9; white-space:pre-wrap; overflow-wrap:anywhere; }
    .announcement-images { display:flex; flex-direction:column; gap:14px; margin-top:20px; }
    .announcement-image { display:block; width:100%; max-height:520px; object-fit:contain; border:1px solid #ded5c2; border-radius:4px; background:#f1eee7; }
    .image-placeholder { display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:120px; padding:16px; border:1px dashed #d6c7a9; border-radius:4px; background:#f1eee7; color:#9b8e78; font-size:12px; text-align:center; overflow-wrap:anywhere; }
    .announcement-dialog-footer { padding:16px 30px 24px; text-align:right; }
    .announcement-dialog-footer .fake-el-button { padding:10px 20px; border-color:var(--gold); background:var(--gold); color:var(--ink); }
    .desktop-toast { position:absolute; top:18px; left:50%; transform:translateX(-50%); padding:10px 16px; border:1px solid #e0b46e; border-radius:4px; background:#fff5df; color:#8b6221; font-size:12px; box-shadow:0 8px 25px rgba(35,31,22,.16); }
    .phone-shell { width:390px; max-width:100%; margin:0 auto; padding:10px; border:1px solid #303036; border-radius:34px; background:#050506; box-shadow:0 22px 55px rgba(38,46,35,.22); }
    .phone-screen { position:relative; overflow:hidden; height:760px; border-radius:25px; background:var(--abg); color:var(--atext); }
    .phone-status { display:flex; justify-content:space-between; padding:10px 18px 4px; color:#b7b7bf; font:10px Consolas,monospace; }
    .android-app { padding:10px 16px 16px; }
    .android-uid { color:var(--adim); font-size:11px; }
    .android-title-row { display:flex; align-items:center; gap:8px; margin-top:6px; }
    .android-title { flex:1; color:var(--agold); font-size:22px; font-weight:800; }
    .android-button { padding:8px 11px; border:1px solid #3a3a43; border-radius:5px; background:#202027; color:var(--agold); font-size:11px; white-space:nowrap; }
    .android-button.new { border-color:#9c7a3c; background:#332b1d; font-weight:700; }
    .android-hero { display:flex; gap:8px; margin-top:14px; }
    .android-avatar { flex:1; height:94px; border:1px solid var(--aline); border-radius:7px; background:linear-gradient(145deg,#292832,#17171c); }
    .android-tags { display:flex; gap:7px; margin-top:10px; }
    .android-tag { padding:5px 8px; border:1px solid #3a3a43; border-radius:999px; background:#23232b; color:var(--adim); font-size:9px; }
    .android-stats { display:grid; grid-template-columns:repeat(3,1fr); margin-top:14px; padding:14px 8px; border:1px solid var(--aline); border-radius:7px; background:var(--acard); }
    .android-stat { text-align:center; border-right:1px solid var(--aline); }
    .android-stat:last-child { border-right:0; }
    .android-stat b { display:block; color:var(--agold); font-size:17px; }
    .android-stat span { color:var(--adim); font-size:9px; }
    .android-actions { display:grid; grid-template-columns:repeat(4,1fr); gap:7px; margin-top:12px; }
    .android-actions .android-button { padding:10px 4px; text-align:center; }
    .android-overlay { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; padding:18px; background:rgba(0,0,0,.68); }
    .material-dialog { width:100%; max-height:650px; overflow:hidden; border:1px solid #33333c; border-radius:14px; background:var(--acard); box-shadow:0 24px 70px rgba(0,0,0,.55); }
    .material-dialog-title { padding:20px 20px 0; color:var(--agold); font-size:18px; font-weight:700; line-height:1.4; }
    .material-dialog-scroll { max-height:500px; overflow-x:hidden; overflow-y:auto; padding:4px 20px; scrollbar-width:none; -ms-overflow-style:none; overscroll-behavior:contain; -webkit-overflow-scrolling:touch; touch-action:pan-y; }
    .material-dialog-scroll::-webkit-scrollbar { display:none; width:0; height:0; }
    .android-meta { color:var(--agold); font-size:11px; }
    .android-body { margin-top:8px; color:var(--atext); font-size:13px; line-height:1.75; white-space:pre-wrap; overflow-wrap:anywhere; }
    .android-images { display:flex; flex-direction:column; gap:10px; margin-top:10px; }
    .android-image { display:block; width:100%; height:auto; border-radius:5px; background:#23232b; }
    .material-dialog-actions { padding:12px 20px 18px; text-align:right; }
    .android-dismiss { padding:8px 4px; border:0; background:transparent; color:var(--agold); font-size:13px; font-weight:700; }
    .android-toast { position:absolute; left:50%; bottom:42px; transform:translateX(-50%); padding:9px 14px; border-radius:5px; background:#34343d; color:#f1f1f4; font-size:11px; white-space:nowrap; box-shadow:0 8px 24px rgba(0,0,0,.35); }
    .manifest-panel { margin:16px 36px 36px; padding:18px 20px; border:1px solid #cbd0c2; border-radius:8px; background:#f8f9f4; }
    .manifest-head { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:12px; }
    .manifest-head h2 { margin:0; font-size:15px; }
    .manifest-head span { color:var(--muted); font-size:11px; }
    .manifest-list { display:flex; flex-direction:column; gap:7px; }
    .manifest-row { display:grid; grid-template-columns:84px minmax(140px,1.2fr) minmax(180px,2fr) 125px 110px 80px; gap:10px; align-items:center; padding:10px 12px; border:1px solid #dde1d6; border-radius:5px; background:#fff; font-size:12px; }
    .manifest-row.current { border-color:var(--gold); background:#fffaf0; }
    .status-badge { justify-self:start; padding:3px 7px; border-radius:999px; background:#e7eadf; color:#66705e; font-size:10px; white-space:nowrap; }
    .status-badge.active { background:#e2f0df; color:#3f6d38; }
    .status-badge.invalid { background:#f8dcd8; color:#9b3e36; }
    .status-badge.expired, .status-badge.inactive { background:#e7e8e4; color:#777d73; }
    .manifest-title { font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .manifest-id { color:#777f71; font:11px Consolas,monospace; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .manifest-meta { color:#858c7e; font-size:11px; }
    .warning-panel { margin-top:12px; padding:11px 13px; border-left:4px solid var(--gold); background:#fff5df; color:#7a5a21; font-size:12px; line-height:1.75; white-space:pre-wrap; }
    .warning-panel.hidden { display:none; }
    .empty-row { padding:20px; color:var(--muted); text-align:center; font-size:12px; }
    @media (max-width:1120px) { .stage { grid-template-columns:1fr; } .phone-shell { margin-left:0; } .manifest-row { grid-template-columns:84px minmax(140px,1.2fr) minmax(180px,2fr) 110px 100px; } .manifest-row .manifest-images { display:none; } }
    @media (max-width:720px) { .lab-header, .controls, .stage { padding-left:16px; padding-right:16px; } .lab-header { align-items:flex-start; flex-direction:column; } .lab-summary { justify-content:flex-start; } .desktop-window { height:620px; } .manifest-panel { margin-left:16px; margin-right:16px; } .manifest-row { grid-template-columns:76px minmax(100px,1fr) 110px; } .manifest-row .manifest-id, .manifest-row .manifest-meta, .manifest-row .manifest-images { display:none; } }
  </style>
</head>
<body>
  <header class="lab-header">
    <div>
      <div class="lab-kicker">ANNOUNCEMENT PREVIEW / LOCAL ONLY</div>
      <h1>公告显示测试台</h1>
      <p class="lab-sub">读取本地清单并内嵌图片；不访问 R2、不上传。修改公告后重新运行脚本即可刷新。</p>
    </div>
    <div class="lab-summary" id="summary"></div>
  </header>
  <section class="controls">
    <label>测试场景
      <select id="scenario">
        <option value="unread">打开 App · 新公告（未读）</option>
        <option value="read">手动打开 · 已读</option>
        <option value="cached">缓存回退 · 网络失败</option>
        <option value="closed">仅看入口按钮</option>
        <option value="empty">暂无公告</option>
      </select>
    </label>
    <label>公告内容 <select id="announcement"></select></label>
    <button type="button" id="reload">重新载入页面</button>
    <span class="control-note">页面生成时间：<span id="generated-at"></span></span>
    <div class="selection-note" id="selection-note"></div>
  </section>
  <main class="stage">
    <section class="preview-card">
      <div class="preview-head">
        <div><div class="preview-title">桌面端</div><div class="preview-sub">暖白纸张公告弹窗 · 720px</div></div>
        <div class="state-chips" id="desktop-states"></div>
      </div>
      <div class="desktop-window">
        <div class="desktop-top">
          <div class="brand"><span class="brand-mark"></span>少女前线抽卡记录工具</div>
          <div class="desktop-actions">
            <span class="fake-el-button primary">分享</span><span class="version">v1.1.6</span>
            <span class="fake-el-button" id="desktop-button">🔔 公告</span>
            <span class="fake-el-button">检查更新</span><span class="fake-el-button">日志</span>
          </div>
        </div>
        <div class="desktop-main">
          <div class="desktop-main-title">抽卡记录</div>
          <div class="desktop-main-sub">用于观察公告弹窗排布的本地静态背景，不包含真实账号数据。</div>
          <div class="desktop-cards">
            <div class="desktop-card"><b>角色池</b><span>抽卡信息占位</span></div>
            <div class="desktop-card"><b>武器池</b><span>抽卡信息占位</span></div>
            <div class="desktop-card"><b>常驻池</b><span>抽卡信息占位</span></div>
          </div>
        </div>
        <div class="desktop-toast hidden" id="desktop-toast">暂无公告</div>
        <div class="desktop-overlay hidden" id="desktop-overlay">
          <div class="announcement-dialog" role="dialog" aria-label="桌面端公告预览">
            <div class="announcement-dialog-header">
              <div class="announcement-kicker"><span class="announcement-kicker-line"></span>ANNOUNCEMENT / 公告</div>
              <button class="announcement-close" type="button" aria-label="关闭公告">×</button>
              <div class="announcement-dialog-title" id="desktop-dialog-title"></div>
              <div class="announcement-dialog-meta" id="desktop-dialog-meta"></div>
            </div>
            <div class="announcement-dialog-content">
              <div class="announcement-copy" id="desktop-copy"></div>
              <div class="announcement-images" id="desktop-images"></div>
            </div>
            <div class="announcement-dialog-footer"><span class="fake-el-button">知道了</span></div>
          </div>
        </div>
      </div>
    </section>
    <section class="preview-card">
      <div class="preview-head">
        <div><div class="preview-title">安卓端</div><div class="preview-sub">Material 暗金公告弹窗 · 390px</div></div>
        <div class="state-chips" id="android-states"></div>
      </div>
      <div class="phone-shell"><div class="phone-screen">
        <div class="phone-status"><span>10:24</span><span>5G&nbsp;&nbsp;86%</span></div>
        <div class="android-app">
          <div class="android-uid">UID: 100****001</div>
          <div class="android-title-row"><div class="android-title">稳定发挥</div><span class="android-button" id="android-button">公告</span><span class="android-button">检查更新</span></div>
          <div class="android-hero"><div class="android-avatar"></div><div class="android-avatar"></div><div class="android-avatar"></div></div>
          <div class="android-tags"><span class="android-tag">一鸣惊人</span><span class="android-tag">五星收集者</span></div>
          <div class="android-stats"><div class="android-stat"><b>45</b><span>平均出金</span></div><div class="android-stat"><b>18</b><span>五星数量</span></div><div class="android-stat"><b>62%</b><span>不歪率</span></div></div>
          <div class="android-actions"><span class="android-button">添加账号</span><span class="android-button">选择账号</span><span class="android-button">分享</span><span class="android-button">刷新</span></div>
        </div>
        <div class="android-toast hidden" id="android-toast">暂无公告</div>
        <div class="android-overlay hidden" id="android-overlay">
          <div class="material-dialog" role="dialog" aria-label="安卓端公告预览">
            <div class="material-dialog-title" id="android-dialog-title"></div>
            <div class="material-dialog-scroll">
              <div class="android-meta" id="android-dialog-meta"></div>
              <div class="android-body" id="android-copy"></div>
              <div class="android-images" id="android-images"></div>
            </div>
            <div class="material-dialog-actions"><button class="android-dismiss" type="button">知道了</button></div>
          </div>
        </div>
      </div></div>
    </section>
  </main>
  <section class="manifest-panel">
    <div class="manifest-head"><h2>清单状态</h2><span>只有“启用中”且发布时间最新的一条会被两端自动展示</span></div>
    <div class="manifest-list" id="manifest-list"></div>
    <div class="warning-panel hidden" id="warning-panel"></div>
  </section>
  <script>
    const DATA = __DATA__;
    const $ = (id) => document.getElementById(id);
    const scenario = $('scenario');
    const announcementSelect = $('announcement');

    function formatDesktopDate(timestamp) {
      const value = Number(timestamp || 0);
      if (!Number.isFinite(value) || value <= 0) return '';
      try {
        return new Intl.DateTimeFormat('zh-CN', { year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false }).format(new Date(value * 1000));
      } catch (_) { return ''; }
    }

    function formatAndroidDate(timestamp) {
      const value = Number(timestamp || 0);
      if (!Number.isFinite(value) || value <= 0) return '';
      const date = new Date(value * 1000);
      const pad = (n) => String(n).padStart(2, '0');
      return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
    }

    function selectedItem() {
      const id = announcementSelect.value;
      return DATA.items.find((item) => item.id === id) || DATA.items.find((item) => item.id === DATA.latestId) || DATA.items[0] || null;
    }

    function clearNode(node) { while (node.firstChild) node.removeChild(node.firstChild); }

    function makeChip(text, className) {
      const span = document.createElement('span');
      span.className = 'state-chip' + (className ? ' ' + className : '');
      span.textContent = text;
      return span;
    }

    function renderImages(container, item, platform) {
      clearNode(container);
      if (!item) return;
      item.images.forEach((image, index) => {
        if (image.kind === 'local') {
          const img = document.createElement('img');
          img.className = platform === 'desktop' ? 'announcement-image' : 'android-image';
          img.src = image.src;
          img.alt = `公告图片 ${index + 1}`;
          img.addEventListener('error', () => {
            const placeholder = document.createElement('div');
            placeholder.className = 'image-placeholder';
            placeholder.textContent = '图片内嵌失败：' + image.label;
            container.replaceChild(placeholder, img);
          });
          container.appendChild(img);
        } else {
          const placeholder = document.createElement('div');
          placeholder.className = 'image-placeholder';
          const title = document.createElement('strong');
          title.textContent = image.note;
          const code = document.createElement('code');
          code.textContent = image.label;
          placeholder.append(title, document.createElement('br'), code);
          container.appendChild(placeholder);
        }
      });
    }

    function setButton(button, unread) {
      button.textContent = unread ? '🔔 公告 · 新' : '🔔 公告';
      button.classList.toggle('new', unread);
    }

    function renderStates(target, item, unread, dialogOpen, cacheState) {
      clearNode(target);
      target.appendChild(makeChip(unread ? '按钮：公告 · 新' : '按钮：公告', unread ? 'new' : ''));
      target.appendChild(makeChip(dialogOpen ? '弹窗：打开' : '弹窗：关闭', dialogOpen ? '' : 'off'));
      target.appendChild(makeChip(cacheState ? '数据：缓存回退' : '数据：本地清单', cacheState ? 'cache' : ''));
      if (item) target.appendChild(makeChip(`图片：${item.images.length} 张`));
    }

    function render() {
      const item = scenario.value === 'empty' ? null : selectedItem();
      const unread = scenario.value === 'unread' && !!item;
      const dialogOpen = !!item && ['unread', 'read', 'cached'].includes(scenario.value);
      const cacheState = scenario.value === 'cached' && !!item;
      const emptyToast = scenario.value === 'empty';

      setButton($('desktop-button'), unread);
      setButton($('android-button'), unread);
      $('desktop-overlay').classList.toggle('hidden', !dialogOpen);
      $('android-overlay').classList.toggle('hidden', !dialogOpen);
      $('desktop-toast').classList.toggle('hidden', !emptyToast);
      $('android-toast').classList.toggle('hidden', !emptyToast);

      if (item) {
        const desktopDate = formatDesktopDate(item.publishedAt);
        const androidDate = formatAndroidDate(item.publishedAt);
        $('desktop-dialog-title').textContent = item.title || '公告';
        $('desktop-dialog-meta').textContent = desktopDate;
        $('desktop-copy').textContent = item.body;
        $('desktop-copy').style.display = item.body ? '' : 'none';
        $('android-dialog-title').textContent = item.title || '公告';
        $('android-dialog-meta').textContent = androidDate ? `公告 · ${androidDate}` : '公告';
        $('android-copy').textContent = item.body;
        $('android-copy').style.display = item.body ? '' : 'none';
        renderImages($('desktop-images'), item, 'desktop');
        renderImages($('android-images'), item, 'android');
      } else {
        ['desktop-dialog-title','desktop-dialog-meta','desktop-copy','android-dialog-title','android-dialog-meta','android-copy'].forEach((id) => { $(id).textContent = ''; $(id).style.display = ''; });
        clearNode($('desktop-images'));
        clearNode($('android-images'));
      }

      renderStates($('desktop-states'), item, unread, dialogOpen, cacheState);
      renderStates($('android-states'), item, unread, dialogOpen, cacheState);

      const note = $('selection-note');
      if (item && item.status !== 'active') {
        note.textContent = `当前选中的公告状态为“${item.statusLabel}”，真实客户端不会展示它；这里仍可检查长内容或图片排布。`;
        note.classList.add('on');
      } else if (cacheState) {
        note.textContent = '缓存回退场景：两端会显示最近一次成功缓存的公告；桌面端额外提示更新失败，安卓端仅在手动打开且有缓存时继续显示。';
        note.classList.add('on');
      } else {
        note.textContent = '';
        note.classList.remove('on');
      }
    }

    function renderManifest() {
      const list = $('manifest-list');
      clearNode(list);
      if (!DATA.items.length) {
        const empty = document.createElement('div');
        empty.className = 'empty-row';
        empty.textContent = '清单中没有公告。';
        list.appendChild(empty);
        return;
      }
      DATA.items.forEach((item) => {
        const row = document.createElement('div');
        row.className = 'manifest-row' + (item.id === DATA.latestId ? ' current' : '');
        const badge = document.createElement('span');
        badge.className = 'status-badge ' + item.status;
        badge.textContent = item.id === DATA.latestId ? '两端展示' : item.statusLabel;
        const title = document.createElement('div');
        title.className = 'manifest-title';
        title.textContent = item.title || '（无标题）';
        title.title = item.title;
        const id = document.createElement('div');
        id.className = 'manifest-id';
        id.textContent = item.id || '（无 ID）';
        id.title = item.id;
        const meta = document.createElement('div');
        meta.className = 'manifest-meta';
        meta.textContent = `发布 ${formatDesktopDate(item.publishedAt) || '—'} · 正文 ${item.bodyLength} 字`;
        const expires = document.createElement('div');
        expires.className = 'manifest-meta';
        expires.textContent = item.expiresAt > 0 ? `到期 ${formatDesktopDate(item.expiresAt)}` : '长期有效';
        const images = document.createElement('div');
        images.className = 'manifest-meta manifest-images';
        images.textContent = `${item.images.length}/${item.imageTotal} 图`;
        row.append(badge, title, id, meta, expires, images);
        list.appendChild(row);
      });
    }

    function renderSummary() {
      const summary = $('summary');
      clearNode(summary);
      const activeCount = DATA.items.filter((item) => item.status === 'active').length;
      const localImageCount = DATA.items.reduce((sum, item) => sum + item.images.filter((image) => image.kind === 'local').length, 0);
      const chips = [['公告', `${DATA.items.length} 条`], ['启用中', `${activeCount} 条`], ['本地图片', `${localImageCount} 张`], ['校验警告', `${DATA.warnings.length} 条`]];
      chips.forEach(([label, value], index) => {
        const chip = document.createElement('span');
        chip.className = 'chip' + (index === 3 && DATA.warnings.length ? ' warn' : '');
        const strong = document.createElement('strong');
        strong.textContent = value;
        chip.append(label + ' ', strong);
        summary.appendChild(chip);
      });
    }

    function renderWarnings() {
      const panel = $('warning-panel');
      if (!DATA.warnings.length) {
        panel.classList.add('hidden');
        panel.textContent = '';
        return;
      }
      panel.textContent = '清单校验：\n' + DATA.warnings.map((warning) => '• ' + warning).join('\n');
      panel.classList.remove('hidden');
    }

    function populateControls() {
      clearNode(announcementSelect);
      DATA.items.forEach((item) => {
        const option = document.createElement('option');
        option.value = item.id;
        option.textContent = `[${item.statusLabel}] ${item.title || '（无标题）'} · ${item.id || '（无 ID）'}`;
        announcementSelect.appendChild(option);
      });
      if (DATA.latestId) announcementSelect.value = DATA.latestId;
      announcementSelect.disabled = DATA.items.length === 0;
      $('generated-at').textContent = formatDesktopDate(DATA.generatedAt);
    }

    scenario.addEventListener('change', render);
    announcementSelect.addEventListener('change', render);
    $('reload').addEventListener('click', () => location.reload());
    populateControls();
    renderSummary();
    renderManifest();
    renderWarnings();
    render();
  </script>
</body>
</html>
'''


def render_html(data: dict) -> str:
    return HTML_TEMPLATE.replace("__DATA__", _script_json(data))


def main() -> int:
    parser = argparse.ArgumentParser(description="生成两端公告显示本地预览")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="本地公告清单路径")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="输出 HTML 路径")
    parser.add_argument("--no-open", action="store_true", help="只生成文件，不自动打开浏览器")
    args = parser.parse_args()

    try:
        data = build_preview_data(args.manifest)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html(data), encoding="utf-8")
    active_count = sum(item["status"] == "active" for item in data["items"])
    print(f"公告清单：{data['manifestPath']}")
    print(f"公告数量：{len(data['items'])}（启用中 {active_count}）")
    print(f"当前展示：{data['latestId'] or '无'}")
    print(f"预览文件：{output}")
    if data["warnings"]:
        print("校验警告：")
        for warning in data["warnings"]:
            print(f"  - {warning}")
    print("未访问 R2，未上传任何内容。")
    if not args.no_open:
        # Cache-busting query keeps an already-open browser tab from showing a stale preview.
        webbrowser.open(f"{output.as_uri()}?v={int(time.time())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
