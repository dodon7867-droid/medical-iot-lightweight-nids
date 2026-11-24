"""EDA figures for the dataset (run after the data is in data/).

    python3 src/s07_eda.py data/MedSec-25.csv

Writes results/eda/eda1..eda5 as PNG plus a CSV of the plotted numbers for each
figure (the table view of the chart), and prints the key numbers to stdout.

Figures
  1 relabel   : share of benign flows inside each attack capture (why we relabel per flow)
  2 classes   : flows per label after relabel, log axis, colored by device tier
  3 windows   : the two source time-window features by stage (log axis, box = 25-75%, whiskers 5-95%)
  4 timeline  : flows per minute in each capture, train (first 70%) vs test (last 30%)
  5 columns   : how 84 CSV columns become the final 12 features
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from common import load, log  # noqa: E402

OUT = 'results/eda'

# ---- look (same palette as the slides; tier colors validated for CVD) ----
SURF, INK, INK2, MUTED, GRID = '#FBFAF7', '#13202F', '#3F4A5A', '#5A6474', '#E4E1D8'
GRAY, ACCENT, NAVY = '#7A8493', '#B8491A', '#2D5DA1'
T1, T2, T3 = '#2563B0', '#0E8A72', '#B8491A'

for path in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
             '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc']:
    if os.path.exists(path):
        font_manager.fontManager.addfont(path)
_names = {f.name for f in font_manager.fontManager.ttflist}
KR_FONT = next((n for n in ['IBM Plex Sans KR', 'Noto Sans CJK KR', 'Malgun Gothic', 'AppleGothic', 'NanumGothic']
                if n in _names), 'DejaVu Sans')   # first Korean font this computer has
plt.rcParams.update({
    'font.family': [KR_FONT, 'DejaVu Sans'],
    'font.size': 11, 'axes.unicode_minus': False,
    'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF,
    'axes.edgecolor': GRID, 'axes.labelcolor': INK2, 'xtick.color': MUTED, 'ytick.color': INK2,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.grid': False, 'grid.color': GRID, 'grid.linewidth': 0.8, 'grid.linestyle': '-',
})

STAGE_KO = {'Benign': '정상', 'Reconnaissance': '정찰', 'Initial access': '초기 침투',
            'Lateral movement': '내부 확산', 'Exfiltration': '유출'}
ORDER = ['Benign', 'Reconnaissance', 'Initial access', 'Lateral movement', 'Exfiltration']


def title(fig, main, sub):
    fig.text(0.012, 0.975, main, ha='left', va='top', fontsize=14, fontweight='bold', color=INK)
    fig.text(0.012, 0.905, sub, ha='left', va='top', fontsize=10.5, color=MUTED)


def save(fig, name, table):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(f'{OUT}/{name}.png', dpi=200)
    plt.close(fig)
    table.to_csv(f'{OUT}/{name}.csv', index=False)
    log(f'[SAVED] {OUT}/{name}.png')


def fig_relabel(D):
    ct = pd.crosstab(D.d.cap, D.y)
    rows = []
    for c in ['Reconnaissance', 'Initial access', 'Lateral movement', 'Exfiltration']:
        tot, ben = int(ct.loc[c].sum()), int(ct.loc[c, 'Benign'])
        rows.append((f'{STAGE_KO[c]} 녹화', ben, tot, 100 * ben / tot))
    t = pd.DataFrame(rows, columns=['capture', 'benign_flows', 'all_flows', 'benign_pct'])
    log('[EDA1] benign share in attack captures\n' + t.to_string(index=False))

    fig, ax = plt.subplots(figsize=(8, 3.6))
    fig.subplots_adjust(left=0.17, right=0.80, top=0.78, bottom=0.12)
    y = np.arange(len(t))[::-1]
    hi = t.benign_pct.idxmax()
    ax.barh(y, t.benign_pct, height=0.42, color=[ACCENT if i == hi else GRAY for i in t.index])
    for yi, (_, r) in zip(y, t.iterrows()):
        ax.text(r.benign_pct + 1.5, yi, f'{r.benign_pct:.1f}%  ({r.benign_flows:,} / {r.all_flows:,})',
                va='center', fontsize=10.5, color=INK if r.name == hi else INK2,
                fontweight='bold' if r.name == hi else 'normal')
    ax.set_yticks(y, t.capture)
    ax.set_xlim(0, 100)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    ax.set_xticks([0, 25, 50, 75, 100], ['0%', '25%', '50%', '75%', '100%'])
    ax.tick_params(length=0)
    ax.spines['left'].set_visible(False)
    title(fig, '공격 녹화 파일 안의 정상 flow 비율',
          '녹화 파일 하나에 라벨 하나가 붙어 있어, flow마다 통신 주체를 보고 라벨을 다시 붙였다 (MedSec-25, 정리 후 552,291 flow)')
    save(fig, 'eda1_relabel', t)


def fig_classes(D):
    s = pd.Series(D.ys).value_counts()
    spec = [('Benign', '정상', GRAY, '-'), ('Reconnaissance', '정찰', T3, 'T3'),
            ('MQTT attack', '초기 침투 · MQTT 서비스 공격', T1, 'T1'),
            ('Server SSH guess', '초기 침투 · 서버 SSH 대입', T2, 'T2'),
            ('Device PW guess', '초기 침투 · 기기 비밀번호 대입', T3, 'T3'),
            ('Lateral movement', '내부 확산', T3, 'T3'), ('Exfiltration', '유출', T3, 'T3')]
    t = pd.DataFrame([(lab, ko, tier, int(s.get(lab, 0))) for lab, ko, _, tier in spec],
                     columns=['label', 'label_ko', 'tier', 'flows'])
    log('[EDA2] flows per label\n' + t.to_string(index=False))
    log(f'[EDA2] largest/smallest = {t.flows.max():,}/{t.flows.min():,} = {t.flows.max() / t.flows.min():.0f}x')

    fig, ax = plt.subplots(figsize=(8, 4.2))
    fig.subplots_adjust(left=0.30, right=0.90, top=0.80, bottom=0.11)
    y = np.arange(len(t))[::-1]
    ax.barh(y, t.flows, height=0.46, color=[c for _, _, c, _ in spec])
    for yi, v in zip(y, t.flows):
        ax.text(v * 1.12, yi, f'{v:,}', va='center', fontsize=10.5, color=INK2)
    ax.set_xscale('log')
    ax.set_xlim(100, 2e6)
    ax.set_xticks([1e2, 1e3, 1e4, 1e5, 1e6], ['100', '1천', '1만', '10만', '100만'])
    ax.minorticks_off()
    ax.set_yticks(y, t.label_ko)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    ax.spines['left'].set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (T1, T2, T3, GRAY)]
    ax.legend(handles, ['T1 생명 유지', 'T2 진료 지원', 'T3 CCTV', '정상'], loc='lower right',
              frameon=False, fontsize=10, ncol=1)
    title(fig, '라벨별 flow 수 (로그 축)',
          f'가장 큰 정찰과 가장 작은 서버 SSH 대입은 {t.flows.max() / t.flows.min():,.0f}배 차이. 색은 그 공격을 맡는 기기 등급')
    save(fig, 'eda2_classes', t)


def fig_windows(D):
    feats = [('w60_dports', '최근 60초에 같은 출발지가 두드린 목적지 포트 수'),
             ('w10_flows', '최근 10초에 같은 출발지가 만든 flow 수')]
    rows = []
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    fig.subplots_adjust(left=0.07, right=0.99, top=0.76, bottom=0.12, wspace=0.22)
    for ax, (f, desc) in zip(axes, feats):
        data, meds = [], []
        for c in ORDER:
            v = D.d[f].values[D.y == c].astype(float)
            data.append(v + 1)
            q = np.percentile(v, [5, 25, 50, 75, 95])
            meds.append(q[2])
            rows.append((f, STAGE_KO[c], len(v), *q))
        bp = ax.boxplot(data, whis=(5, 95), showfliers=False, widths=0.42, patch_artist=True,
                        medianprops=dict(color=SURF, linewidth=2), whiskerprops=dict(color=MUTED),
                        capprops=dict(color=MUTED))
        for i, b in enumerate(bp['boxes']):
            b.set_facecolor(GRAY if i == 0 else NAVY)
            b.set_edgecolor(GRAY if i == 0 else NAVY)
        ax.set_yscale('log')
        ax.set_ylim(0.8, 1.2e5)
        ax.set_yticks([1, 11, 101, 1001, 10001, 100001], ['0', '10', '100', '1천', '1만', '10만'])   # values are plotted as v + 1
        ax.minorticks_off()
        ax.yaxis.grid(True)
        ax.set_axisbelow(True)
        ax.set_xticks(range(1, 6), [STAGE_KO[c] for c in ORDER])
        ax.tick_params(length=0)
        k = int(np.argmax(meds))
        for i in sorted({0, k}):
            ax.text(i + 1.28, meds[i] + 1, f'중앙값 {meds[i]:,.0f}', va='center', fontsize=9.5, color=INK2)
        ax.set_title(f'{f}\n{desc}', loc='left', fontsize=10.5, color=INK2, pad=8)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (GRAY, NAVY)]
    axes[1].legend(handles, ['정상', '공격'], loc='upper right', frameon=False, fontsize=10)
    title(fig, '트리가 가장 많이 쓰는 출발지 시간창 피처 2개의 분포 (로그 축)',
          '상자 = 가운데 50%, 선 = 5~95%. 정찰과 초기 침투는 정상과 크게 갈리고, 내부 확산은 정상과 겹친다')
    t = pd.DataFrame(rows, columns=['feature', 'stage', 'flows', 'p5', 'p25', 'median', 'p75', 'p95'])
    log('[EDA3] window features by stage\n' + t.to_string(index=False))
    save(fig, 'eda3_windows', t)


def fig_timeline(D):
    d = pd.DataFrame({'cap': D.d.cap.values, 'ts': D.d.ts.values, 'te': D.te})
    caps = ['Benign', 'Reconnaissance', 'Initial access', 'Exfiltration', 'Lateral movement']
    fig, axes = plt.subplots(len(caps), 1, figsize=(10, 7.4))
    fig.subplots_adjust(left=0.13, right=0.98, top=0.85, bottom=0.07, hspace=1.05)
    rows = []
    for ax, c in zip(axes, caps):
        g = d[d.cap == c]
        t0 = g.ts.min()
        mins = ((g.ts - t0).dt.total_seconds() // 60).astype(int)
        span = int(mins.max()) + 1
        tr = np.bincount(mins[~g.te.values], minlength=span)
        te = np.bincount(mins[g.te.values], minlength=span)
        x = np.arange(span)
        unit, div = ('시간', 60.0) if span > 180 else ('분', 1.0)
        ax.bar(x / div, tr, width=1 / div, color=NAVY, linewidth=0)
        ax.bar(x / div, te, width=1 / div, bottom=tr, color=ACCENT, linewidth=0)
        ax.set_xlim(0, span / div)
        ax.set_yticks([])
        ax.spines['left'].set_visible(False)
        ax.tick_params(length=0, labelsize=9.5)
        ax.text(-0.01, 0.5, f'{STAGE_KO[c]} 녹화', transform=ax.transAxes, ha='right', va='center',
                fontsize=10.5, color=INK)
        ax.text(1.0, 1.12, f'{t0:%Y-%m-%d} 시작 · {span / div:,.1f}{unit} · {len(g):,} flow · 분당 최대 {int((tr + te).max()):,}',
                transform=ax.transAxes, ha='right', va='bottom', fontsize=9, color=MUTED)
        ax.set_xlabel(f'녹화 시작부터 ({unit})', fontsize=8.5, color=MUTED, labelpad=0)
        rows.append((c, str(t0), span, len(g), int(tr.sum()), int(te.sum())))
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (NAVY, ACCENT)]
    fig.legend(handles, ['학습 (각 묶음의 앞 70%)', '평가 (뒤 30%)'], loc='upper right',
               bbox_to_anchor=(0.98, 0.985), frameon=False, fontsize=10, ncol=2)
    title(fig, '녹화별 분당 flow 수와 시간순 분할',
          '(녹화 × 라벨 × 공격 출발지) 묶음마다 시간 앞 70%로 학습, 뒤 30%로 평가. 세로 축은 녹화마다 다르다')
    t = pd.DataFrame(rows, columns=['capture', 'start', 'minutes', 'flows', 'train', 'test'])
    log('[EDA4] captures\n' + t.to_string(index=False))
    save(fig, 'eda4_timeline', t)


def fig_columns(D):
    steps = [('MedSec-25 CSV 컬럼', 84), ('키 7개 제외 (flow ID·IP·포트·시각·라벨)', 77),
             ('값이 하나뿐인 컬럼 10개 제외', 67), ('기기를 드러내는 식별 컬럼 2개 제외', 65),
             ('출발지 시간창 4개 추가', 69), ('공유기에서 가볍게 계산할 후보', 32),
             ('최종 (중요도 순위·개수 비교)', 12)]
    assert len(D.FULL) == 65 and len(D.LIGHT) + len(D.WIN) == 32
    t = pd.DataFrame(steps, columns=['step', 'n'])
    fig, ax = plt.subplots(figsize=(8, 3.9))
    fig.subplots_adjust(left=0.42, right=0.93, top=0.80, bottom=0.06)
    y = np.arange(len(t))[::-1]
    ax.barh(y, t.n, height=0.46, color=[ACCENT if i == len(t) - 1 else GRAY for i in t.index])
    for yi, v in zip(y, t.n):
        ax.text(v + 1.2, yi, str(v), va='center', fontsize=10.5, color=INK2)
    ax.set_yticks(y, t.step)
    ax.set_xlim(0, 92)
    ax.set_xticks([])
    ax.tick_params(length=0)
    for s in ('left', 'bottom'):
        ax.spines[s].set_visible(False)
    title(fig, 'CSV 컬럼 84개가 피처 12개가 되기까지',
          '최종 12개 = CICFlowMeter 정의 10개 + 직접 만든 시간창 2개 (w60_dports, w10_flows)')
    save(fig, 'eda5_columns', t)


if __name__ == '__main__':
    D = load(sys.argv[1] if len(sys.argv) > 1 else 'data/MedSec-25.csv', verbose=False)
    fig_relabel(D)
    fig_classes(D)
    fig_windows(D)
    fig_timeline(D)
    fig_columns(D)
