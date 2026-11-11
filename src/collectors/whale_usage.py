# -*- coding: utf-8 -*-
"""DeepSeek 用量采集器：直接读 dsh-whale-widget 的本地账本。

数据来源：`~/.dsh/.dshw-usage.json`（小鲸鱼挂件在 DSH 界面开着时持续写入）
    {
      "date": "2026-11-11",
      "lastBalance": 379.5,        # 最近一次观测到的余额（元）
      "todayUsage": 15.59,         # 当日已用（元，按余额差记账）
      "history": {"2026-11-10": 6.62, ...},
      "events": [{"ts":…, "day":"…", "model":"deepseek-flash",
                  "cost":0.51, "tokens":7226207}, ...]
    }

不读任何密钥、不联网：余额与 token 都由挂件侧观测/记账，这里只做投影。
所以当 DSH 界面长时间没开时数据会变旧 —— 用 updated_at + stale 如实标注。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

DSH_HOME = Path.home() / ".dsh"
LEDGER_CANDIDATES = [
    DSH_HOME / ".dshw-usage.json",
    DSH_HOME / "profiles" / "web" / ".dshw-usage.json",
]

BEIJING = timezone(timedelta(hours=8))
STALE_AFTER = timedelta(hours=6)


@dataclass
class DeepSeekUsage:
    available: bool = False
    balance: Optional[float] = None
    today_cost: Optional[float] = None
    today_tokens: int = 0
    model: str = ""
    updated_at: Optional[datetime] = None
    history: List[Tuple[str, float]] = field(default_factory=list)
    stale: bool = False
    note: str = ""


def _find_ledger() -> Optional[Path]:
    for p in LEDGER_CANDIDATES:
        if p.exists():
            return p
    return None


def load(path: Optional[Path] = None) -> DeepSeekUsage:
    p = path or _find_ledger()
    if not p or not p.exists():
        return DeepSeekUsage(available=False, note="未找到小鲸鱼账本")

    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return DeepSeekUsage(available=False, note=f"账本读取失败: {e}")

    now = datetime.now(BEIJING)
    today = now.strftime("%Y-%m-%d")

    balance = raw.get("lastBalance")
    ledger_day = raw.get("date")
    today_cost = raw.get("todayUsage")
    if ledger_day != today:
        # 账本是上一天的：今天的支出还没开始记，别拿昨天的数字冒充
        today_cost = 0.0

    events = raw.get("events") or []
    today_events = [e for e in events if e.get("day") == today]
    tokens = sum(int(e.get("tokens") or 0) for e in today_events)
    model = ""
    if today_events:
        model = str(today_events[-1].get("model") or "")

    # 余额是挂件持续轮询写入的：文件 mtime 往往比"最近一条事件"更能反映新鲜度
    stamps = [p.stat().st_mtime]
    stamps += [int(e["ts"]) / 1000 for e in today_events if e.get("ts")]
    updated = datetime.fromtimestamp(max(stamps), BEIJING)

    hist = []
    h = raw.get("history") or {}
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        hist.append((day, float(h.get(day, 0.0))))

    stale = (now - updated) > STALE_AFTER

    return DeepSeekUsage(
        available=True,
        balance=float(balance) if balance is not None else None,
        today_cost=float(today_cost) if today_cost is not None else None,
        today_tokens=tokens,
        model=model,
        updated_at=updated,
        history=hist,
        stale=stale,
    )


def human_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1000:.0f}K"
    return str(n)
