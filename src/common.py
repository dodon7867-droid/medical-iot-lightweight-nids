"""Shared data pipeline for all stages.

load(csv_path) does, in order:
  1. data inventory (columns, constants, inf/nan/negative values, label counts)
  2. flow-level relabel (MedSec-25 ships capture-level labels; see README)
  3. drop Protocol 0 flows
  4. causal source time-window features (w10_flows, w60_flows, w60_dports, w60_dsts)
  5. drop attacker background flows and negative-time flows
  6. chronological 70/30 split inside each (capture, label, attack source)

It returns a SimpleNamespace so every stage script uses the exact same data.
"""
import time
from types import SimpleNamespace

import numpy as np
import pandas as pd


def log(*a):
    print(*a, flush=True)


# Hosts in the MedSec-25 testbed (from the dataset paper and the capture contents)
ATTACKERS = {'192.168.1.108', '10.0.2.15'}          # .108 = MQTT attacker, 10.0.2.15 = VM attacker
PIS = {'192.168.1.101', '192.168.1.102', '192.168.1.103'}  # Raspberry Pi devices
SERVER = '192.168.1.104'
PIVOT = '192.168.1.103'                              # compromised device used for lateral movement
BACKGROUND_PORTS = {53, 67, 68, 123, 137, 138, 1900, 5353, 5355}  # DNS, DHCP, NTP, NetBIOS, SSDP, mDNS, LLMNR
SERVICE_PORTS = [21, 22, 23, 80, 443, 445, 3389, 5985]

ID_COLS = ['Flow ID', 'Src IP', 'Src Port', 'Dst IP', 'Dst Port', 'Timestamp', 'Label']
IDENTITY_COLS = ['Protocol', 'Init Fwd Win Byts', 'Init Bwd Win Byts']
LIGHT0 = ['Flow Duration', 'Tot Fwd Pkts', 'Tot Bwd Pkts', 'TotLen Fwd Pkts', 'TotLen Bwd Pkts',
          'Fwd Pkt Len Max', 'Fwd Pkt Len Min', 'Fwd Pkt Len Mean', 'Bwd Pkt Len Max', 'Bwd Pkt Len Min',
          'Bwd Pkt Len Mean', 'Flow Byts/s', 'Flow Pkts/s', 'Flow IAT Mean', 'Flow IAT Max', 'Flow IAT Min',
          'Fwd IAT Min', 'Bwd IAT Min', 'Fwd Header Len', 'Bwd Header Len', 'Pkt Len Min', 'Pkt Len Max',
          'Pkt Len Mean', 'FIN Flag Cnt', 'SYN Flag Cnt', 'RST Flag Cnt', 'PSH Flag Cnt', 'ACK Flag Cnt']
WIN = ['w10_flows', 'w60_flows', 'w60_dports', 'w60_dsts']
CLASSES = ['Benign', 'Reconnaissance', 'Initial access', 'Lateral movement', 'Exfiltration']

# Tier (= scenario) label scopes
TIER_SCOPES = {
    'T1': ['Benign', 'MQTT attack'],                       # life-support / patient monitoring
    'T2': ['Benign', 'Server SSH guess'],                  # clinical support server
    'T3': ['Benign', 'Reconnaissance', 'Device PW guess',  # CCTV chain
           'Lateral movement', 'Exfiltration'],
}


def _windows(o, cap_, src_, sec_, dp_, di_, W):
    """Per (capture, source): flows, distinct dst ports, distinct dst IPs in the last W seconds (causal)."""
    n = len(o); f = [0] * n; pc = [0] * n; ic = [0] * n; i = 0
    while i < n:
        j = i + 1
        while j < n and src_[j] == src_[i] and cap_[j] == cap_[i]: j += 1
        cp = {}; ci = {}; tot = 0; left = i; k = i
        while k < j:
            m = k + 1
            while m < j and sec_[m] == sec_[k]: m += 1
            for r in range(k, m):
                cp[dp_[r]] = cp.get(dp_[r], 0) + 1; ci[di_[r]] = ci.get(di_[r], 0) + 1
            tot += m - k; lim = sec_[k] - W
            while sec_[left] <= lim:
                p = dp_[left]; cp[p] -= 1
                if cp[p] == 0: del cp[p]
                q = di_[left]; ci[q] -= 1
                if ci[q] == 0: del ci[q]
                tot -= 1; left += 1
            for r in range(k, m): f[r] = tot; pc[r] = len(cp); ic[r] = len(ci)
            k = m
        i = j
    out = [np.empty(n, np.int32) for _ in range(3)]
    for arr, src in zip(out, (f, pc, ic)): arr[o] = src
    return out


