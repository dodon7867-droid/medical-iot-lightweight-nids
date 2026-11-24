# lab_*.sh가 함께 쓰는 설정. 직접 실행하지 않는다.
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LAB_DIR=${LAB_DIR:-$HOME/nids-lab/lab-v1}   # 키트를 푼 폴더
# 키트 안의 lab.conf가 있으면 그걸 쓴다 (디스크와 버전이 맞도록)
if [ -z "${CONF:-}" ]; then
  if [ -f "$LAB_DIR/lab.conf" ]; then CONF=$LAB_DIR/lab.conf; else CONF=$HERE/lab.conf; fi
fi
RUN=${RUN:-/tmp/nidslab}                     # 실행 중 VM의 pid·콘솔 소켓
MC=230.0.0.1
LA=127.0.0.1

die() { echo "오류: $*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "$1 이(가) 없습니다. sudo apt install -y $2"; }

# 이름 디스크 메모리 포트 MAC (lab.conf에서 주석·빈 줄 제외)
devices() { sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "$CONF"; }

alive() { [ -f "$RUN/$1.pid" ] && kill -0 "$(cat "$RUN/$1.pid")" 2>/dev/null; }

all_names() { echo router; devices | awk '{print $1}'; }
