"""Stage 5: final shared feature set (k = 12) and the three deployable tier trees.

Features = top-k of the CCTV (T3) tree importance order (stage 4), shared by all three tiers so the
gateway computes them once. Compares k = 6, 8, 10, 12, 15 and saves the k = 12 models.

Usage: python src/s05_final_models.py data/MedSec-25.csv [--out outputs]
"""
import argparse, json, os, pickle
import numpy as np, pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import f1_score

from common import load, log, tier_mask, class_weights, count_alerts

ap = argparse.ArgumentParser(); ap.add_argument('csv'); ap.add_argument('--out', default='outputs')
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
D = load(a.csv)
tr, te, ys = D.tr, D.te, D.ys
G = D.LIGHT + D.WIN; XG = D.prep(G); gi = {f: i for i, f in enumerate(G)}
SC = {'T1': (tier_mask(D, 'T1'), 10.0), 'T2': (tier_mask(D, 'T2'), 1.0), 'T3': (tier_mask(D, 'T3'), 1.0)}

# T3 tree importance order on the 32 candidates (same model as stage 4)
T3 = SC['T3'][0]
m32 = DecisionTreeClassifier(max_depth=10, min_samples_leaf=5, class_weight=class_weights(ys[tr & T3]),
                             random_state=0).fit(XG[tr & T3], ys[tr & T3])
IMP = [f for v, f in sorted(zip(m32.feature_importances_, G), reverse=True) if v > 0]
log('T3 importance order', IMP)

rng = np.random.default_rng(0); smp = rng.choice(np.where(tr)[0], 100000, replace=False)
R = pd.DataFrame(XG[smp], columns=G).rank().corr().abs()
keep = {}
for k in [6, 8, 10, 12, 15]:
    feats = IMP[:k]; cols = [gi[f] for f in feats]; out = {}; ben = te & (ys == 'Benign'); fl = []
    for t, (sc, bm) in SC.items():
        mtr, mte = tr & sc, te & sc
        m = DecisionTreeClassifier(max_depth=10, min_samples_leaf=5, class_weight=class_weights(ys[mtr], bm),
                                   random_state=0).fit(XG[mtr][:, cols], ys[mtr])
        pr = m.predict(XG[mte][:, cols]); yt = ys[mte]; atk, f_ = yt != 'Benign', pr != 'Benign'
        extra = (f' lateralF1={f1_score(yt, pr, labels=["Lateral movement"], average=None)[0]:.3f}'
                 f' pwF1={f1_score(yt, pr, labels=["Device PW guess"], average=None)[0]:.3f}') if t == 'T3' else ''
        out[t] = m; fl.append(m.predict(XG[ben][:, cols]) != 'Benign')
        log(f'[k={k}] {t}: macroF1={f1_score(yt, pr, average="macro"):.3f} recall={f_[atk].mean():.4f} '
            f'FPR={f_[~atk].mean():.4f} nodes={m.tree_.node_count}{extra}')
    u = fl[0] | fl[1] | fl[2]
    sub = R.loc[feats, feats].values; iu = np.triu_indices(len(feats), 1)
    log(f'[k={k}] union FPR={u.mean():.4f} false_alerts={count_alerts(D, ben, np.where(u, "X", "Benign"))} '
        f'| within-set max|rho|={sub[iu].max():.3f} pairs>=0.9={(sub[iu] >= 0.9).sum()}')
    if k == 12:
        log('   k=12 features', feats)
        log('   k=12 pairs |rho|>=0.9', [(feats[i], feats[j], round(float(sub[i, j]), 3)) for i, j in zip(*iu) if sub[i, j] >= 0.9])
    keep[k] = (feats, out)

feats12, models12 = keep[12]
pickle.dump({'features': feats12, 'models': models12}, open(os.path.join(a.out, 'tier_models_k12.pkl'), 'wb'))
json.dump({'features': feats12}, open(os.path.join(a.out, 'features_k12.json'), 'w'), indent=1)

# small test sample for the C agreement check (stage 6)
idx = np.where(te)[0]; idx = rng.choice(idx, min(20000, len(idx)), replace=False)
np.save(os.path.join(a.out, 'test_sample_k12.npy'), XG[idx][:, [gi[f] for f in feats12]].astype(np.float32))
log('[SAVED]', os.path.join(a.out, 'tier_models_k12.pkl'))
