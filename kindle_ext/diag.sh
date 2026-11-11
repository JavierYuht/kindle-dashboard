#!/bin/sh
# 只读诊断：结果写到 /mnt/us/dashboard/diag.txt，拔线插电脑就能看
PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
D=/mnt/us/dashboard
OUT=$D/diag.txt
. "$D/server.conf" 2>/dev/null

{
  echo "===== 时间 ====="; date
  echo; echo "===== 内核 ====="; uname -a
  echo; echo "===== 固件 ====="; cat /etc/prettyversion.txt 2>/dev/null; cat /mnt/us/system/version.txt 2>/dev/null
  echo; echo "===== 越狱痕迹 ====="; ls -l /mnt/us/documents/JAILBROKEN.txt 2>&1; ls -d /var/local/kmc /mnt/us/kmc 2>&1
  echo; echo "===== 内置命令 ====="
  for c in eips lipc-get-prop lipc-set-prop curl wget setsid nohup; do printf "%-14s %s\n" "$c" "$(command -v $c 2>/dev/null || echo MISSING)"; done
  echo; echo "===== 屏幕 ====="; eips -i 2>&1 | head -6
  echo; echo "===== 电量 ====="; lipc-get-prop com.lab126.powerd battLevel 2>&1; lipc-get-prop com.lab126.powerd isCharging 2>&1
  echo; echo "===== 网络 ====="; ifconfig 2>/dev/null | grep -E "inet (addr:)?[0-9]" | head -4
  echo; echo "===== PC 连通性 ====="
  echo "HOST=$HOST PORT=$PORT"
  curl -s -m 5 -o /dev/null -w "health=%{http_code}\n" "http://$HOST:$PORT/health" 2>&1
  curl -s -m 10 -o /dev/null -w "dash=%{http_code} size=%{size_download}\n" "http://$HOST:$PORT/dash.png?t=$TOKEN" 2>&1
  echo; echo "===== 进程 ====="; ps 2>/dev/null | grep -E "dash.sh|koreader" | grep -v grep
  echo; echo "===== 日志尾部 ====="; tail -20 $D/dash.log 2>&1
  echo; echo "===== boot.log ====="; tail -10 $D/boot.log 2>&1
} > "$OUT" 2>&1

# 屏上也给个反馈
eips 4 10 "diag written: $OUT" 2>/dev/null || true
exit 0
