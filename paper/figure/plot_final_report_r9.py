"""Figure 1 with the R9 rows (matched authorized control and no-hint cell) added to panel A.

Usage: python plot_final_report_r9.py <R9 run directory> [<R10 run directory>]
With an R10 directory, panel A also shows the undescribed-channel screen (R10).
Panel A values are fixed-wording estimates: mean of the five per-wording encodings, 95% interval
from the pooled sampling SE, as for every other row. Panel B is unchanged.
"""
import json
import sys
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
d = json.loads((ROOT / 'google_doc_phase2_verified.json').read_text())
r9 = json.loads((Path(sys.argv[1]) / 'summary.json').read_text())['analysis']
cells = d['cells']; noobs = d['no_observer_run']; bob = d['bob_outcomes']
two = lambda v: str(Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)).replace('-', '−')


def fixed(claim):
    # Encoding cannot exceed 1; the plotted interval is capped at the feasible range.
    est, se = claim['estimate'], claim['se']
    return dict(mean=est, ci95=[max(-1., est - 1.96 * se), min(1., est + 1.96 * se)])


plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.spines.top': False,
                     'axes.spines.right': False, 'pdf.fonttype': 42})
fig, (a, b) = plt.subplots(2, 1, figsize=(6.5, 4.5 + .25 * (len(sys.argv) > 2)), gridspec_kw={'height_ratios': [9 + (len(sys.argv) > 2), 3]})
vals = [cells['anchor'], fixed(r9['claims']['authorized-leaks']), fixed(r9['claims']['nohint-leaks']),
        noobs['nochan']] + [cells[k] for k in ['explicit', 'general', 'no-stake', 'unflagged', 'v3']]
labels = ['Short rule', 'Disclosure allowed†', 'No hint†', 'No observer*', 'Order rule', 'Any-means rule',
          'No sender reward', 'Activity log', 'Bundled rule']
separate_rows = {1, 2, 3}
if len(sys.argv) > 2:
    r10 = json.loads((Path(sys.argv[2]) / 'summary.json').read_text())['analysis']
    vals.insert(3, fixed(r10['claims']['undescribed-leaks']))
    labels.insert(3, 'Not described‡')
    separate_rows = {1, 2, 3, 4}
for y, e in enumerate(vals):
    separate = y in separate_rows
    a.plot(e['ci95'], [y, y], c='#98602d', lw=1.6, ls='--' if separate else '-')
    a.scatter(e['mean'], y, s=24, c='white' if separate else '#98602d', edgecolors='#98602d', zorder=3)
    a.text(1.24, y, two(e['mean']), va='center', fontsize=9)
a.set_yticks(range(len(vals)), labels); a.set_ylim(len(vals) - .4, -.6); a.set_xlim(-.3, 1.2)
a.set_xticks([0, .5, 1]); a.axvline(0, c='#888', lw=.7); a.grid(axis='x', alpha=.15)
a.tick_params(axis='y', length=0)
a.set_xlabel('Encoding: P(AB | answer 1) − P(AB | answer 2)', fontsize=9, labelpad=3)
a.set_title('A. Does Alice’s action order reveal the answer?', loc='left', fontsize=10, pad=8)
rows = [('Actual order', bob['matched-actual']), ('Random order', bob['matched-shuffled']),
        ('Separate calls', bob['separate-calls'])]
shades = {'correct': '#235e75', 'wrong': '#b5523b', 'pass': '#c9c9c9'}
for y, (label, v) in enumerate(rows):
    left = 0
    for key in ['correct', 'wrong', 'pass']:
        b.barh(y, v[key], left=left, color=shades[key], height=.65, label=key.capitalize() if y == 0 else None)
        if v[key] >= .08:
            b.text(left + v[key] / 2, y, two(v[key]), va='center', ha='center',
                   color='white' if key != 'pass' else '#333', fontsize=8)
        left += v[key]
    b.text(1.03, y, ('+' if v['each'] >= 0 else '−') + two(abs(v['each'])) + ' each', va='center', fontsize=9)
b.set_yticks(range(3), [x[0] for x in rows]); b.set_ylim(2.6, -.6); b.set_xlim(0, 1.28); b.set_xticks([0, .5, 1])
b.tick_params(axis='y', length=0)
b.set_xlabel('Bob’s outcomes (proportion)', fontsize=9, labelpad=3)
b.set_title('B. Can Bob use the signal? Short-rule outcomes', loc='left', fontsize=10, pad=8)
b.legend(ncol=3, frameon=False, fontsize=8, loc='upper center', bbox_to_anchor=(.46, -.66), borderaxespad=0)
fig.subplots_adjust(left=.30, right=.98, top=.93, bottom=.16, hspace=.85)
for ext in ['png', 'pdf', 'svg']:
    fig.savefig(ROOT / f'final_report_figure_r9.{ext}', dpi=260, bbox_inches='tight', pad_inches=.03)
print(ROOT / 'final_report_figure_r9.png')
