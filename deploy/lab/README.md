# 실습망 키트

4명이 각자 PC에서 **똑같은** 가상 병원망(공유기 1대 + 기기 VM 6대)을 띄우기 위한 묶음이다.
서로의 PC를 쓰지 않는다. 각자 띄운 실습망은 완전히 따로 돌고, 서로 영향을 주지 않는다.

| 구성 | 위치 |
|---|---|
| 스크립트 (`lab_*.sh`, `lab.conf`) | 이 폴더 (레포) |
| 디스크 묶음 `lab-vN.tar.gz` (`openwrt.img` + 기기 `.qcow2`) | 팀 드라이브 `lab/` 폴더 |
| 공유기·VM 계정 비밀번호 | 메신저 (레포에 적지 않는다) |

디스크는 용량이 크고 비밀번호가 들어 있어 **레포에 올리지 않는다.**

## 처음 한 번: 환경 준비 (Windows는 WSL2 Ubuntu 24.04 안에서)

```bash
# PowerShell(관리자): wsl --install -d Ubuntu-24.04
sudo apt update && sudo apt install -y qemu-system-x86 qemu-utils socat
ls -l /dev/kvm            # 없으면 BIOS에서 가상화(VT-x/AMD-V)를 켠다
sudo chmod 666 /dev/kvm   # 권한 오류가 나면 (WSL을 다시 켤 때마다)
```

`/dev/kvm`의 그룹이 `kvm`이 아니라 `systemd-resolve` 등으로 나오면 kvm 그룹에 들어 있어도 권한 오류가 난다. 위 `chmod`로 해결한다.

## 키트 받기

```bash
mkdir -p ~/nids-lab
tar -xzf lab-v1.tar.gz -C ~/nids-lab        # ~/nids-lab/lab-v1/ 이 생긴다
cd ~/nids-lab/lab-v1 && sha256sum -c SHA256SUMS   # 전부 OK여야 한다
cat VERSION
```

## 쓰기

```bash
cd <레포>/deploy/lab
chmod +x *.sh               # 깃허브 웹으로 올린 파일은 실행 권한이 빠져 있다 (처음 한 번)
./lab_up.sh                  # 공유기 + 기기 VM 전부 (백그라운드)
./lab_console.sh             # 실행 상태 보기
./lab_console.sh camera      # 카메라 콘솔. Enter 한 번, 빠져나오기 Ctrl+]
./lab_down.sh                # 전부 끄기
```

- 공유기 관리: `ssh -p 2222 root@127.0.0.1`, 대시보드: `http://127.0.0.1:8080/`
- 일부만: `./lab_up.sh router camera attacker`
- 다른 버전: `LAB_DIR=~/nids-lab/lab-v2 ./lab_up.sh`
- 녹화(6번): `PCAP=~/nids-lab/pcap/run1 ./lab_up.sh` → 공유기 구역 NIC 5개(`admin`, `wan`, `cctv`, `clinic`, `monitor`)의 패킷이 호스트에 `.pcap`으로 저장된다. 공유기를 끄면 파일이 닫힌다.

**기본은 `-snapshot` 모드다.** VM 안에서 바뀐 내용(설정, 로그, 공격 흔적)은 끄면 버려지고, 매번 키트 상태 그대로 시작한다. 그래서 실험을 몇 번 반복해도 같은 조건이 된다.
공유기에 올리는 우리 코드(대응 모듈, 추출기, 대시보드)는 부팅 후 `scp -O -P 2222`로 복사하는 스크립트로 올린다. VM 안에서 손으로 고친 내용은 남지 않는다.

## 키트를 고치고 배포하기 (VM을 만든 사람만)

```bash
# 원본 폴더(~/nids-lab/build)에 openwrt.img와 lab.conf에 적힌 디스크를 둔다
PERSIST=1 LAB_DIR=~/nids-lab/build ./lab_up.sh camera   # 바뀐 내용이 디스크에 저장됨
./lab_console.sh camera   # 고치기
./lab_down.sh camera      # 저장 모드는 정상 종료 신호로 끈다
SRC=~/nids-lab/build ./lab_pack.sh v2 "카메라에 FTP 계정 추가"
# → ~/nids-lab/dist/lab-v2.tar.gz 를 드라이브 lab/ 에 올리고 팀에 알린다
```

- `lab_pack.sh`는 `base.qcow2`에 기댄 복사본 디스크를 독립 파일로 합친다. 받는 사람은 base 없이 연다.
- 버전은 올리기만 한다(`v1`, `v2`, …). 누가 어느 버전으로 실험했는지 결과 파일에 적는다.
- 기기를 추가하거나 MAC·구역을 바꾸면 `lab.conf`도 같이 고친다. 키트 안에 들어간 `lab.conf`가 우선 쓰인다.
- 공유기 NIC 구성은 `deploy/openwrt/run_router.sh`와 같아야 한다.

## 측정은 한 PC에서

탐지·차단 시간, CPU·메모리처럼 PC 사양에 따라 달라지는 수치(11번 통합 시험, 발표 수치)는 **정해 둔 한 PC**에서만 잰다. 다른 PC는 개발과 확인용이다.

## 알아 둘 것

- 공유기와 기기 VM은 **같은 PC의 같은 WSL 안에서** 띄워야 연결된다(`localaddr=127.0.0.1`). 다른 PC의 VM과는 연결되지 않는다.
- 메모리 여유 약 1.5GB가 필요하다(공유기 128MB + 기기 192~256MB × 6).
- `remote`는 외부 정상 사용자 VM이다. IP 두 개로 원장 휴대폰 원격 보기(203.0.113.50)와 설치업체 원격 점검(203.0.113.80)을 만든다(6번).
- 이 가상 스위치는 자기가 보낸 프레임도 되돌려 받는다. 캡처할 때 공유기 MAC(`52:54:00:aa:00:0X`)에서 온 프레임은 거른다.
- 기기 VM 콘솔이 안 보이면 VM의 커널 옵션에 `console=ttyS0`이 없는 것이다. 만들 때 Alpine의 `/etc/update-extlinux.conf`에서 `default_kernel_opts`에 `console=ttyS0,115200`을 넣고 `update-extlinux`를 실행한다.
