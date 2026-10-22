from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "announcements" / "images" / "announcement-wechat-miniapp-launch.png"
OUT.parent.mkdir(parents=True, exist_ok=True)

W, H = 1080, 620
BG = "#121315"
CARD = "#1b1c1f"
CARD_LINE = "#35363b"
GOLD = "#f4cd75"
WHITE = "#f3f3f1"
MUTED = "#a4a6ab"
SOFT = "#d7d8da"
GREEN = "#32d583"
RED = "#ef5350"

FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_BODY = r"C:\Windows\Fonts\Deng.ttf"
FONT_MONO = r"C:\Windows\Fonts\consola.ttf"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size)


def draw_tracked(draw: ImageDraw.ImageDraw, xy, text: str, fnt, fill, spacing: int = 2):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill, anchor="lt")
        x += draw.textlength(ch, font=fnt) + spacing


img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# Subtle background bands.
d.rectangle((0, 0, W, 9), fill="#1a1b1e")
d.rectangle((0, H - 9, W, H), fill="#17181a")

# Outer announcement card.
d.rounded_rectangle((24, 24, 1056, 596), radius=28, fill=CARD, outline=CARD_LINE, width=2)
d.rounded_rectangle((24, 24, 38, 596), radius=7, fill=GOLD)
d.rounded_rectangle((40, 24, 1056, 596), radius=28, fill=CARD)
# Restore a clean left edge while keeping the gold rule visible.
d.rectangle((40, 24, 54, 596), fill=CARD)
d.rounded_rectangle((24, 24, 38, 596), radius=7, fill=GOLD)

# Brand slashes, echoing the existing announcement art.
def slash(x: int, y: int, color: str, shift: int = 0):
    d.polygon(
        [
            (x + 24 + shift, y),
            (x + 43 + shift, y),
            (x + 19 + shift, y + 64),
            (x, y + 64),
        ],
        fill=color,
    )

slash(902, 70, GREEN)
slash(944, 70, GOLD)
slash(986, 70, RED)

# Kicker.
draw_tracked(d, (90, 76), "OFFICIAL RELEASE  ·  WECHAT MINI PROGRAM", font(FONT_MONO, 20), GOLD, 1)
d.line((90, 116, 810, 116), fill="#4a4434", width=2)

# Main headline.
d.text((88, 148), "夏克里助手", font=font(FONT_BOLD, 76), fill=WHITE, anchor="lt")
d.text((88, 240), "微信小程序正式上线", font=font(FONT_BOLD, 58), fill=GOLD, anchor="lt")

# Benefit statement.
d.line((90, 336, 990, 336), fill="#3b3c40", width=2)
d.text((88, 361), "抽卡记录云端长期保存", font=font(FONT_BOLD, 46), fill=WHITE, anchor="lt")
d.text(
    (90, 430),
    "换机 · 清缓存 · 本地文件丢失，也不必担心记录消失",
    font=font(FONT_BODY, 27),
    fill=SOFT,
    anchor="lt",
)

# Feature chips.
chips = [
    ("主动导入", GREEN),
    ("云端留存", GOLD),
    ("概率统计", RED),
    ("图鉴与助战", "#8ab4ff"),
]
x = 90
y = 486
for label, color in chips:
    tw = d.textlength(label, font=font(FONT_BODY, 22))
    w = int(tw + 48)
    d.rounded_rectangle((x, y, x + w, y + 50), radius=25, fill="#26282c", outline="#44474d", width=1)
    d.ellipse((x + 18, y + 21, x + 26, y + 29), fill=color)
    d.text((x + 34, y + 12), label, font=font(FONT_BODY, 22), fill="#e9e9e7", anchor="lt")
    x += w + 14

# Footer.
d.line((90, 554, 990, 554), fill="#303136", width=1)
d.text(
    (90, 565),
    "免费玩家数据工具  ·  数据由用户主动导入  ·  默认仅本人可见",
    font=font(FONT_BODY, 18),
    fill=MUTED,
    anchor="lt",
)
d.text((992, 565), "2026.10.23", font=font(FONT_MONO, 17), fill="#777b83", anchor="rt")

img.save(OUT, "PNG", optimize=True)
print(OUT)
