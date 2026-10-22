#!/usr/bin/env python
"""从 01 的全窗口原图（2880x1800，DPR=2）裁出角色池详情 02。

用法：python tools/site-shots/pc/crop.py [--pad 12]
"""
import argparse
import json
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = HERE / "raw"
OUT = ROOT / "XKL_site" / "public" / "shots" / "pc"

ap = argparse.ArgumentParser()
ap.add_argument("--pad", type=int, default=12, help="CSS px padding around the character column")
ap.add_argument("--src", default=str(RAW / "01-overview-full.png"))
ap.add_argument("--dst", default=str(OUT / "02-character.png"))
args = ap.parse_args()

meta = json.loads((RAW / "character-rect.json").read_text(encoding="utf-8"))
rect, dpr = meta["rect"], meta["dpr"]

img = Image.open(args.src)
print("source:", args.src, img.size, "dpr:", dpr)

pad = args.pad
x0 = int(round((rect["x"] - pad) * dpr))
y0 = int(round((rect["y"] - pad) * dpr))
x1 = int(round((rect["x"] + rect["width"] + pad) * dpr))
y1 = int(round((rect["y"] + rect["height"] + pad) * dpr))
x0, y0 = max(0, x0), max(0, y0)
x1, y1 = min(img.size[0], x1), min(img.size[1], y1)

box = (x0, y0, x1, y1)
print("crop box:", box, "->", (x1 - x0, y1 - y0))
crop = img.crop(box)
crop.save(args.dst, optimize=True)
print("written:", args.dst, crop.size, f"{Path(args.dst).stat().st_size / 1024:.0f} KB")

# 简单自检：不是空白图，也不是纯背景
colors = crop.convert("RGB").getcolors(maxcolors=1_000_000) or []
nb = sum(c for c, _ in colors if c > 40)
print(f"distinct colors: {len(colors)}, non-background pixels: {nb}")
