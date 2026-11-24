#!/usr/bin/env bash
# 실습망 키트: 가상 공유기와 기기 VM을 한 번에 백그라운드로 띄운다.
#   ./lab_up.sh                 # 전부
#   ./lab_up.sh router camera   # 일부만
#   PERSIST=1 ./lab_up.sh       # 바뀐 내용을 디스크에 저장 (VM을 만들거나 고칠 때만)
#   LAB_DIR=~/nids-lab/lab-v2 ./lab_up.sh   # 다른 버전의 키트
#   PCAP=~/nids-lab/pcap/run1 ./lab_up.sh   # 공유기 구역 NIC 5개의 패킷을 호스트에 pcap으로 녹화 (6번)
# 기본은 -snapshot: 끄면 VM 안에서 바뀐 내용이 버려지고 매번 키트 상태 그대로 시작한다.
set -euo pipefail
source "$(dirname "$0")/common.sh"
need qemu-system-x86_64 qemu-system-x86
need socat socat
[ -d "$LAB_DIR" ] || die "키트 폴더 $LAB_DIR 가 없습니다. 드라이브에서 받은 lab-vN.tar.gz를 ~/nids-lab/에 푸세요."
mkdir -p "$RUN"

PERSIST=${PERSIST:-0}
if [ -w /dev/kvm ]; then
  ACCEL=(-enable-kvm)
else
  echo "경고: /dev/kvm 권한이 없어 KVM 없이 매우 느리게 돕니다. 'sudo chmod 666 /dev/kvm' 후 다시 실행하세요." >&2
  ACCEL=(-accel tcg)
fi
SNAP=(); [ "$PERSIST" = 1 ] || SNAP=(-snapshot)

start() {   # start 이름 메모리 [qemu 인자...]
  local name=$1 mem=$2; shift 2
  if alive "$name"; then echo "  $name: 이미 실행 중"; return; fi
  rm -f "$RUN/$name".{pid,sock,mon}
  qemu-system-x86_64 "${ACCEL[@]}" -m "$mem" -smp 1 -display none -daemonize \
    -pidfile "$RUN/$name.pid" \
    -serial "unix:$RUN/$name.sock,server=on,wait=off" \
    -monitor "unix:$RUN/$name.mon,server=on,wait=off" \
    "${SNAP[@]}" "$@"
  echo "$PERSIST" > "$RUN/$name.mode"
  echo "  $name: 시작 (콘솔: ./lab_console.sh $name)"
}

want() { [ $# -eq 0 ] && return 0; local n; for n in "${SEL[@]}"; do [ "$n" = "$1" ] && return 0; done; return 1; }
SEL=("$@")
sel() { [ ${#SEL[@]} -eq 0 ] || want "$1"; }

echo "키트: $LAB_DIR  (저장 모드: $([ "$PERSIST" = 1 ] && echo 켬 || echo 끔, 끄면 원래대로))"

# 공유기: deploy/openwrt/run_router.sh와 NIC 구성이 같아야 한다 (eth0~eth5).
if sel router; then
  [ -f "$LAB_DIR/openwrt.img" ] || die "$LAB_DIR/openwrt.img 가 없습니다."
  DUMP=()
  if [ -n "${PCAP:-}" ]; then
    mkdir -p "$PCAP"
    for z in admin wan cctv clinic monitor; do
      DUMP+=(-object "filter-dump,id=d-$z,netdev=$z,file=$PCAP/$z.pcap")
    done
    echo "  녹화: $PCAP/{admin,wan,cctv,clinic,monitor}.pcap (공유기를 끄면 파일이 닫힘)"
  fi
  start router 128 "${DUMP[@]}" -drive "file=$LAB_DIR/openwrt.img,format=raw" \
    -netdev socket,id=admin,mcast=$MC:10001,localaddr=$LA   -device e1000,netdev=admin,mac=52:54:00:aa:00:01 \
    -netdev socket,id=wan,mcast=$MC:10002,localaddr=$LA     -device e1000,netdev=wan,mac=52:54:00:aa:00:02 \
    -netdev socket,id=cctv,mcast=$MC:10003,localaddr=$LA    -device e1000,netdev=cctv,mac=52:54:00:aa:00:03 \
    -netdev socket,id=clinic,mcast=$MC:10004,localaddr=$LA  -device e1000,netdev=clinic,mac=52:54:00:aa:00:04 \
    -netdev socket,id=monitor,mcast=$MC:10005,localaddr=$LA -device e1000,netdev=monitor,mac=52:54:00:aa:00:05 \
    -netdev user,id=mgmt,restrict=on,hostfwd=tcp:127.0.0.1:8080-:80,hostfwd=tcp:127.0.0.1:2222-:22 \
    -device e1000,netdev=mgmt,mac=52:54:00:aa:00:06
fi

while read -r name mem port mac disk; do
  sel "$name" || continue
  if [ ! -f "$LAB_DIR/$disk" ]; then echo "  $name: 디스크 $disk 없음, 건너뜀"; continue; fi
  start "$name" "$mem" -drive "file=$LAB_DIR/$disk,format=qcow2" \
    -netdev socket,id=n0,mcast=$MC:$port,localaddr=$LA -device e1000,netdev=n0,mac=$mac
done < <(devices)

echo "끝. 공유기 관리: ssh -p 2222 root@127.0.0.1 · 대시보드: http://127.0.0.1:8080/ · 끄기: ./lab_down.sh"
