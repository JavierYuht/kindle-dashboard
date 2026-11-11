# -*- coding: utf-8 -*-
"""
Kindle 工作控制台 · HUD 风格渲染器

目标设备：Kindle Paperwhite 3，竖屏 1072 x 1448，16 级灰度。

设计参考：机甲/HUD 模块化仪表盘
- 粗黑边框 + 模块编号标签
- 顶部：位置 / 主显示 / 系统状态
- 24 小时天气扫描条
- 日历 / 笔记 / 待办 / Token 用量
- 底部快捷图标栏

输出：8bit 灰度 PNG（colortype 0），渲染阶段主动量化到 16 级。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1072
HEIGHT = 1448
GRAY_LEVELS = 16

# 16 级灰阶调色板
BLACK = 0
INK = 32
GRAY_DARK = 96
GRAY_MID = 140
GRAY_LIGHT = 200
GRAY_FAINT = 235
WHITE = 255

# 天气图标精灵图目录（由 tools/build_weather_icons.py 预生成）
ASSET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
)
WEATHER_ICON_DIR = os.path.join(ASSET_DIR, "weather_icons")
MASCOT_PATH = os.path.join(ASSET_DIR, "whale", "mascot.png")
# 旧友好的天气名 → QWeather 天气代码（和风天气 API 直接返回数字代码）
NAME_TO_QWEATHER = {
    "sunny": "100", "clear": "100", "fine": "100",
    "partly": "103", "few": "102",
    "cloudy": "101", "overcast": "104",
}

MARGIN = 44
GAP = 22
PANEL_BORDER = 2
TITLE_H = 44
PAD = 18

# 每项为 (粗体, 常规)；元素可以是路径，或 (路径, TTC 索引)
FONT_CANDIDATES = [
    ("C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc"),   # 微软雅黑
    ("C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simhei.ttf"), # 黑体
    # macOS：冬青黑体 W6(粗) / W3(常规)，同文件不同 face
    (("/System/Library/Fonts/Hiragino Sans GB.ttc", 2),
     ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0)),
    # macOS 备选：宋体-简 粗体 / 常规体
    (("/System/Library/Fonts/Supplemental/Songti.ttc", 1),
     ("/System/Library/Fonts/Supplemental/Songti.ttc", 6)),
]


# ------------------------------------------------------------------ 数据模型
@dataclass
class Weather:
    location: str = "上海市黄浦区"
    temp_now: Optional[int] = None
    temp_high: Optional[int] = None
    temp_low: Optional[int] = None
    text: str = "—"
    icon_code: Optional[str] = None
    observed_at: Optional[datetime] = None
    stale: bool = False


@dataclass
class HourlyWeather:
    hour: str = "12:00"
    temp: int = 25
    icon_code: str = "sunny"       # sunny / cloudy / partly / overcast


@dataclass
class SysStatusItem:
    label: str = ""
    value: str = ""
    ratio: float = 0.0             # 0.0 - 1.0，用于右侧小条


@dataclass
class Quota:
    label: str = ""
    remain_ratio: float = 0.0
    reset_text: str = ""
    stale: bool = False


@dataclass
class CodexTask:
    title: str = ""
    state: str = "idle"
    state_text: str = "空闲"
    elapsed: str = ""
    last_progress: str = ""


@dataclass
class Intervention:
    level: str = ""
    title: str = ""
    detail: str = ""


@dataclass
class Todo:
    title: str
    due_text: str = ""
    priority: str = ""
    overdue: bool = False


@dataclass
class TokenUsage:
    name: str = ""
    usage_ratio: float = 0.0       # 已用比例
    status: str = ""             # 右侧主状态文字，如 剩96% / 需终端
    detail: str = ""             # 与 status 合并到顶行的短补充，如 5h窗口
    note: str = ""              # 进度条下方小字补充，如 累计88.0M（不与顶行冲突）
    weekly_ratio: float = 0.0    # 周窗口已用比例（Codex secondary），同一行内子条
    weekly_remaining: int = 0    # 周窗口剩余百分比，如 2
    weekly_reset: str = ""       # 周窗口重置文字，如 约5d后重置
    weekly_status: str = ""      # 周窗口状态文字（覆盖 weekly_remaining）。如「额度未知」
                                 # 表示 Codex 主额度拿不到、但仍要画一条「额度未知·周窗口」子条


@dataclass
class BottomIcon:
    label: str = ""
    icon_type: str = "circle"      # command / gear / auto / wifi / number / board


@dataclass
class DeviceStatus:
    pc_online: bool = True
    kindle_battery: Optional[int] = None
    kindle_charging: bool = False
    updated_at: Optional[datetime] = None


@dataclass
class Snapshot:
    now: datetime = field(default_factory=datetime.now)
    last_updated: Optional[datetime] = None   # 数据最后刷新时间，供 SYS STATUS 显示
    weather: Weather = field(default_factory=Weather)
    hourly_weather: List[HourlyWeather] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    make_summary: List[str] = field(default_factory=list)  # 今日日记「搞点什么」区块概要
    sys_status: List[SysStatusItem] = field(default_factory=list)
    tokens: List[TokenUsage] = field(default_factory=list)
    # DeepSeek 用量（collectors.whale_usage.DeepSeekUsage，鸭子类型，避免渲染器反向依赖采集器）
    deepseek: object = None
    todos: List[Todo] = field(default_factory=list)
    todo_done: int = 0
    bottom_icons: List[BottomIcon] = field(default_factory=list)
    # 旧字段保留，避免外部引用报错
    intervention: Optional[Intervention] = None
    codex: CodexTask = field(default_factory=CodexTask)
    quotas: List[Quota] = field(default_factory=list)
    device: DeviceStatus = field(default_factory=DeviceStatus)
    page: int = 1
    page_count: int = 3


# ------------------------------------------------------------------ 渲染器
class DashboardRenderer:
    def __init__(self, width: int = WIDTH, height: int = HEIGHT,
                 gray_levels: int = GRAY_LEVELS):
        self.w = width
        self.h = height
        self.gray_levels = gray_levels
        self._fonts()

        # 16 级量化查找表
        step = 255.0 / (gray_levels - 1)
        self._lut = [int(round(round(v / step) * step)) for v in range(256)]

        # 天气图标精灵图缓存
        self._sprite_cache: dict = {}
        # 鲸鱼娘立绘缓存（None=未加载，False=素材缺失）
        self._mascot_cache = None

    # ---- 字体 ----
    def _fonts(self):
        def spec(p):
            return (p, 0) if isinstance(p, str) else p

        bold_path = regular_path = None
        for b, r in FONT_CANDIDATES:
            b, r = spec(b), spec(r)
            if os.path.exists(b[0]) and os.path.exists(r[0]):
                bold_path, regular_path = b, r
                break
        if bold_path is None:
            raise RuntimeError("未找到中文字体（msyh/simhei 或 macOS 冬青黑体）")

        self._bold_spec = bold_path

        def mk(size):
            return ImageFont.truetype(regular_path[0], size,
                                     index=regular_path[1])

        def mkb(size):
            return ImageFont.truetype(bold_path[0], size, index=bold_path[1])

        self.f_title = mkb(20)           # 模块标题
        self.f_code = mkb(18)            # 编号标签
        self.f_time = mkb(86)            # 主时间
        self.f_date = mk(26)             # 日期
        self.f_temp_big = mkb(56)        # 当前温度
        self.f_clock = mkb(48)           # 最近更新时间大数字
        self.f_temp = mkb(26)            # 小时温度
        self.f_weather = mk(24)          # 天气文字
        self.f_mode = mkb(48)            # AUTO 等模式字
        self.f_status = mk(22)           # 状态小字
        self.f_body = mk(26)             # 正文
        self.f_body_b = mkb(26)          # 正文粗
        self.f_small = mk(22)            # 小字
        self.f_tiny = mk(20)             # 极小字
        self.f_icon = mk(20)             # 底部图标文字
        self.f_label = mk(21)            # 模块名（常规字重，安静）
        self.f_hero = mkb(94)            # 时钟 / 电量
        self.f_huge = mkb(112)           # 温度
        self.f_num = mkb(62)             # DeepSeek 余额
        self.f_hour = mkb(30)            # 逐时温度
        self.f_tag = mkb(16)             # 模块编号牌

    # ---- 工具 ----
    def _bold(self, size):
        return ImageFont.truetype(self._bold_spec[0], size,
                                  index=self._bold_spec[1])

    def _fit(self, draw, text, font, max_w):
        if not text:
            return ""
        if draw.textlength(text, font=font) <= max_w:
            return text
        ell = "…"
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if draw.textlength(text[:mid] + ell, font=font) <= max_w:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo] + ell

    def _wrap_text(self, draw, text, font, max_w, max_lines=6):
        """按像素宽度做贪心换行：
        - 中文逐字可断；
        - 英文/数字等连续非 CJK 序列按词边界保持完整；
        - 超过 max_lines 时，最后一行用 _fit 截断并加省略号。
        """
        if not text:
            return []

        # 拆分为最小排版单元：单个 CJK 字符（含中文标点），或一段连续非 CJK 文本
        tokens = re.findall(
            r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]|\s+|[^\s\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]+",
            text)

        lines = []
        cur = ""
        for idx, tok in enumerate(tokens):
            if tok == "\n":
                lines.append(cur)
                cur = ""
                if len(lines) >= max_lines:
                    break
                continue

            trial = cur + tok
            if draw.textlength(trial, font=font) <= max_w:
                cur = trial
                continue

            # tok 单放不进空行：必须拆（通常是超长 URL/无空格英文）
            if not cur and draw.textlength(tok, font=font) > max_w:
                # 对该 token 逐字强断
                for ch in tok:
                    if draw.textlength(cur + ch, font=font) <= max_w:
                        cur += ch
                    else:
                        if cur:
                            lines.append(cur)
                        cur = ch
                        if len(lines) >= max_lines:
                            break
                continue

            # 正常换行
            if cur:
                lines.append(cur.rstrip())
            cur = tok
            if len(lines) >= max_lines - 1:
                # 已到最后一行允许空间，剩余内容截断加省略号
                remaining = "".join(tokens[idx:])
                cur = self._fit(draw, remaining, font, max_w)
                break

        if cur:
            lines.append(cur)
        return lines[:max_lines]

    def _draw_bulleted_items(self, draw, entries, x0, y0, x1, y1, cy,
                             *, font, max_lines=4, line_h=32, indent=20,
                             dot_r=3, gap=4):
        """绘制带项目符号的多条文本：每条自动换行（CJK 友好），符号置于首行左。
        返回新的 cy（已累加留白）。超出面板底边 y1 时停止绘制以免溢出。"""
        for entry in entries:
            if cy > y1 - 24:
                break
            wrapped = self._wrap_text(draw, entry, font,
                                      (x1 - x0) - indent, max_lines=max_lines)
            if not wrapped:
                continue
            # 项目符号：小实心圆，与第一行文字垂直居中
            dot_cx = x0 + dot_r + 2
            dot_cy = cy + 13
            draw.ellipse((dot_cx - dot_r, dot_cy - dot_r,
                          dot_cx + dot_r, dot_cy + dot_r), fill=INK)
            for ln in wrapped:
                if cy > y1 - 24:
                    break
                draw.text((x0 + indent, cy), ln, font=font, fill=INK)
                cy += line_h
            cy += gap   # 条目间留白
        return cy

    def _quantize(self, img: Image.Image) -> Image.Image:
        return img.point(self._lut)

    def _panel_frame(self, draw, box, title="", tag="", right="", fill=WHITE):
        """日系卡片：圆角 + 1px 浅灰描边，标题只做安静的左上角注记。"""
        x0, y0, x1, y1 = box
        draw.rounded_rectangle(box, radius=18, outline=GRAY_MID, width=2,
                               fill=fill)
        if title:
            draw.text((x0 + 26, y0 + 26), title, font=self.f_label,
                      fill=GRAY_DARK, anchor="lm")
        return (x0 + 26, y0 + 54, x1 - 26, y1 - 22)

    def _progress_bar(self, draw, box, ratio, fill=BLACK, back=GRAY_LIGHT,
                      border=BLACK, height=22):
        """粗边框进度条。"""
        x0, y0, x1, y1 = box
        # 槽
        draw.rectangle((x0, y0, x1, y0 + height), outline=border,
                       width=2, fill=back)
        ratio = max(0.0, min(1.0, ratio))
        inner_w = x1 - x0 - 4
        if ratio > 0 and inner_w > 0:
            fw = max(4, int(inner_w * ratio))
            draw.rectangle((x0 + 2, y0 + 2, x0 + 2 + fw, y0 + height - 2),
                           fill=fill)

    def _segmented_bar(self, draw, box, ratio, n=20, gap=3, cell_h=20,
                       used=BLACK, unused=GRAY_LIGHT, border=BLACK):
        """格子组成的长条：已用部分黑格，未用部分灰格。"""
        x0, y0, x1, _y1 = box
        ratio = max(0.0, min(1.0, ratio))
        inner_w = x1 - x0
        if inner_w <= 0 or n <= 0:
            return
        cell_w = (inner_w - gap * (n - 1)) / n
        if cell_w <= 0:
            return
        used_n = int(round(ratio * n))
        for i in range(n):
            cx = x0 + i * (cell_w + gap)
            ix0 = int(round(cx))
            ix1 = int(round(cx + cell_w))
            fill = used if i < used_n else unused
            draw.rectangle((ix0, y0, ix1, y0 + cell_h), fill=fill,
                           outline=border, width=1)

    def _checkbox(self, draw, x, y, size=22, checked=False):
        """方框复选框。"""
        draw.rounded_rectangle((x, y, x + size, y + size), radius=4,
                               outline=GRAY_DARK, width=2, fill=WHITE)
        if checked:
            # 画对勾
            draw.line([(x + 4, y + size // 2), (x + size // 3, y + size - 4),
                       (x + size - 3, y + 4)], fill=BLACK, width=3)

    # ---- 天气图标（QWeather 精灵图） ----
    def _weather_sprite(self, code):
        """读取预生成的 QWeather 图标精灵图（黑色实心、透明底）。"""
        if code in self._sprite_cache:
            return self._sprite_cache[code]
        sprite = None
        path = os.path.join(WEATHER_ICON_DIR, f"{code}.png")
        if os.path.exists(path):
            sprite = Image.open(path).convert("RGBA")
        self._sprite_cache[code] = sprite
        return sprite

    def _draw_weather_icon(self, img, cx, cy, size, code):
        """把 QWeather 精灵图按 size（最长边）等比贴到 img 上，黑色实心、透明底。"""
        code = NAME_TO_QWEATHER.get(code, code)
        sprite = self._weather_sprite(code)
        if sprite is None:
            # 缺图标时画占位圆，避免空白
            d = ImageDraw.Draw(img)
            r = size // 2
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=BLACK, width=2)
            return
        w, h = sprite.size
        scale = min(size / w, size / h)
        nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
        sp = sprite.resize((nw, nh), Image.LANCZOS)
        x = int(round(cx - nw / 2))
        y = int(round(cy - nh / 2))
        mask = sp.split()[-1]
        img.paste(0, (x, y, x + nw, y + nh), mask=mask)

    def _bottom_icon(self, draw, cx, cy, size, icon_type):
        """底部圆形图标。"""
        r = size // 2
        # 外框
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=BLACK,
                     width=3, fill=GRAY_FAINT)
        # 内部符号
        if icon_type == "command":
            # 三角播放
            draw.polygon([(cx - 5, cy - 7), (cx + 7, cy), (cx - 5, cy + 7)],
                         fill=BLACK)
        elif icon_type == "gear":
            draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), outline=BLACK, width=2)
            for angle in range(0, 360, 45):
                import math
                a = math.radians(angle)
                x1 = cx + int(6 * math.cos(a))
                y1 = cy + int(6 * math.sin(a))
                x2 = cx + int(9 * math.cos(a))
                y2 = cy + int(9 * math.sin(a))
                draw.line((x1, y1, x2, y2), fill=BLACK, width=2)
        elif icon_type == "auto":
            draw.text((cx, cy), "A", font=self.f_body_b, fill=BLACK, anchor="mm")
        elif icon_type == "wifi":
            # 弧线
            for i, arc_r in enumerate((4, 7, 10)):
                draw.arc((cx - arc_r, cy - arc_r, cx + arc_r, cy + arc_r),
                         start=-45, end=45, fill=BLACK, width=2)
        elif icon_type == "number":
            draw.text((cx, cy), "256", font=self.f_tiny, fill=BLACK, anchor="mm")
        elif icon_type == "board":
            draw.rectangle((cx - 6, cy - 5, cx + 6, cy + 5), outline=BLACK, width=2)
            draw.line((cx - 6, cy + 1, cx + 6, cy + 1), fill=BLACK, width=1)
        else:
            draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=BLACK)

    # ---- 各区块 ----
    def _soft_bar(self, draw, box, ratio, height=12, track=GRAY_LIGHT,
                  fill=BLACK, radius=6):
        """圆角细进度条，替代原来的格子条。"""
        x0, y0, x1, y1 = box
        ratio = max(0.0, min(1.0, ratio))
        draw.rounded_rectangle((x0, y0, x1, y0 + height), radius=radius,
                               fill=track)
        w = int((x1 - x0) * ratio)
        if w > height:
            draw.rounded_rectangle((x0, y0, x0 + w, y0 + height),
                                   radius=radius, fill=fill)

    def _panel_location(self, draw, box, weather, img):
        x0, y0, x1, y1 = self._panel_frame(
            draw, box, weather.location or "位置")
        cxp = (x0 + x1) // 2
        avail = x1 - x0

        t = "—" if weather.temp_now is None else f"{weather.temp_now}°"
        icon_size, gap = 56, 12
        f = self.f_huge
        for size in (108, 96, 84, 72):
            f = self._bold(size)
            if icon_size + gap + draw.textlength(t, font=f) <= avail:
                break
        tw = draw.textlength(t, font=f)

        row_cy = y0 + 88
        start = cxp - (icon_size + gap + tw) / 2
        self._draw_weather_icon(img, start + icon_size / 2, row_cy,
                                icon_size, weather.icon_code or "100")
        draw.text((start + icon_size + gap, row_cy), t, font=f,
                  fill=BLACK, anchor="lm")

        sub = weather.text or ""
        if weather.temp_high is not None and weather.temp_low is not None:
            sub = f"{sub}  {weather.temp_low}° / {weather.temp_high}°"
        sub = self._fit(draw, sub.strip(), self.f_weather, avail)
        draw.text((cxp, y1 - 4), sub, font=self.f_weather,
                  fill=GRAY_DARK, anchor="mb")

    def _panel_main_display(self, draw, box, snap):
        x0, y0, x1, y1 = self._panel_frame(draw, box, "当前时间")
        lu = snap.now
        ts = lu.strftime("%H:%M")
        f = self.f_hero
        if draw.textlength(ts, font=f) > (x1 - x0) + 6:
            f = self._bold(82)
        draw.text((x0 - 3, y0 + 22), ts, font=f, fill=BLACK)

        week = "一二三四五六日"[lu.weekday()]
        draw.text((x0, y0 + 152), f"{lu.month}月{lu.day}日",
                  font=self.f_body, fill=BLACK)
        # 星期跟日期同一行右侧，省一行高度
        draw.text((x1, y0 + 152), f"周{week}", font=self.f_body,
                  fill=GRAY_DARK, anchor="ra")

        on = snap.device.pc_online
        cy = y0 + 202
        draw.ellipse((x0, cy - 6, x0 + 12, cy + 6), fill=BLACK if on else WHITE,
                     outline=BLACK, width=2)
        draw.text((x0 + 22, cy), "PC 在线" if on else "离线缓存",
                  font=self.f_small, fill=GRAY_DARK, anchor="lm")

    def _panel_sys_status(self, draw, box, snap):
        x0, y0, x1, y1 = self._panel_frame(draw, box, "KINDLE 电量")
        batt = snap.device.kindle_battery
        charging = snap.device.kindle_charging

        big = "—" if batt is None else f"{int(batt)}%"
        ratio = 0.0 if batt is None else max(0.0, min(1.0, batt / 100.0))
        draw.text((x0 - 3, y0 + 30), big, font=self.f_hero, fill=BLACK)

        bar_y = y0 + 152
        self._segmented_bar(draw, (x0, bar_y, x1, bar_y), ratio,
                            n=18, gap=3, cell_h=18)

        cy = bar_y + 40
        if batt is None:
            status = "看板端待上报电量"
        else:
            status = "充电中" if charging else "未充电"
            if snap.device.updated_at:
                status += f" · 上报 {snap.device.updated_at:%H:%M}"
        draw.text((x0, cy), status, font=self.f_small, fill=GRAY_DARK)

    def _panel_hourly_weather(self, draw, box, hourly, img):
        x0, y0, x1, y1 = self._panel_frame(draw, box, "6 小时预报")
        if not hourly:
            return

        n = len(hourly)
        item_w = (x1 - x0) / n
        for i, h in enumerate(hourly):
            ix = x0 + item_w * (i + 0.5)
            draw.text((ix, y0 + 2), h.hour, font=self.f_small,
                      fill=GRAY_MID, anchor="mt")
            self._draw_weather_icon(img, ix, y0 + 50, 42, h.icon_code)
            draw.text((ix, y0 + 82), f"{h.temp}°", font=self.f_hour,
                      fill=BLACK, anchor="mt")

    def _placeholder_removed(self):
        pass

    def _panel_notes(self, draw, box, notes):
        x0, y0, x1, y1 = self._panel_frame(draw, box, "笔记")
        if not notes:
            draw.text((x0, y0 + 4), "暂无内容", font=self.f_body, fill=GRAY_LIGHT)
            return

        # 先排好行，再整体垂直居中，避免只有一条时孤零零贴在顶上
        blocks = []
        for note in notes[:4]:
            lines = self._wrap_text(draw, note, self.f_body, x1 - x0 - 24,
                                    max_lines=3)
            if lines:
                blocks.append(lines)

        lh, block_gap = 42, 16
        total = sum(lh * len(b) for b in blocks) + block_gap * (len(blocks) - 1)
        cy = y0

        for lines in blocks:
            # 一条备忘只给一个圆点，别每换一行就补一个
            draw.ellipse((x0, cy + 16, x0 + 8, cy + 24), fill=GRAY_DARK)
            for ln in lines:
                draw.text((x0 + 22, cy), ln, font=self.f_body, fill=BLACK)
                cy += lh
            cy += block_gap

    def _panel_todo(self, draw, box, todos):
        x0, y0, x1, y1 = self._panel_frame(draw, box, "待办")

        if not todos:
            draw.text((x0, y0 + 4), "没有待办", font=self.f_body, fill=GRAY_LIGHT)
        else:
            done_rows = getattr(self, "_todo_done", 0)
            limit = y1 - (34 if done_rows else 6)
            cy = y0 + 4
            for t in todos[:8]:
                lines = self._wrap_text(draw, t.title, self.f_body,
                                        x1 - x0 - 40, max_lines=2)
                need = 36 * len(lines) + 16
                # 放不下整条就停，别把字压到"已完成"那行上
                if cy + need > limit:
                    break
                self._checkbox(draw, x0, cy + 5, size=18)
                for ln in lines:
                    draw.text((x0 + 36, cy), ln, font=self.f_body, fill=BLACK)
                    cy += 36
                if t.due_text:
                    draw.text((x1, cy - 36), t.due_text, font=self.f_small,
                              fill=GRAY_DARK, anchor="ra")
                cy += 16

        done = getattr(self, "_todo_done", 0)
        if done:
            draw.text((x0, y1 - 12), f"已完成 {done} 项", font=self.f_tiny,
                      fill=GRAY_MID, anchor="lm")

    def _placeholder_removed(self):
        pass

    def _mascot(self):
        if self._mascot_cache is None:
            img = False
            if os.path.exists(MASCOT_PATH):
                img = Image.open(MASCOT_PATH).convert("L")
            self._mascot_cache = img
        return self._mascot_cache or None

    @staticmethod
    def _human_tokens(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1000:.0f}K"
        return str(n)

    def _todo_height(self, draw, todos, wrap_w, lo=222, hi=360):
        """待办面板高度：按真实换行行数算，长条目不会把 footer 挤掉。"""
        if not todos:
            return lo
        total = 0
        for t in todos[:8]:
            lines = self._wrap_text(draw, t.title, self.f_body, wrap_w, max_lines=2)
            total += 36 * len(lines) + 16
        need = 54 + 22 + total + (34 if self._todo_done else 0) + 8
        return int(max(lo, min(hi, need)))

    def _notes_height(self, draw, notes, wrap_w, lo=136, hi=320):
        """按实际行数算笔记面板高度：内容少就是一条窄带，内容多才撑高。"""
        if not notes:
            return lo
        total = 0
        for note in notes[:4]:
            lines = self._wrap_text(draw, note, self.f_body, wrap_w, max_lines=3)
            if lines:
                total += 42 * len(lines) + 16
        return int(max(lo, min(hi, total + 26)))

    def _status_strip(self, draw, box, snap):
        """底部只留一行安静的注记，不做状态栏。"""
        x0, y0, x1, y1 = box
        batt = snap.device.kindle_battery
        parts = ["在线" if snap.device.pc_online else "离线"]
        if batt is not None:
            parts.append(f"{int(batt)}%")
        if snap.last_updated:
            parts.append(f"同步 {snap.last_updated:%H:%M}")
        text = "   ·   ".join(parts)
        draw.text(((x0 + x1) / 2, (y0 + y1) / 2), text, font=self.f_small,
                  fill=GRAY_MID, anchor="mm")

    def _panel_deepseek(self, draw, box, d, img):
        x0, y0, x1, y1 = self._panel_frame(draw, box, "DeepSeek")

        if d is None or not getattr(d, "available", False):
            draw.text((x0, y0 + 4), "小鲸鱼账本未就绪", font=self.f_body, fill=BLACK)
            draw.text((x0, y0 + 44), "打开一次 DSH 界面即会生成账本",
                      font=self.f_small, fill=GRAY_DARK)
            return

        # 左列：立绘
        m = self._mascot()
        mid_x = x0
        if m is not None:
            mh = min(340, y1 - y0 - 6)
            scale = mh / m.height
            mm = m.resize((int(m.width * scale), mh), Image.LANCZOS)
            img.paste(mm, (x0, y0))
            mid_x = x0 + mm.width + 24

        # 中列：余额 / 今日
        bar_x = x0 + int((x1 - x0) * 0.66)
        draw.text((mid_x, y0 + 2), "余额 BALANCE", font=self.f_tiny, fill=GRAY_MID)
        bal = f"¥{d.balance:.2f}" if d.balance is not None else "—"
        bf = self.f_num
        if draw.textlength(bal, font=bf) > (bar_x - mid_x - 20):
            bf = self._bold(48)
        draw.text((mid_x, y0 + 26), bal, font=bf, fill=BLACK)

        y = y0 + 108
        cost = f"¥{d.today_cost:.2f}" if d.today_cost is not None else "—"
        draw.text((mid_x, y), "今日已用", font=self.f_small, fill=GRAY_DARK)
        draw.text((bar_x - 24, y - 4), cost, font=self.f_body_b, fill=BLACK, anchor="ra")
        y += 38
        draw.text((mid_x, y), "今日 Token", font=self.f_small, fill=GRAY_DARK)
        draw.text((bar_x - 24, y - 4), self._human_tokens(d.today_tokens),
                  font=self.f_body_b, fill=BLACK, anchor="ra")

        # 右列：近 7 日
        draw.line((bar_x, y0, bar_x, y1), fill=GRAY_LIGHT, width=1)
        hist = list(getattr(d, "history", []) or [])
        if len(hist) >= 2:
            bx0 = bar_x + 24
            draw.text((bx0, y0 + 2), "近 7 日", font=self.f_tiny, fill=GRAY_MID)
            up = d.updated_at.strftime("%H:%M") if getattr(d, "updated_at", None) else "--:--"
            tail = f"更新 {up}" + (" · 偏旧" if getattr(d, "stale", False) else "")
            draw.text((x1, y0 + 2), tail, font=self.f_tiny, fill=GRAY_MID, anchor="ra")

            top = y0 + 34
            base = y1 - 26
            n = len(hist)
            slot = (x1 - bx0) // n
            mx = max((c for _, c in hist), default=0.0) or 1.0
            for i, (day, c) in enumerate(hist):
                bh = int((base - top) * (c / mx)) if c > 0 else 0
                bx = bx0 + i * slot + 6
                bw = max(8, slot - 16)
                if bh > 2:
                    fill = BLACK if i == n - 1 else GRAY_LIGHT
                    draw.rounded_rectangle((bx, base - bh, bx + bw, base),
                                           radius=4, fill=fill)
                draw.text((bx + bw // 2, base + 4), day[-2:],
                          font=self.f_tiny, fill=GRAY_DARK, anchor="ma")

    def _bottom_bar(self, draw, box, icons):
        x0, y0, x1, y1 = box
        # 顶部分隔线
        draw.line((x0, y0, x1, y0), fill=BLACK, width=3)

        if not icons:
            return

        n = len(icons)
        icon_w = (x1 - x0) // n
        for i, ic in enumerate(icons):
            cx = x0 + i * icon_w + icon_w // 2
            cy = y0 + 10 + (y1 - y0 - 20) // 2
            self._bottom_icon(draw, cx, cy - 10, 44, ic.icon_type)
            draw.text((cx, y1 - 18), ic.label, font=self.f_icon, fill=BLACK,
                      anchor="mm")

    # ---- 主渲染 ----
    def render(self, snap: Snapshot) -> Image.Image:
        img = Image.new("L", (self.w, self.h), WHITE)
        draw = ImageDraw.Draw(img)

        x0, x1 = MARGIN, self.w - MARGIN
        y = MARGIN

        # 顶部三栏：等宽（照 GitHub 项目的三栏比例）
        top_h = 286
        col_w = (x1 - x0 - GAP * 2) // 3
        self._panel_location(draw, (x0, y, x0 + col_w, y + top_h),
                             snap.weather, img)
        self._panel_main_display(draw, (x0 + col_w + GAP, y,
                                        x0 + 2 * col_w + GAP, y + top_h), snap)
        self._panel_sys_status(draw, (x0 + 2 * (col_w + GAP), y, x1, y + top_h),
                               snap)
        y += top_h + GAP

        # 逐时天气
        hourly_h = 184
        self._panel_hourly_weather(draw, (x0, y, x1, y + hourly_h),
                                   snap.hourly_weather, img)
        y += hourly_h + GAP

        # 笔记 + 待办：横向并列
        half = (x1 - x0 - GAP) // 2
        wrap_w = half - 2 * PAD - 24
        notes_need = self._notes_height(draw, snap.notes, wrap_w, lo=222, hi=322)
        self._todo_done = snap.todo_done
        todo_need = self._todo_height(draw, snap.todos, half - 2 * PAD - 40)
        row_h = max(notes_need, todo_need)
        self._panel_notes(draw, (x0, y, x0 + half, y + row_h), snap.notes)
        self._panel_todo(draw, (x0 + half + GAP, y, x1, y + row_h), snap.todos)
        y += row_h + GAP

        status_top = self.h - MARGIN

        # DeepSeek 整行，吃满剩余高度
        ds_h = status_top - GAP - y
        self._panel_deepseek(draw, (x0, y, x1, y + ds_h), snap.deepseek, img)

        return self._quantize(img)

    def save(self, snap: Snapshot, path: str) -> str:
        img = self.render(snap)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        img.save(path, "PNG", optimize=True)
        return path


# ------------------------------------------------------------------ 演示数据

def demo_snapshot() -> Snapshot:
    """按示例图构造假数据，不读取任何真实账户信息。"""
    return Snapshot(
        now=datetime(2026, 7, 30, 8, 59),
        last_updated=datetime(2026, 7, 30, 8, 58, 17),
        weather=Weather(
            location="上海 · 嘉定",
            temp_now=34,
            temp_high=37,
            temp_low=28,
            text="晴",
            icon_code="100",
        ),
        hourly_weather=[
            HourlyWeather("09:00", 34, "100"),
            HourlyWeather("10:00", 35, "103"),
            HourlyWeather("11:00", 36, "103"),
            HourlyWeather("12:00", 37, "101"),
            HourlyWeather("13:00", 37, "101"),
            HourlyWeather("14:00", 37, "104"),
        ],
        sys_status=[
            SysStatusItem("MODE", "AUTO", 0.0),
            SysStatusItem("AVAILABLE", "", 0.65),
        ],
        notes=[
            "虽然名义叫第二块屏幕，但 Kindle 只负责安静地显示最后一个有效版本，不承载任何交互。",
            "MOC 负责思考与排期，把结构化结论推送到设备；Kindle 是单向的只读输出端。",
            "后续若要做双向同步，需要先在 MOC 侧补齐回写接口与冲突解决策略。",
        ],
        make_summary=[
            "把 Kindle Dashboard 的第一版真正跑到 Kindle 上：先设计界面、再梳理数据来源与刷新方案，最后刷机上机验证。",
            "目标不是一次把方案做到完美，而是先完整走通这类硬件项目从设计到部署的路径。",
        ],
        todos=[
            Todo("确认三种主题（浅色/深色/自动）在 16 级灰度下的实际可读性与对比度", "", "", overdue=True),
            Todo("购买支持数据传输的 USB 线", "", "", overdue=False),
            Todo("准备天气数据源并接入预报刷新", "", "", overdue=False),
            Todo("完成 Kindle 只读备份与恢复验证", "", "", overdue=False),
        ],
        tokens=[
            TokenUsage("CODEX", 0.36, "剩64%", "5h窗口", "累计88.0M · 约3h后重置",
                       weekly_ratio=0.62, weekly_remaining=38,
                       weekly_reset="约5d后重置"),
            TokenUsage("CLAUDE", 0.0, "UNAVAILABLE"),
        ],
        bottom_icons=[
            BottomIcon("EVA COMMAND", "command"),
            BottomIcon("GRAY", "gear"),
            BottomIcon("AUTO", "auto"),
            BottomIcon("WIFI", "wifi"),
            BottomIcon("256", "number"),
            BottomIcon("ONBOARD", "board"),
        ],
    )


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "preview_hud.png"
    r = DashboardRenderer()
    r.save(demo_snapshot(), out)
    print(f"已生成 {out}  ({WIDTH}x{HEIGHT}, {GRAY_LEVELS} 级灰度)")
