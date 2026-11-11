#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把鲸鱼娘立绘处理成墨水屏可用的灰度图。

输入：dsh-whale-widget 的 DSniang1.png（RGBA 彩色立绘）
输出：assets/whale/mascot.png（裁边 + 灰化 + 16 级 Floyd–Steinberg 抖动）

为什么要预渲染而不是在渲染器里现算：
- 看板最终会把整张图量化到 16 级灰，彩色插画直接量化会出现大面积断层；
- 先在素材侧抖动好，再让统一 LUT 原样通过（抖动点落在同一组灰阶上），
  避免"抖动 → 再量化"把网点洗掉。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SRC = Path.home() / ".dsh/profiles/desktop/node_modules/dsh-whale-widget/assets/DSniang1.png"
DEFAULT_OUT = REPO / "assets" / "whale" / "mascot.png"


def fs_dither(gray: np.ndarray, levels: int = 16) -> np.ndarray:
    """Floyd–Steinberg 抖动到固定 levels 级灰阶（与看板 LUT 同网格）。"""
    a = gray.astype(np.float32)
    h, w = a.shape
    step = 255.0 / (levels - 1)
    for y in range(h):
        for x in range(w):
            old = a[y, x]
            new = min(255.0, max(0.0, round(old / step) * step))
            a[y, x] = new
            err = old - new
            if x + 1 < w:
                a[y, x + 1] += err * 7 / 16
            if y + 1 < h:
                if x > 0:
                    a[y + 1, x - 1] += err * 3 / 16
                a[y + 1, x] += err * 5 / 16
                if x + 1 < w:
                    a[y + 1, x + 1] += err * 1 / 16
    return np.clip(a, 0, 255).astype(np.uint8)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--height", type=int, default=300)
    args = ap.parse_args()

    if not args.src.exists():
        raise SystemExit(f"找不到立绘：{args.src}")

    im = Image.open(args.src).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    im = Image.alpha_composite(bg, im).convert("L")

    # 去掉四周大片空白（透明区合成白后的纯白边）
    bbox = Image.eval(im, lambda v: 255 - v).getbbox()
    if bbox:
        pad = 6
        im = im.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                      min(im.width, bbox[2] + pad), min(im.height, bbox[3] + pad)))

    # 等比缩放到目标高度，先锐化一点，避免缩小后线条发糊
    scale = args.height / im.height
    im = im.resize((max(1, int(im.width * scale)), args.height), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    # 拉一下对比：深色头发在 16 级灰里容易糊成一片中灰
    im = ImageOps.autocontrast(im, cutoff=1)

    arr = fs_dither(np.array(im), levels=16)
    out = Image.fromarray(arr, "L")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.save(args.out)
    print(f"{args.out}  {out.size[0]}x{out.size[1]}  {args.out.stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
