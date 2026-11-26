# 가상 병원망 실습 키트

공유기 1대와 기기 VM 6대를 PC 한 대의 WSL2 안에서 실행한다. 조원마다 같은 키트를 받아 독립된 망을 사용한다.

## 파일 위치

| 자료 | 배포 위치 |
|---|---|
| lab-v1.tar.gz | 팀 드라이브의 lab/ 폴더 |
| lab_*.sh, common.sh, lab.conf, README.md | GitHub deploy/lab/ |
| BUILD.md, TOPOLOGY.md | GitHub deploy/lab/ — 제작 방법·실제 IP 구성도 |
| devices.csv | GitHub deploy/ — 기기 등급표 |
| 계정표 | 팀 메신저로 별도 전달 |

키트 압축에는 공유기 이미지, 기기 디스크 6개, lab.conf, VERSION, SHA256SUMS가 들어 있다. 실행 스크립트는 GitHub에서 받는다. 이미지·디스크·계정표는 GitHub에 올리지 않는다.

## 처음 한 번: 환경 준비

Windows에서는 WSL2 Ubuntu 24.04 안에서 모든 VM을 띄운다. 호스트 여유 메모리는 약 1.5GB 이상을 권장한다.

```bash
# WSL이 없다면 Windows PowerShell에서:
# wsl --install -d Ubuntu-24.04
# 아래 명령은 Ubuntu에서 실행
sudo apt update
sudo apt install -y git qemu-system-x86 qemu-utils socat
ls -l /dev/kvm
```

KVM 권한 오류가 있을 때만 아래 명령을 실행한다. `newgrp`로 열린 셸에서 계속한다.

```bash
sudo groupadd -f kvm
sudo chgrp kvm /dev/kvm
sudo chmod 660 /dev/kvm
sudo usermod -aG kvm "$USER"
newgrp kvm
```

`/dev/kvm`이 없으면 BIOS 가상화·WSL2 설정을 확인한다. KVM이 없으면 부팅이 매우 느려질 수 있다.

## 키트 받기

드라이브에서 받은 압축 파일이 있는 Ubuntu 폴더에서 실행한다.

```bash
mkdir -p ~/nids-lab
tar -xzf lab-v1.tar.gz -C ~/nids-lab
cd ~/nids-lab/lab-v1
sha256sum -c SHA256SUMS
cat VERSION
```

모든 파일이 OK여야 한다. 각 qcow2는 독립 디스크이므로 base.qcow2가 필요 없다.

## 실행

레포는 Ubuntu 홈 폴더 아래에 받는다. 이미 받았다면 해당 레포의 deploy/lab 폴더로 이동한다.

```bash
# 처음 받는 경우:
git clone https://github.com/dodon7867-droid/medical-iot-lightweight-nids.git ~/medical-iot-lightweight-nids
cd ~/medical-iot-lightweight-nids/deploy/lab
chmod +x *.sh
./lab_up.sh
./lab_console.sh
./lab_console.sh admin
./lab_down.sh
```

콘솔에서 Enter를 누르고 별도로 받은 계정으로 로그인한다. Ctrl+]는 콘솔 연결만 끊는다. VM은 `lab_down.sh`로 종료한다.

- 공유기 SSH: `ssh -p 2222 root@127.0.0.1`.
- 공유기 웹 관리: `http://127.0.0.1:8080/`. 관제 대시보드는 포함하지 않는다.
- 일부만 시작: `./lab_up.sh router camera attacker`.
- 다른 키트 위치: `LAB_DIR=/경로/lab-v1 ./lab_up.sh`.
- 기본은 snapshot 모드다. 종료하면 VM 안의 변경이 사라진다. 원본을 수정할 때만 `PERSIST=1`을 사용한다.

## 연결 확인

admin 콘솔에서:

```sh
ping -c 2 10.0.30.21
ping -c 2 10.0.20.10
ping -c 2 10.0.10.33
nc -zv -w 3 10.0.20.10 22
wget -qO- http://10.0.30.21/stream.bin | wc -c
mosquitto_sub -h 10.0.10.33 -t ward1/bed3/hr -C 3
```

영상 파일은 1048576바이트, MQTT 합성 신호는 3개가 출력되어야 한다.

attacker 콘솔에서:

```sh
nc -zv -w 3 10.0.30.21 21
nc -zv -w 3 10.0.30.21 23
nc -zv -w 3 10.0.30.21 80
nc -zv -w 3 10.0.20.10 22
```

카메라 포트 3개는 성공, 진료 서버 22는 실패해야 한다. 공유기에서 `tcpdump -nn -i eth3`를 켜고 admin에서 서버로 ping하면 구역 간 패킷이 보여야 한다.

5개 구역은 루프백 멀티캐스트로 연결하며 물리 NIC에 브리지하지 않는다. 기기 VM에는 인터넷용 NIC가 없다. 공유기 관리 NIC는 restrict=on이며 기본 경로가 없다. WAN에서 내부로 새로 시작하는 연결은 카메라 TCP 21·23·80만 허용한다. 구역 간 통신은 NAT 없이 공유기를 거친다.

## 수정과 다음 버전 배포

```bash
PERSIST=1 LAB_DIR=~/nids-lab/build ./lab_up.sh camera
./lab_console.sh camera
./lab_down.sh camera
SRC=~/nids-lab/build ./lab_pack.sh v2 "변경 내용"
```

새 키트는 `~/nids-lab/dist/lab-v2.tar.gz`에 생긴다. 버전은 올리기만 하고 조원에게 같은 버전을 전달한다. 다른 조원 PC에서도 위 연결 확인을 수행하고 결과를 남긴다.