def load(csv_path, verbose=True):
    say = log if verbose else (lambda *a: None)
    t0 = time.time()
    d = pd.read_csv(csv_path, low_memory=False)
    d.columns = [c.strip() for c in d.columns]

    # ---- 1) inventory ----
    say('[INV] rows', len(d), 'cols', d.shape[1])
    feat = [c for c in d.columns if c not in ID_COLS]
    say('[INV] feature cols', len(feat))
    say('[INV] non-numeric', [c for c in feat if not pd.api.types.is_numeric_dtype(d[c])])
    const = [c for c in feat if d[c].nunique(dropna=False) <= 1]
    say('[INV] constant', len(const), const)
    A = d[feat].to_numpy(dtype='float64')
    say('[INV] inf', {c: int(v) for c, v in zip(feat, np.isinf(A).sum(0)) if v})
    say('[INV] nan', {c: int(v) for c, v in zip(feat, np.isnan(A).sum(0)) if v})
    say('[INV] negative', {c: int(v) for c, v in zip(feat, (A < 0).sum(0)) if v})
    del A
    say('[INV] duplicate full rows', int(d.duplicated().sum()))
    say('[INV] label counts', d.Label.value_counts().to_dict())
    say('[INV] protocol counts', d.Protocol.value_counts().to_dict())

    # ---- 2) flow-level relabel ----
    S, T = d['Src IP'].astype(str), d['Dst IP'].astype(str)
    P, SP, L = d['Dst Port'], d['Src Port'], d['Label']
    MC = T.str.startswith(('224.', '239.', '255.')) | S.str.startswith(('224.', '239.', '255.'))
    internal = lambda x: x.str.startswith('192.168.1.')
    att_any = S.isin(ATTACKERS) | T.isin(ATTACKERS)
    # rule 1: non-benign capture + flow touches an attacker (minus attacker background traffic)
    r1 = (L != 'Benign') & att_any
    r1_bg = r1 & (P.isin(BACKGROUND_PORTS) | SP.isin(BACKGROUND_PORTS) | MC)
    # rule 2: exfiltration = device <-> server transfer inside the exfiltration capture
    r2 = L.eq('Exfiltration') & ((S.isin(PIS) & T.eq(SERVER)) | (S.eq(SERVER) & T.isin(PIS)))
    # rule 3: lateral movement = pivot device -> other internal hosts (no attacker, no background)
    r3 = L.eq('Lateral movement') & ~att_any & (
        (S.eq(PIVOT) & internal(T) & ~T.eq(PIVOT) & ~P.isin(BACKGROUND_PORTS) & ~MC
         & ~(T.eq('192.168.1.101') & P.eq(1883)))
        | (T.eq(PIVOT) & internal(S) & SP.isin(SERVICE_PORTS)))
    say('[RELABEL] lateral pivot->external kept benign (exception)',
        int((L.eq('Lateral movement') & S.eq(PIVOT) & ~internal(T) & ~MC).sum()))
    # rule 4: everything else is benign
    d['y'] = np.where((r1 & ~r1_bg) | r2 | r3, L, 'Benign')
    d['cap'] = L
    d['att'] = np.select([S.eq('10.0.2.15') | T.eq('10.0.2.15'), S.eq('192.168.1.108') | T.eq('192.168.1.108')],
                         ['vm', '108'], 'none')
    d['drop_bg'] = r1_bg.values
    TIMEC = [c for c in feat if ('IAT' in c or 'Duration' in c or c.endswith('/s'))]
    negt = (d[TIMEC] < 0).any(axis=1)
    d['drop_neg'] = negt.values
    say('[CLEAN] negative-time rows', int(negt.sum()), 'by y', d.loc[negt, 'y'].value_counts().to_dict())

    # ---- 3) drop Protocol 0 ----
    p0 = d.Protocol.eq(0)
    say('[RELABEL] drop protocol0', int(p0.sum()), 'attacker-bg', int((r1_bg & ~p0).sum()))
    d = d[~p0].reset_index(drop=True)

    # ---- 4) source time-window features (computed before the drops so counts see all traffic) ----
    d['ts'] = pd.to_datetime(d['Timestamp'], format='%d/%m/%Y %I:%M:%S %p', errors='coerce')
    say('[TS] NaT', int(d.ts.isna().sum()), 'range', d.ts.min(), d.ts.max())
    d['sec'] = d.ts.values.astype('datetime64[s]').astype('int64')
    capv, srcv, secv = d['cap'].astype(str).values, d['Src IP'].astype(str).values, d['sec'].values
    o = np.lexsort((secv, srcv, capv))
    args = (o, capv[o].tolist(), srcv[o].tolist(), secv[o].tolist(),
            d['Dst Port'].values[o].tolist(), d['Dst IP'].astype(str).values[o].tolist())
    t = time.time()
    w60f, w60p, w60i = _windows(*args, 60); w10f, _, _ = _windows(*args, 10)
    d['w10_flows'], d['w60_flows'], d['w60_dports'], d['w60_dsts'] = w10f, w60f, w60p, w60i
    say(f'[WIN] done {time.time() - t:.0f}s')

    # ---- 5) drop attacker background + negative-time flows ----
    say('[CLEAN] drop attacker-bg', int(d.drop_bg.sum()), 'drop negative-time', int((d.drop_neg & ~d.drop_bg).sum()))
    d = d[~(d.drop_bg | d.drop_neg)].reset_index(drop=True)
    say('[DATA] after drops', len(d))
    say(pd.crosstab(d.cap, d.y).to_string())

    # ---- 6) chronological 70/30 split inside each (capture, label, attack source) ----
    d = d.sort_values(['cap', 'y', 'att', 'ts'], kind='stable').reset_index(drop=True)
    g = d.groupby(['cap', 'y', 'att'])
    split_rank = (g.cumcount() / g['ts'].transform('size')).values
    tr = split_rank < 0.7; te = ~tr
    y, cap, att = d.y.values, d.cap.values, d.att.values
    say('[SPLIT] train', int(tr.sum()), 'test', int(te.sum()))
    say('[SPLIT] test per class', pd.Series(y[te]).value_counts().to_dict())

    feat2 = [c for c in feat if d[c].nunique() > 1]
    IDENT = [c for c in IDENTITY_COLS if c in feat2]
    FULL = [c for c in feat2 if c not in IDENT]
    say('[FEAT] constant after cleaning', len(feat) - len(feat2), [c for c in feat if c not in feat2])
    say('[FEAT] identity removed', IDENT, '-> FULL', len(FULL))
    LIGHT = [c for c in LIGHT0 if c in FULL]
    say('[FEAT] LIGHT', len(LIGHT), 'missing/const', [c for c in LIGHT0 if c not in FULL])

    # 7 flow labels: split "Initial access" by target
    S_ip, T_ip = d['Src IP'].astype(str).values, d['Dst IP'].astype(str).values
    srv = (S_ip == SERVER) | (T_ip == SERVER)
    ys = y.astype(object).copy()
    pwv = (y == 'Initial access') & (att == 'vm')
    ys[(y == 'Initial access') & (att == '108')] = 'MQTT attack'
    ys[pwv & srv] = 'Server SSH guess'
    ys[pwv & ~srv] = 'Device PW guess'

    def prep(cols):
        X = d[cols].to_numpy(dtype='float64'); X[~np.isfinite(X)] = -1; return X

    say(f'[LOAD] done {time.time() - t0:.0f}s')
    return SimpleNamespace(d=d, y=y, ys=ys, cap=cap, att=att, tr=tr, te=te, split_rank=split_rank,
                           FULL=FULL, IDENT=IDENT, LIGHT=LIGHT, WIN=WIN, prep=prep)


