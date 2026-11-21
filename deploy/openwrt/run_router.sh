#!/usr/bin/env bash
# 가상 공유기: 1 vCPU, 128MB, 구역 NIC 5개(eth0~4) + 관리 NIC 1개(eth5)
set -e
cd "$(dirname "$0")"
IMG=${IMG:-openwrt.img}
MC=230.0.0.1
LA=127.0.0.1

exec qemu-system-x86_64 -enable-kvm -m 128 -smp 1 -nographic \
  -drive file="$IMG",format=raw \
  -netdev socket,id=admin,mcast=$MC:10001,localaddr=$LA   -device e1000,netdev=admin,mac=52:54:00:aa:00:01 \
  -netdev socket,id=wan,mcast=$MC:10002,localaddr=$LA     -device e1000,netdev=wan,mac=52:54:00:aa:00:02 \
  -netdev socket,id=cctv,mcast=$MC:10003,localaddr=$LA    -device e1000,netdev=cctv,mac=52:54:00:aa:00:03 \
  -netdev socket,id=clinic,mcast=$MC:10004,localaddr=$LA  -device e1000,netdev=clinic,mac=52:54:00:aa:00:04 \
  -netdev socket,id=monitor,mcast=$MC:10005,localaddr=$LA -device e1000,netdev=monitor,mac=52:54:00:aa:00:05 \
  -netdev user,id=mgmt,restrict=on,hostfwd=tcp:127.0.0.1:8080-:80,hostfwd=tcp:127.0.0.1:2222-:22 \
  -device e1000,netdev=mgmt,mac=52:54:00:aa:00:06
