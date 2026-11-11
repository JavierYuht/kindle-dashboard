#!/bin/sh
# 看板服务启动器：挑一个带 Pillow 的 Python，然后前台跑 dash_server（launchd 负责守护）
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

for PY in \
  "$HOME/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3" \
  "$ROOT/.venv/bin/python" \
  "$(command -v python3 2>/dev/null)"
do
  [ -n "$PY" ] && [ -x "$PY" ] || continue
  if "$PY" -c "import PIL" >/dev/null 2>&1; then
    exec "$PY" src/dash_server.py --image samples/preview_home.png --port 8765 --auto-build
  fi
done

echo "找不到带 Pillow 的 Python，先装依赖：python3 -m pip install -r requirements.txt" >&2
exit 1
