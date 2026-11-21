"""Stage 1: rule baseline vs Random Forest vs decision tree on the 5 MedSec-25 classes.

Shows (a) that identity columns inflate scores, (b) what the source time-window features add,
(c) per-capture benign false positives (does the model learn the capture instead of the attack?),
(d) operator-level false alerts.

Usage: python src/s01_baselines.py data/MedSec-25.csv [--out outputs]
"""
import argparse, os, time
import numpy as np, pandas as pd, joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import f1_score, precision_recall_fscore_support

from common import load, log, CLASSES, count_alerts

ap = argparse.ArgumentParser(); ap.add_argument('csv'); ap.add_argument('--out', default='outputs')
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
D = load(a.csv)
d, y, cap, att, tr, te = D.d, D.y, D.cap, D.att, D.tr, D.te
FULL, IDENT, LIGHT, WIN, prep = D.FULL, D.IDENT, D.LIGHT, D.WIN, D.prep


def ev(name, cols, mdl):
    X = prep(cols); t = time.time(); mdl.fit(X[tr], y[tr]); pr = mdl.predict(X[te]); yt = y[te]
    mf = f1_score(yt, pr, average='macro')
    p, r, f, s = precision_recall_fscore_support(yt, pr, labels=CLASSES, zero_division=0)
    # "unseen": test rows whose exact feature vector never appears in train
    h = pd.util.hash_pandas_object(pd.DataFrame(X), index=False).values
    un = ~np.isin(h[te], np.unique(h[tr]))
    mfu = f1_score(yt[un], pr[un], average='macro')
    fu = f1_score(yt[un], pr[un], labels=CLASSES, average=None, zero_division=0)
    log(f'\n[{name}] n_feat={len(cols)} macroF1={mf:.3f} unseen_macroF1={mfu:.3f} unseen_frac={un.mean():.3f} fit={time.time()-t:.0f}s')
    for c, pp, rr, ff, ss, fuu in zip(CLASSES, p, r, f, s, fu):
        log(f'   {c:17s} P={pp:.3f} R={rr:.3f} F1={ff:.3f} n={ss} | unseenF1={fuu:.3f} n_unseen={int(((yt==c)&un).sum())}')
    capte = cap[te]
    log('   benignFP_by_capture', {c: round(float((pr[(yt == 'Benign') & (capte == c)] != 'Benign').mean()), 4) for c in CLASSES})
    ba, bp = (yt != 'Benign'), (pr != 'Benign')
    log(f'   binary: attack_recall={bp[ba].mean():.4f} benign_FPR={bp[~ba].mean():.4f} binF1={f1_score(ba, bp):.4f}')
    m = att[te] == 'vm'
    log(f'   pw-guess flows: detected={bp[m].mean():.3f} as_initial={(pr[m] == "Initial access").mean():.3f} n={int(m.sum())}')
    if hasattr(mdl, 'tree_'):
        used = sorted({cols[i] for i in mdl.tree_.feature if i >= 0})
        log(f'   tree nodes={mdl.tree_.node_count} depth={mdl.get_depth()} leaves={mdl.get_n_leaves()} used={len(used)}')
    imp = sorted(zip(mdl.feature_importances_, cols), reverse=True)[:10]
    log('   top10', [(c, round(float(v), 3)) for v, c in imp])
    return mdl, pr


# rule baseline: same-source flow count in the last 60 s, threshold chosen on train
w = d['w60_flows'].values; best = None
for th in [2, 3, 5, 8, 10, 15, 20, 30, 50, 75, 100, 150, 200, 300, 500, 1000]:
    fb = f1_score(y[tr] != 'Benign', w[tr] >= th)
    if best is None or fb > best[0]: best = (fb, th)
th = best[1]; bp = w[te] >= th; yt = y[te]
log(f'\n[RULE w60_flows>={th}] binF1={f1_score(yt != "Benign", bp):.4f} attack_recall={bp[yt != "Benign"].mean():.4f} benign_FPR={bp[yt == "Benign"].mean():.4f}')
for c in CLASSES[1:]: log(f'   recall {c}: {bp[yt == c].mean():.3f}')

rf = lambda: RandomForestClassifier(100, n_jobs=-1, random_state=0, class_weight='balanced', max_depth=16)
dt = lambda: DecisionTreeClassifier(max_depth=10, min_samples_leaf=5, class_weight='balanced', random_state=0)
ev('B-ident  RF full+identity', FULL + IDENT, rf())
ev('B        RF full', FULL, rf())
_, prBW = ev('B+W      RF full+window', FULL + WIN, rf())
ev('A        DT light', LIGHT, dt())
mAW, prAW = ev('A+W      DT light+window', LIGHT + WIN, dt())
ev('A+W d6   DT light+window depth6', LIGHT + WIN,
   DecisionTreeClassifier(max_depth=6, min_samples_leaf=5, class_weight='balanced', random_state=0))

bt = d[te & (y == 'Benign')].groupby('cap').ts.agg(['min', 'max'])
hrs = float(((bt['max'] - bt['min']).dt.total_seconds() / 3600).sum())
for name, pr in [('A+W', prAW), ('B+W', prBW)]:
    n = count_alerts(D, te, pr)
    log(f'[ALERT {name}] false alerts={n} over {hrs:.2f} test-benign hours ({n / max(hrs, 1e-9):.2f}/h)')
joblib.dump({'model': mAW, 'features': LIGHT + WIN, 'classes': list(mAW.classes_)}, os.path.join(a.out, 'tree_5class.joblib'))
