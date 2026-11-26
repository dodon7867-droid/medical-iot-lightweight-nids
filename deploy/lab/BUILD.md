# 가상 병원망 제작 메모

## 기본 환경

- WSL2 Ubuntu 24.04, qemu-system-x86, qemu-utils, socat, KVM.
- 기기 OS: 공식 Alpine Linux virt 3.24.4 x86_64 ISO.
- 배포처: https://dl-cdn.alpinelinux.org/alpine/v3.24/releases/x86_64/
- ISO SHA256: `157d353f8e54252cad2d9812a0d56bb7fa2231fc154a110e1d180d7480ef8b4f`.
- 공유기는 제공받은 OpenWrt 이미지 사용.
- 실행 스크립트 기반: 팀 GitHub의 `deploy/lab/`, `deploy/openwrt/run_router.sh`.

## 기본 VM

레포 밖 `~/nids-lab/build`에서 `qemu-img create -f qcow2 base.qcow2 2G`로 디스크를 만든다. Alpine virt ISO로 부팅한 뒤 `setup-alpine`으로 설치한다. 패키지를 설치할 때만 `-netdev user`를 붙인다.

디스크 설치는 `setup-disk -m sys -s 0 /dev/sda`를 사용했다. `BOOT_SIZE=128`, `ROOT_SIZE`는 미설정으로 두어 남은 공간을 루트로 사용했다. 새 VM 디스크만 설치 대상으로 지정한다.

`acpid`를 설치하고 `rc-update add acpid default`, `rc-update add local default`를 적용한다. `/etc/update-extlinux.conf`의 `default_kernel_opts`에 `console=tty0 console=ttyS0,115200`을 넣고 `update-extlinux`를 실행한다. `/etc/inittab`의 ttyS0 getty 설정도 확인한다.

기본 VM 종료 후 역할별 복사본을 만든다.

```bash
qemu-img create -f qcow2 -F qcow2 -b "$HOME/nids-lab/build/base.qcow2" camera.qcow2
# server, monitor, admin, attacker, remote도 같은 방식
```

각 복사본은 호스트 이름·IP·게이트웨이를 바꾸고 `lab.conf`의 서로 다른 MAC으로 실행한다.

## 역할별 서비스

| VM | 설치 패키지 | 설정 |
|---|---|---|
| camera | busybox-extras, vsftpd, lighttpd | Telnet 23·FTP 21·HTTP 80, 별도 실습 계정, 1MiB stream.bin |
| server | openssh | SSH 22, 일반 사용자 비밀번호 로그인 |
| monitor | mosquitto, mosquitto-clients | MQTT 1883, ward1/bed3/hr 합성 신호 1초 간격 |
| admin | openssh-client, busybox-extras, lftp, mosquitto-clients | 영상 파일 5초 간격 수신, MQTT 구독 |
| attacker | nmap, hydra | 도구 설치 |
| remote | busybox-extras, lftp, curl | 원장·설치업체 주소 2개 |

서비스는 `rc-update add <서비스> default`로 등록한다. Telnet·센서 발행·관리자 구독 및 영상 수신 작업은 `/etc/local.d/*.start`에 두고 실행 권한을 준다.

카메라 웹 서버는 `server.document-root`를 `/var/www/localhost/htdocs`, `server.pid-file`을 `/run/lighttpd.pid`로 지정한다. `mod_indexfile`과 `index-file.names = ( "index.html" )`을 설정한다. `dd if=/dev/zero of=/var/www/localhost/htdocs/stream.bin bs=1024 count=1024`로 합성 영상 파일을 만든다. FTP는 로컬 사용자 로그인 및 active 모드를 사용한다.

진료 서버는 `PasswordAuthentication yes`, `PermitRootLogin no`로 설정한다. MQTT는 실습망의 1883 리스너와 익명 접속을 사용한다. 계정표는 별도로 전달한다.

## 고정 주소

전체 주소·등급은 `devices.csv`, MAC·구역 포트는 `lab.conf`가 기준이다. 카메라의 `/etc/network/interfaces` 예:

```text
auto lo
iface lo inet loopback
auto eth0
iface eth0 inet static
    address 10.0.30.21/24
    gateway 10.0.30.1
```

remote에는 `203.0.113.50/24`와 `203.0.113.80/24`를 함께 부여하고 게이트웨이를 `203.0.113.1`로 지정한다. 기기 DNS는 설정하지 않는다.

## 연결과 배포

설정 저장 후 VM을 정상 종료한다. 이후 `PERSIST=1 LAB_DIR=~/nids-lab/build ./lab_up.sh`로 실습망 NIC만 연결해 확인한다. 구역 간 ping·서비스 접속, 외부 허용 포트, 인터넷 분리, 공유기 tcpdump를 검사한다.

`lab_down.sh`로 모두 종료한 뒤 `SRC=~/nids-lab/build ./lab_pack.sh vN "변경 내용"`으로 묶는다. 배포 디스크는 backing 파일 없이 열리는 독립 qcow2로 변환한다. 새 폴더에 압축을 풀어 해시·부팅·연결을 확인하고 다른 조원 PC에서도 같은 절차를 수행한다.

