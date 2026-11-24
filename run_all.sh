#!/usr/bin/env bash
# Runs every stage in order and keeps the logs in results/.
set -euo pipefail
CSV=${1:-data/MedSec-25.csv}
mkdir -p results outputs
for s in s01_baselines s02_tier_models s03_feature_count s04_correlation_filter s05_final_models; do
  echo "== $s"
  python3 src/$s.py "$CSV" | tee results/$s.log
done
python3 src/s06_export_c.py | tee results/s06_export_c.log
make -C c check size | tee -a results/s06_export_c.log
python3 src/s07_eda.py "$CSV" | tee results/s07_eda.log   # EDA figures -> results/eda/
