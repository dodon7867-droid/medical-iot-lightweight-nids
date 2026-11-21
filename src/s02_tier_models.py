"""Stage 2: one small tree per device tier (= scenario), 32 candidate features.

T1 life-support / patient monitoring : Benign vs MQTT attack       (alert only, never auto-block)
T2 clinical support server           : Benign vs Server SSH guess  (alert, block external only if confident)
T3 CCTV chain                        : Benign vs Recon / Device PW guess / Lateral / Exfiltration (auto-block external)

Also tests the cost weights (benign x10 = false positives are expensive, attack x10 = misses are
expensive) and whether probability thresholds change anything (trees saturate at 0/1).

Usage: python src/s02_tier_models.py data/MedSec-25.csv [--out outputs]
"""
import argparse, os, pickle
import numpy as np, pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import f1_score

from common import load, log, tier_mask, class_weights, count_alerts

ap = argparse.ArgumentParser(); ap.add_argument('csv'); ap.add_argument('--out', default='outputs')
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
D = load(a.csv)
tr, te, ys = D.tr, D.te, D.ys
X = D.prep(D.LIGHT + D.WIN)
log('labels', pd.Series(ys).value_counts().to_dict())
log('test counts', pd.Series(ys[te]).value_counts().to_dict())


def run(name, scope, weights):
    mtr, mte = tr & scope, te & scope
    mdl = DecisionTreeClassifier(max_depth=10, min_samples_leaf=5, class_weight=weights, random_state=0)
    mdl.fit(X[mtr], ys[mtr]); pr = mdl.predict(X[mte]); yt = ys[mte]
    labs = sorted(set(yt)); f = f1_score(yt, pr, labels=labs, average=None)
    atk, flag = yt != 'Benign', pr != 'Benign'
    used = len({i for i in mdl.tree_.feature if i >= 0})
    log(f'\n[{name}] nodes={mdl.tree_.node_count} used={used} macroF1={f1_score(yt, pr, average="macro"):.3f} '
        f'attack_recall={flag[atk].mean():.4f} benign_FPR={flag[~atk].mean():.4f} false_alerts={count_alerts(D, mte, pr)}')
    log('   F1', {l: (round(float(v), 3), int((yt == l).sum())) for l, v in zip(labs, f)})
    return mdl, mte


def thr(name, mdl, mte):
    P = mdl.predict_proba(X[mte]); bi = list(mdl.classes_).index('Benign'); p = 1 - P[:, bi]
    atk = ys[mte] != 'Benign'
    log(f'[THR {name}] share of flows with 0.05<p<0.95 = {((p > 0.05) & (p < 0.95)).mean():.4f}')
    for t in [0.09, 0.5, 0.9]:
        fl = p >= t; log(f'   t={t:.2f} recall={fl[atk].mean():.4f} FPR={fl[~atk].mean():.4f}')


T1, T2, T3 = (tier_mask(D, t) for t in ['T1', 'T2', 'T3'])
cw = lambda m, **k: class_weights(ys[tr & m], **k)
run('T1 life-support MQTT, balanced', T1, cw(T1))
m1, te1 = run('T1 life-support MQTT, benign x10', T1, cw(T1, benign_mult=10))
m2b, te2 = run('T2 clinical-support server SSH, balanced', T2, cw(T2))
m2f, _ = run('T2 clinical-support server SSH, benign x10', T2, cw(T2, benign_mult=10))
m3, te3 = run('T3 CCTV chain, balanced', T3, cw(T3))
run('T3 CCTV chain, attack x10', T3, cw(T3, attack_mult=10))
run('T3 CCTV chain, benign x10', T3, cw(T3, benign_mult=10))
thr('T3 tree', m3, te3); thr('T1 tree benign x10', m1, te1); thr('T2 tree balanced', m2b, te2)

ben_te = te & (ys == 'Benign'); Xb = X[ben_te]
for tag, m2 in [('T2 balanced', m2b), ('T2 benign x10', m2f)]:
    fl = [(m.predict(Xb) != 'Benign') for m in (m1, m2, m3)]; u = fl[0] | fl[1] | fl[2]
    log(f'[UNION with {tag}] FPR={u.mean():.4f} per={[round(float(f.mean()), 4) for f in fl]} '
        f'false_alerts={count_alerts(D, ben_te, np.where(u, "X", "Benign"))}')
pickle.dump({'T1': m1, 'T2': m2b, 'T3': m3, 'features': D.LIGHT + D.WIN}, open(os.path.join(a.out, 'tier_models_32.pkl'), 'wb'))
