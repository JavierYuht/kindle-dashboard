#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Kindle 端文件部署到已挂载的 Kindle（macOS / Linux 通用 POSIX 路径）。

用法：
    python tools/deploy_kindle_macos.py                 # 自动找 /Volumes/Kindle
    python tools/deploy_kindle_macos.py --root /Volumes/Kindle
    python tools/deploy_kindle_macos.py --dry-run       # 只打印计划

写入内容：
    <root>/dashboard/dash.sh         主循环
    <root>/dashboard/start.sh        后台启动
    <root>/dashboard/stop.sh         停止
    <root>/dashboard/server.conf     HOST/PORT/TOKEN 与刷新参数
    <root>/documents/看板-启动.sh     Scriptlet（书库里点它启动）
    <root>/documents/看板-停止.sh     Scriptlet（点它停止）

说明：
- 全部用 open() 直接写文本，避免 macOS 在 FAT32 上生成 `._` 附属文件。
- server.conf 里的 TOKEN 取自 ~/.dash_server/token（由 dash_server.py 首次运行生成）。
- 不做 KUAL 扩展：5.15.1.1 走 Scriptlet（SH_Integration）即可，避免 KUAL 兼容问题。
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "kindle_ext"
TOKEN_FILE = Path.home() / ".dash_server" / "token"


def lan_ip() -> str:
    """取本机在局域网里的地址（不实际发包）。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


def find_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit)
    else:
        root = Path("/Volumes/Kindle")
        if not root.exists():
            sys.exit("找不到 /Volumes/Kindle，请先插上 Kindle 并确认已挂载")
    if not (root / "documents").is_dir():
        sys.exit(f"{root} 不像 Kindle 根目录（缺少 documents/）")
    return root


def build_server_conf(host: str, port: int, token: str, frontlight: int = 10) -> str:
    return f"""# Kindle 看板配置（由 tools/deploy_kindle_macos.py 生成）
# HOST 留空则靠 dash.sh 自动发现；写死可加快首次连接。
HOST={host}
PORT={port}
TOKEN={token}

DAY_INTERVAL=60
NIGHT_INTERVAL=60
NIGHT_START=1
NIGHT_END=6
FULL_REFRESH_RATE=5

# 亮度默认不接管（0=用 Kindle 自己设置里的亮度，手动调过会被系统记住）
# 想让脚本在启动时强制设一个值，改成 APPLY_FL=1
APPLY_FL=0
DEF_FL={frontlight}
"""


def write_text(path: Path, content: str, mode: int = 0o644, dry: bool = False):
    if not dry:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.chmod(path, mode)
    print(f"  {'(dry) ' if dry else ''}写入 {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="部署 Kindle 看板端文件")
    ap.add_argument("--root", default=None, help="Kindle 根目录，默认 /Volumes/Kindle")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default=None,
                    help="PC 内网 IP；默认自动探测，留空字符串表示交给 dash.sh 自动发现")
    ap.add_argument("--token", default=None, help="覆盖 token（默认读 ~/.dash_server/token）")
    ap.add_argument("--frontlight", type=int, default=10,
                    help="前光强度 0-24，默认 10（PW3 没有环境光传感器，只能手调）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = find_root(args.root)
    token = args.token or (TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else "")
    if not token:
        sys.exit("缺少 token：先运行一次 src/dash_server.py，它会生成 ~/.dash_server/token")
    host = args.host if args.host is not None else lan_ip()

    print(f"Kindle: {root}")
    print(f"PC: {host or '(自动发现)'}:{args.port}")
    print(f"Token: {token[:6]}…{token[-4:]}")

    files = {
        root / "dashboard" / "dash.sh": (SRC / "dash.sh").read_text(encoding="utf-8"),
        root / "dashboard" / "start.sh": (SRC / "start.sh").read_text(encoding="utf-8"),
        root / "dashboard" / "stop.sh": (SRC / "stop.sh").read_text(encoding="utf-8"),
        root / "dashboard" / "diag.sh": (SRC / "diag.sh").read_text(encoding="utf-8"),
        root / "dashboard" / "server.conf": build_server_conf(host, args.port, token,
                                                              args.frontlight),
        root / "documents" / "看板-启动.sh": (SRC / "documents" / "看板-启动.sh").read_text(encoding="utf-8"),
        root / "documents" / "看板-停止.sh": (SRC / "documents" / "看板-停止.sh").read_text(encoding="utf-8"),
        root / "documents" / "看板-诊断.sh": (SRC / "documents" / "看板-诊断.sh").read_text(encoding="utf-8"),
    }
    for path, content in files.items():
        write_text(path, content, 0o755 if path.suffix == ".sh" else 0o644, args.dry_run)

    # 清理已弃用的亮度脚本（亮度改回手动，由 Kindle 自己记）
    if not args.dry_run:
        for obsolete in (root / "dashboard" / "bright.sh",
                         root / "dashboard" / "fl_intensity",
                         root / "documents" / "看板-亮度加.sh",
                         root / "documents" / "看板-亮度减.sh"):
            if obsolete.exists():
                obsolete.unlink()
                print(f"  (清理) 删除 {obsolete.relative_to(root)}")

    # 清掉历史上可能留下的 AppleDouble 附属文件，免得被 Kindle 索引
    if not args.dry_run:
        for junk in root.rglob("._*"):
            try:
                junk.unlink()
            except OSError:
                pass

    print("\n完成。拔线后在书库点『看板 启动』，约 10–20 秒出图。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
