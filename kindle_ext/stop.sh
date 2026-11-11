#!/bin/sh
# 停止看板：打 stop 标志，主循环在下一轮（≤1 个重绘周期）退出并恢复原生界面
D=/mnt/us/dashboard
touch "$D/stop"

i=0
while [ $i -lt 40 ]; do
  pid=$(cat "$D/dash.pid" 2>/dev/null)
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    echo "看板已停止"
    lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null
    rm -f "$D/dash.pid"
    exit 0
  fi
  sleep 1
  i=$((i + 1))
done

# 超时强杀
pid=$(cat "$D/dash.pid" 2>/dev/null)
[ -n "$pid" ] && kill "$pid" 2>/dev/null
rm -f "$D/dash.pid"
lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null
echo "已强制停止看板"
exit 0
