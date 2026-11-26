#!/usr/bin/env bash
# VM 콘솔에 붙는다.  ./lab_console.sh camera   ·  빠져나오기: Ctrl+]   (VM은 계속 돈다)
# 인자 없이 실행하면 VM별 실행 상태를 보여 준다.
set -uo pipefail
source "$(dirname "$0")/common.sh"
if [ $# -eq 0 ]; then
  for n in $(all_names); do printf '  %-9s %s\n' "$n" "$(alive "$n" && echo 실행 중 || echo 꺼짐)"; done
  exit 0
fi
alive "$1" || die "$1 이(가) 실행 중이 아닙니다. ./lab_up.sh $1"
echo "[$1 콘솔] Enter를 한 번 누르세요. 빠져나오기: Ctrl+]"
exec socat -,raw,echo=0,escape=0x1d "unix-connect:$RUN/$1.sock"
