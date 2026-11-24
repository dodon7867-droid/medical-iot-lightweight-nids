# Lightweight NIDS with Tiered Automated Response for Medical IoT

A network intrusion detection system small enough to run on a clinic's router
(OpenWrt, 1 vCPU, 128 MB RAM). Three decision trees, one per device tier, about 2.8 KB of C code in total.

- **Problem:** CCTV and IP cameras in small clinics leak video because of weak or default passwords.
  Small clinics have no security staff and cannot install agents on medical devices.
- **Approach:** passive flow-based detection on the router, plus automated response through the
  router firewall (nftables). The response depends on the device tier, because blocking a
  life-support device is more dangerous than the attack itself.
- **Data:** [MedSec-25](data/README.md), relabeled at flow level.

## Device tiers (= scenarios)

| Tier | Devices | Attack in MedSec-25 | Response |
|---|---|---|---|
| T1 | Life-support / patient monitoring | MQTT service attacks | Alert only, never auto-block |
| T2 | Clinical support servers | Server SSH brute force | Alert, block external sources only when confident |
| T3 | CCTV / IP cameras | Recon → device password guessing → lateral movement → exfiltration | Auto-block external sources |

The presentation demo covers the T3 (CCTV) scenario.

## Repository layout

```
src/common.py               data pipeline shared by every stage (relabel, windows, split)
src/s01_baselines.py        rule vs Random Forest vs tree, 5 classes; capture-trace check
src/s02_tier_models.py      one tree per tier; cost weights; probability thresholds
src/s03_feature_count.py    many features vs few features (69 → 32 → top-k)
src/s04_correlation_filter.py  Spearman correlation filter vs tree importance (CCTV tree)
src/s05_final_models.py     final 12 shared features, saves the three tier trees
src/s06_export_c.py         export trees to C (emlearn, float)
src/s07_eda.py              EDA figures (PNG + the plotted numbers as CSV) into results/eda/
c/                          C check harness (agreement, latency, code size) and exported trees
results/                    logs of our run
data/README.md              where to download the dataset
run_all.sh                  runs everything in order
```

## How to run

Requires Python 3.12 or newer (the pinned numpy 2.5 does not install on older versions),
a C compiler and `make`. On Windows, use WSL2 with Ubuntu 24.04.

```bash
pip install -r requirements.txt
# download MedSec-25.csv into data/ (see data/README.md)
./run_all.sh            # about 10 minutes on a laptop; logs go to results/
```

Each stage can also run alone, e.g. `python3 src/s05_final_models.py data/MedSec-25.csv`.
Stage 6 needs stage 5's output, and `make -C c check size` needs a C compiler.
On Python 3.12, emlearn needs `setuptools` (it imports `distutils`); it is in `requirements.txt`.
Keep the clone inside the WSL home folder, not under `/mnt/c`: Windows file times confuse `make`
(if you see clock-skew warnings, run `make -B -C c check size`).

## EDA figures

`python3 src/s07_eda.py data/MedSec-25.csv` draws five figures into `results/eda/`, each with a CSV of the plotted numbers:

| File | What it shows |
|---|---|
| `eda1_relabel` | share of benign flows inside each attack capture (lateral movement capture: 91.5%), the reason we relabel per flow |
| `eda2_classes` | flows per label after relabel, log axis, colored by device tier (largest/smallest = 1,132×) |
| `eda3_windows` | `w60_dports` and `w10_flows` by stage (box 25–75%, whiskers 5–95%, log axis) |
| `eda4_timeline` | flows per minute in each capture, train (first 70%) vs test (last 30%); the benign capture is from 2022, the attack captures from 2025 |
| `eda5_columns` | how 84 CSV columns become the final 12 features |

## Preprocessing

MedSec-25 labels each **capture** (every flow in an attack capture gets the attack label, including
normal background traffic). We relabel each **flow**:

1. Non-benign capture and the flow touches an attacker host → keep the capture label
   (attacker background traffic such as DNS, DHCP, mDNS is removed).
2. Exfiltration capture and the flow is device ↔ server → Exfiltration.
3. Lateral-movement capture and the flow is pivot device ↔ other internal host → Lateral movement.
4. Everything else → Benign.

Then: drop Protocol 0 flows, add four causal source time-window features
(`w10_flows`, `w60_flows`, `w60_dports`, `w60_dsts`), drop flows with negative time values
from training and evaluation, remove identifiers (IPs, ports, flow ID, timestamp), constants and
identity columns (`Protocol`, `Init Bwd Win Byts`), and split chronologically 70/30 inside each
(capture × label × attack source). "Initial access" is split by target into
MQTT attack, Server SSH guess and Device PW guess.

## Results (test split)

Final models, 12 shared features (from `results/s05_final_models.log`):

| Tier | Nodes | Macro-F1 | Attack recall | Benign FPR |
|---|---|---|---|---|
| T1 | 65 | 0.999 | 100% | 0.17% |
| T2 | 27 | 0.996 | 100% | 0.02% |
| T3 | 173 | 0.918 | 99.77% | 1.46% |

All three together: benign FPR 1.61%, 14 false alerts over about 2.4 hours of benign test traffic.
C export: all 60,000 test predictions match scikit-learn; code size 2,777 bytes (809 + 412 + 1,556) (see `results/s06_export_c.log`).
emlearn writes each split as `x < threshold` while scikit-learn uses `x <= threshold`; many of our thresholds are whole numbers (flow counts), so `s06_export_c.py` rewrites the comparison to `<=`.

Many vs few features (union benign FPR of the three tiers, `results/s03`–`s05` logs):

| Feature set | Union FPR |
|---|---|
| Random Forest, all 65 + 4 | 0.39% |
| Tree, all 65 + 4 | 3.40% |
| Tree, 32 candidates | 2.73% |
| Tree, top 12 by RF ranking | 7.28% |
| **Tree, top 12 by CCTV-tree importance (final)** | **1.61%** |

Removing correlated features first (Spearman |rho| ≥ 0.9) raised the CCTV tree's FPR from 1.46% to 2.70%,
so correlation is reported as a reference and not used as a filter.

## Known limitations

- MedSec-25 has no benign SSH, FTP or Telnet traffic, so false positives on legitimate remote
  administration are not measured here; we test them in our own lab.
- MedSec-25 has no DoS/DDoS traffic.
- The T2 test set has only 122 attack flows, so its scores may be optimistic.
- False alerts are still far above our target of one per day.
- The router deployment (flow extraction on OpenWrt and nftables blocking) is in progress.

## References

- Dataset: Almobaideen et al., "MedSec-25: Creating an IoMT Dataset for a Healthcare IoT Environment," BCCA 2025, doi:10.1109/BCCA66705.2025.11229535
- emlearn: https://github.com/emlearn/emlearn
- CICFlowMeter: https://github.com/ahlashkari/CICFlowMeter
