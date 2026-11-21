"""Stage 3: many features vs few features.

Compares, for the three tier trees together:
  RF on all 65 flow features + 4 window features, tree on 65+4, tree on 32 candidates,
  and trees on the top-k features of a Random Forest importance ranking (k = 20, 15, 12, 10, 8, 6).

Usage: python src/s03_feature_count.py data/MedSec-25.csv
"""
import argparse
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score

from common import load, log, tier_mask, class_weights, count_alerts

ap = argparse.ArgumentParser(); ap.add_argument('csv'); a = ap.parse_args()
D = load(a.csv)
tr, te, ys = D.tr, D.te, D.ys
SC = [('T1', tier_mask(D, 'T1'), 10.0), ('T2', tier_mask(D, 'T2'), 1.0), ('T3', tier_mask(D, 'T3'), 1.0)]
G = D.LIGHT + D.WIN
XG = D.prep(G)
rk = RandomForestClassifier(100, n_jobs=-1, random_state=0, class_weight='balanced', max_depth=16).fit(XG[tr], ys[tr])
rank = [f for _, f in sorted(zip(rk.feature_importances_, G), reverse=True)]
log('RF importance ranking', rank)


def evalset(name, cols, model_fn):
    X = D.prep(cols); out = {}; flags = []; ben = te & (ys == 'Benign')
    for tag, sc, bm in SC:
        mtr, mte = tr & sc, te & sc
        m = model_fn(class_weights(ys[mtr], benign_mult=bm)).fit(X[mtr], ys[mtr]); pr = m.predict(X[mte]); yt = ys[mte]
        atk, fl = yt != 'Benign', pr != 'Benign'
        nodes = m.tree_.node_count if hasattr(m, 'tree_') else None
        out[tag] = (round(f1_score(yt, pr, average='macro'), 3), round(fl[atk].mean(), 4), round(fl[~atk].mean(), 4), nodes)
        flags.append(m.predict(X[ben]) != 'Benign')
        if tag == 'T3':
            labs = sorted(set(yt)); out['T3cls'] = dict(zip(labs, np.round(f1_score(yt, pr, labels=labs, average=None), 3)))
    u = flags[0] | flags[1] | flags[2]
    log(f'\n[{name}] n={len(cols)}')
    for tag in ['T1', 'T2', 'T3']:
        f, r, fp, nd = out[tag]; log(f'   {tag}: macroF1={f} recall={r} FPR={fp} nodes={nd}')
    log('   T3 per-class', out['T3cls'])
    log(f'   union FPR={u.mean():.4f} false_alerts={count_alerts(D, ben, np.where(u, "X", "Benign"))}')


dt = lambda w: DecisionTreeClassifier(max_depth=10, min_samples_leaf=5, class_weight=w, random_state=0)
rf = lambda w: RandomForestClassifier(100, n_jobs=-1, random_state=0, class_weight=w, max_depth=16)
evalset('RF all 65+4', D.FULL + D.WIN, rf)
evalset('Tree all 65+4', D.FULL + D.WIN, dt)
for k in [32, 20, 15, 12, 10, 8, 6]:
    cols = rank[:k] if k < 32 else G
    evalset(f'Tree top-{k} (RF ranking)', cols, dt)
    if k <= 15: log('   features', cols)
