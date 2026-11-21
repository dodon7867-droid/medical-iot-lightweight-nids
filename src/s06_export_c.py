"""Stage 6: export the three k = 12 tier trees to C with emlearn and check them.

Writes c/models/k12_T{1,2,3}.h, a test sample, and the sklearn predictions for that sample.
Then `make -C c check` compiles each tree and reports: C vs sklearn agreement, ns per flow, code size.

dtype='float' matters: emlearn's default int16 conversion truncates thresholds such as
'Flow IAT Min' and disagrees with sklearn on part of the flows.

Usage: python src/s06_export_c.py [--out outputs] [--cdir c]
"""
import argparse, json, os, pickle
import numpy as np
import emlearn

ap = argparse.ArgumentParser(); ap.add_argument('--out', default='outputs'); ap.add_argument('--cdir', default='c')
a = ap.parse_args()
P = pickle.load(open(os.path.join(a.out, 'tier_models_k12.pkl'), 'rb'))
X = np.load(os.path.join(a.out, 'test_sample_k12.npy')).astype(np.float32)
mdir = os.path.join(a.cdir, 'models'); os.makedirs(mdir, exist_ok=True)
X.tofile(os.path.join(a.cdir, 'X.bin'))
meta = {'n_rows': int(X.shape[0]), 'n_features': int(X.shape[1]), 'features': P['features'], 'classes': {}}
for t, m in P['models'].items():
    name = f'k12_{t}'
    emlearn.convert(m, method='inline', dtype='float').save(file=os.path.join(mdir, name + '.h'), name=name)
    cls = list(m.classes_); meta['classes'][t] = cls
    y = np.array([cls.index(v) for v in m.predict(X.astype(np.float64))], dtype=np.int32)
    y.tofile(os.path.join(a.cdir, f'y_{t}.bin'))
    print(f'[{t}] nodes={m.tree_.node_count} classes={cls} -> {mdir}/{name}.h')
json.dump(meta, open(os.path.join(a.cdir, 'meta.json'), 'w'), indent=1)