def tier_mask(D, tier):
    return np.isin(D.ys, TIER_SCOPES[tier])


def class_weights(labels, benign_mult=1.0, attack_mult=1.0):
    """'balanced' class weights, then scaled for the tier's cost of a false positive / false negative."""
    lab, c = np.unique(labels, return_counts=True)
    w = {l: len(labels) / (len(lab) * n) for l, n in zip(lab, c)}
    return {l: v * (benign_mult if l == 'Benign' else attack_mult) for l, v in w.items()}


def count_alerts(D, mask, pred):
    """Operator alerts from benign flows: >=3 flagged flows from one source within 10 min = 1 alert,
    then 10 min quiet period per source."""
    t = D.d.loc[mask, ['cap', 'Src IP', 'ts']].copy(); t['y'] = D.ys[mask]; t['flag'] = (pred != 'Benign')

    def cnt(times):
        n = 0; dq = []; last = None
        for x in times:
            dq.append(x); dq = [u for u in dq if (x - u).total_seconds() <= 600]
            if len(dq) >= 3 and (last is None or (x - last).total_seconds() > 600):
                n += 1; last = x; dq = []
        return n

    fp = t[(t.y == 'Benign') & t.flag].sort_values('ts')
    return sum(cnt(g.ts.tolist()) for _, g in fp.groupby(['cap', 'Src IP']))
