"""Stage 4: does removing highly correlated features (Spearman |rho|) help the CCTV (T3) tree?

Orders the 32 candidates by the T3 tree's own importance, then compares
  (a) correlation filter (|rho| >= 0.99 / 0.95 / 0.9, keep the more important twin) then top-k
  (b) no filter, top-k
Correlation is used as a reference, not as a mechanical rule: stage 5 keeps (b).

Usage: python src/s04_correlation_filter.py data/MedSec-25.csv
"""
import argparse
import numpy as np, pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import f1_score

from common import load, log, tier_mask, class_weights

ap = argparse.ArgumentParser(); ap.add_argument('csv'); a = ap.parse_args()
D = load(a.csv)
tr, te, ys = D.tr, D.te, D.ys
T3 = tier_mask(D, 'T3')
G = D.LIGHT + D.WIN; XG = D.prep(G); gi = {f: i for i, f in enumerate(G)}
W = class_weights(ys[tr & T3])


def fit(feats):
    cols = [gi[f] for f in feats]; mtr, mte = tr & T3, te & T3
    m = DecisionTreeClassifier(max_depth=10, min_samples_leaf=5, class_weight=W, random_state=0).fit(XG[mtr][:, cols], ys[mtr])
    pr = m.predict(XG[mte][:, cols]); yt = ys[mte]; atk, fl = yt != 'Benign', pr != 'Benign'
    lat = f1_score(yt, pr, labels=['Lateral movement'], average=None)[0]
    return m, f'macroF1={f1_score(yt, pr, average="macro"):.3f} recall={fl[atk].mean():.4f} FPR={fl[~atk].mean():.4f} lateralF1={lat:.3f} nodes={m.tree_.node_count}'


m32, r = fit(G); log('[32 candidates]', r)
imp32 = [f for v, f in sorted(zip(m32.feature_importances_, G), reverse=True) if v > 0]
log('T3 tree importance order', imp32)
rng = np.random.default_rng(0); smp = rng.choice(np.where(tr)[0], 100000, replace=False)   # train rows only
R = pd.DataFrame(XG[smp], columns=G).rank().corr().abs()                                    # Spearman
for th in [0.99, 0.95, 0.9]:
    kept = []
    for f in imp32 + [f for f in G if f not in imp32]:
        if not any(R.loc[f, k] >= th for k in kept): kept.append(f)
    log(f'\n[corr filter |rho|>={th}] kept {len(kept)}')
    for k in [8, 10, 12, 15]:
        _, r = fit(kept[:k]); log(f'   top-{k}: {r}')
    log('   top-12 set', kept[:12])
for k in [10, 12, 15]:
    _, r = fit(imp32[:k]); log(f'[no corr filter] top-{k}: {r}')
