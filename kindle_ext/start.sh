#!/bin/sh
# 启动看板主循环（后台常驻）。由 documents 里的 Scriptlet 调用，也可直接 sh 执行。
# 注意：不调用 initctl stop framework —— 保留原生界面/触屏/原生阅读。
D=/mnt/us/dashboard
mkdir -p "$D"

# 已在运行则不重复启动
if [ -f "$D/dash.pid" ]; then
  pid=$(cat "$D/dash.pid" 2>/dev/null)
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "看板已在运行 (pid=$pid)"
    exit 0
  fi
fi

rm -f "$D/stop"

# setsid 脱离当前会话，避免 Scriptlet 退出时被一起带走（busybox 无 setsid 时退回 nohup）
if command -v setsid >/dev/null 2>&1; then
  setsid /bin/sh "$D/dash.sh" >>"$D/boot.log" 2>&1 &
else
  nohup /bin/sh "$D/dash.sh" >>"$D/boot.log" 2>&1 &
fi
echo $! > "$D/dash.pid"
sleep 2

pid=$(cat "$D/dash.pid" 2>/dev/null)
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
  echo "看板已启动 pid=$pid，日志 $D/dash.log"
else
  echo "启动失败，请查看 $D/boot.log 与 $D/dash.log"
fi
exit 0
