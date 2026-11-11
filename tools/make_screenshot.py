#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用演示数据渲染一张 README 用的截图（不含任何真实余额 / 备忘 / token）。"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dashboard_renderer import DashboardRenderer, demo_snapshot, Todo  # noqa: E402
from collectors.whale_usage import DeepSeekUsage                      # noqa: E402


def main() -> int:
    snap = demo_snapshot()
    snap.now = datetime(2026, 11, 11, 17, 8)
    snap.last_updated = snap.now
    snap.todos = [
        Todo("把 Kindle 看板接到桌面，先跑通一版"),
        Todo("SDR 核对"),
        Todo("读《世界因你不同》第三章"),
    ]
    snap.todo_done = 5
    snap.notes = ["日拱一卒，不期速成。今天把看板的刷新对齐到整分钟。"]
    snap.device.pc_online = True
    snap.device.kindle_battery = 94
    snap.device.kindle_charging = False
    snap.device.updated_at = snap.now
    snap.deepseek = DeepSeekUsage(
        available=True,
        balance=42.00,
        today_cost=3.79,
        today_tokens=215_700_000,
        model="deepseek-flash",
        updated_at=snap.now,
        history=[("2026-11-05", 0.8), ("2026-11-06", 8.2), ("2026-11-07", 1.1),
                 ("2026-11-08", 0.4), ("2026-11-09", 0.9), ("2026-11-10", 5.2),
                 ("2026-11-11", 3.8)],
    )

    out = ROOT / "docs" / "screenshot.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    DashboardRenderer().save(snap, str(out))
    print(f"{out}  {out.stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
