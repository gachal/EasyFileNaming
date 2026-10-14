"""生成自诊断样本图:白底黑字「收益分配表」大标题 + 正文/表格行。

一次性脚本(开发机运行,产物入库):
    python scripts/make_sample.py
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",          # macOS
    "/System/Library/Fonts/Hiragino Sans GB.ttc",  # macOS 备选
    "/System/Library/Fonts/STHeiti Light.ttc",
    "C:/Windows/Fonts/msyh.ttc",                   # Win7/10/11 微软雅黑
    "C:/Windows/Fonts/simsun.ttc",                 # Win7 宋体
]

OUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..",
    "src", "easyfilenaming", "resources", "diagnostic_sample.jpg",
)


def find_font() -> str:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    sys.exit("找不到中文字体,请把任一 ttf/ttc 路径加入 FONT_CANDIDATES")


def main() -> None:
    font_path = find_font()
    title_font = ImageFont.truetype(font_path, 64)
    body_font = ImageFont.truetype(font_path, 30)

    img = Image.new("RGB", (1000, 700), "white")
    draw = ImageDraw.Draw(img)

    draw.text((330, 50), "收益分配表", fill="black", font=title_font)
    rows = [
        "编号   姓名   分配金额(元)   签字",
        "001    张三   12,000.00",
        "002    李四   8,500.00",
        "003    王五   6,000.00",
        "合计          26,500.00",
        "制表日期:2026年10月14日",
    ]
    y = 200
    for row in rows:
        draw.text((120, y), row, fill="black", font=body_font)
        y += 70
    draw.rectangle([100, 185, 900, y - 30], outline="black", width=2)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, "JPEG", quality=92)
    print("saved:", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
