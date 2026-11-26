#!/usr/bin/env bash
# 키트 만들기 (VM을 만든 사람만 쓴다).
#   SRC=~/nids-lab/build ./lab_pack.sh v1 "처음 배포"
# SRC 폴더의 openwrt.img와 lab.conf에 적힌 디스크를 모아 ~/nids-lab/dist/lab-v1.tar.gz를 만든다.
# 복사본 디스크(-b base.qcow2)는 독립 파일로 합쳐서 base 없이도 열리게 한다.
set -euo pipefail
source "$(dirname "$0")/common.sh"
need qemu-img qemu-utils
[ $# -ge 1 ] || die "사용법: SRC=원본폴더 ./lab_pack.sh v1 \"바뀐 점\""
VER=$1; NOTE=${2:-}
SRC=${SRC:-$HOME/nids-lab/build}
OUT=$HOME/nids-lab/dist/lab-$VER
[ -e "$OUT" ] && die "$OUT 가 이미 있습니다. 버전을 올리세요."
for n in $(all_names); do
  [ -f "$RUN/$n.pid" ] && kill -0 "$(cat "$RUN/$n.pid")" 2>/dev/null && die "$n 이(가) 실행 중입니다. 먼저 ./lab_down.sh"
done
mkdir -p "$OUT"
cp "$SRC/openwrt.img" "$OUT/"
while read -r name mem port mac disk; do
  [ -f "$SRC/$disk" ] || die "$SRC/$disk 없음"
  echo "  $disk 합치는 중..."
  qemu-img convert -O qcow2 -c "$SRC/$disk" "$OUT/$disk"
done < <(devices)
cp "$CONF" "$OUT/lab.conf"
{ echo "lab-$VER  $(date '+%Y-%m-%d %H:%M')"; [ -n "$NOTE" ] && echo "$NOTE"; } > "$OUT/VERSION"
(cd "$OUT" && sha256sum openwrt.img *.qcow2 lab.conf > SHA256SUMS)
tar -C "$(dirname "$OUT")" -czf "$OUT.tar.gz" "lab-$VER"
ls -lh "$OUT.tar.gz"
echo "드라이브 lab/ 폴더에 올리고 팀에 'lab-$VER' 배포를 알리세요. 비밀번호는 메신저로."
