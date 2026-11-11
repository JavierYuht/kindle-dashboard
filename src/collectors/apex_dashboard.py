# -*- coding: utf-8 -*-
"""Apex Dashboard（Obsidian 插件）采集器。

用户的 vault 用 Apex Dashboard 把「Memo / Todo / Projects / Library」写在一个
`dashboard.md` 里，卡片形如：

    ## Todo

    ### To-Do
    id: card-msr2zkno
    type: task
    - [ ] 仔细计算东方财富做T成本

    ## Memo

    ### 2026-05-24 memo
    id: demo-memo-1
    type: memo
    一段备忘正文……

这里只做只读解析：拿未完成待办喂 O-04，拿备忘录喂 N-02。
不做写回、不猜优先级（Apex 的卡片没有优先级字段）。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

DEFAULT_PATH = Path.home() / "Obsidian" / "Library-yuht" / "dashboard.md"

_ITEM_RE = re.compile(r"^\s*[-*]\s*\[( |x|X)\]\s*(.+?)\s*$")
_DUE_RE = re.compile(r"(?:📅|到期[:：]?|due[:：]?)\s*(\d{4}-\d{2}-\d{2})")
_META_RE = re.compile(r"^\s*(id|type|color|width|height|icon)\s*:", re.I)


@dataclass
class ApexTodo:
    title: str
    due_text: str = ""
    priority: str = ""
    overdue: bool = False
    card_idx: int = 0


@dataclass
class ApexDashboard:
    available: bool = False
    todos: List[ApexTodo] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    done: int = 0
    path: str = ""
    note: str = ""


def _parse_due(text: str) -> tuple[str, bool]:
    m = _DUE_RE.search(text)
    if not m:
        return "", False
    try:
        d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except ValueError:
        return "", False
    today = datetime.now().date()
    return d.strftime("%m-%d"), d < today


def load(path: Optional[Path] = None) -> ApexDashboard:
    p = path or Path(os.environ.get("APEX_DASHBOARD_PATH", DEFAULT_PATH))
    if not p.exists():
        return ApexDashboard(available=False, note=f"未找到 {p}")

    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        return ApexDashboard(available=False, note=str(e))

    column = ""
    card = ""
    card_idx = 0
    todos: List[ApexTodo] = []
    memo_blocks: List[tuple] = []      # (card_idx, card_title, text)
    memo_buf: List[str] = []
    done = 0

    def flush_memo():
        nonlocal memo_buf
        text = " ".join(x.strip() for x in memo_buf if x.strip())
        if text:
            memo_blocks.append((card_idx, card, text))
        memo_buf = []

    for line in lines:
        if line.startswith("## "):
            flush_memo()
            column = line[3:].strip()
            card = ""
            continue
        if line.startswith("### "):
            flush_memo()
            card = line[4:].strip()
            card_idx += 1
            continue
        if _META_RE.match(line) or line.startswith("---"):
            continue

        m = _ITEM_RE.match(line)
        if m and column.lower() == "todo":
            checked = m.group(1).lower() == "x"
            text = m.group(2)
            if checked:
                done += 1
                continue
            due_text, overdue = _parse_due(text)
            clean = _DUE_RE.sub("", text).strip()
            todos.append(ApexTodo(title=clean, due_text=due_text,
                                  overdue=overdue, card_idx=card_idx))
            continue

        # Memo 列：收集正文，忽略空行
        if column.lower().startswith("memo") and line.strip():
            memo_buf.append(line.strip())

    flush_memo()

    # 只保留最新的一张备忘卡：优先按标题里的日期，没有日期就按卡片先后
    def key(block):
        idx, title, _ = block
        m = re.search(r"(\d{4}-\d{2}-\d{2})", title or "")
        return (m.group(1) if m else "", idx)

    notes = []
    if memo_blocks:
        notes = [max(memo_blocks, key=key)[2]]

    # 待办按卡片从新到旧排，最新的先看到
    todos.sort(key=lambda t: -t.card_idx)

    return ApexDashboard(
        available=True,
        todos=todos,
        notes=notes,
        done=done,
        path=str(p),
    )
