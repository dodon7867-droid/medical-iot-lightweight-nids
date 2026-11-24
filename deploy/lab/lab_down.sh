#!/usr/bin/env bash
# 실습망 VM을 끈다.  ./lab_down.sh (전부)  ·  ./lab_down.sh camera (일부)
# 저장 모드(PERSIST=1)로 띄운 VM은 정상 종료 신호를 보내 디스크가 깨지지 않게 하고,
# 기본(-snapshot) 모드는 어차피 바뀐 내용을 버리므로 바로 끈다.
set -uo pipefail
source "$(dirname "$0")/common.sh"
names=("$@"); [ ${#names[@]} -gt 0 ] || mapfile -t names < <(all_names)
for name in "${names[@]}"; do
  alive "$name" || { rm -f "$RUN/$name".{pid,sock,mon,mode}; continue; }
  if [ "$(cat "$RUN/$name.mode" 2>/dev/null)" = 1 ]; then
    echo system_powerdown | socat - "unix-connect:$RUN/$name.mon" >/dev/null 2>&1
    for _ in $(seq 60); do alive "$name" || break; sleep 1; done
    alive "$name" && echo "  $name: 60초 안에 안 꺼짐. 콘솔에서 poweroff 하세요." && continue
  else
    echo quit | socat - "unix-connect:$RUN/$name.mon" >/dev/null 2>&1 || kill "$(cat "$RUN/$name.pid")"
    sleep 1
  fi
  rm -f "$RUN/$name".{pid,sock,mon,mode}
  echo "  $name: 종료"
done
