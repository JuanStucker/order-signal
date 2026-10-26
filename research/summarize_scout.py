"""Rebuild portable selection tables, spend record and pair-level figures."""

import argparse
import csv
import json
from pathlib import Path
from statistics import fmean


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    destination = Path(__file__).resolve().parent
    reports, pairs, aggregates = [], [], []
    offsets = {}
    budget = dict(ceiling_usd=4., requests=0, accounted_cost_usd=0., committed_cost_usd=0.,
                  completed_trials=0, failed_trials=0, unattempted_trials=0, runs=[])
    for root in args.roots:
        report = json.loads((root / "summary.json").read_text())
        cfg = json.loads((root / "config.json").read_text())
        regimen = cfg["base"]["generation"]["reasoning_effort"]
        offset = offsets.get(regimen, 0)
        offsets[regimen] = offset + cfg['pairs']
        reports.append((regimen, cfg, report, offset))
        budget["runs"].append(str(root.resolve()))
        for k in ("requests", "accounted_cost_usd", "committed_cost_usd", "completed_trials", "failed_trials", "unattempted_trials"):
            budget[k] += report[k]
        for row in report["pairs"]:
            pairs.append(dict(regimen=regimen, **{k: v for k, v in row.items() if k not in ("diagnostics", "replication", "path")},
                              replication=row['replication'] + offset, path=str(root / row['path']),
                              **{k: row['diagnostics'][k] for k in ('sender_mi_bits', 'encoding_difference', 'conditional_accuracy')}))
    for regimen in offsets:
        for arm in sorted({r['arm'] for r in pairs if r['regimen'] == regimen}):
            selected = [r for r in pairs if r["arm"] == arm and r['regimen'] == regimen]
            counts = {k: sum(r[k] for r in selected) for k in ("correct", "wrong", "pass", "eval_n")}
            n = counts["eval_n"]
            aggregates.append(dict(
                regimen=regimen, arm=arm,
                complete_pairs=sum(r["status"] == "completed" and r["input_audit"] and r["action_audit"] for r in selected),
                planned_pairs=len(selected), **counts,
                accuracy=counts['correct'] / n if n else None,
                pass_rate=counts['pass'] / n if n else None,
                pair_gain=(2 * counts['correct'] - 4 * counts['wrong']) / n if n else None,
                pair_accuracies=[r['accuracy'] for r in selected],
                pair_gains=[r['pair_gain'] for r in selected],
                encoding_differences=[r['encoding_difference'] for r in selected],
                committed_cost_usd=sum(r['committed_cost_usd'] for r in selected),
            ))
    if args.replay:
        replay = json.loads((args.replay / 'summary.json').read_text())
        budget['runs'].append(str(args.replay.resolve()))
        for k in ('requests', 'accounted_cost_usd', 'committed_cost_usd'):
            budget[k] += replay[k]
        budget['completed_receiver_replays'] = sum(p['completed'] for p in replay['pairs'])
        budget['planned_receiver_replays'] = sum(p['planned'] for p in replay['pairs'])
    budget["remaining_usd"] = budget["ceiling_usd"] - budget["committed_cost_usd"]
    budget["basis"] = "Peak-rate ledger estimates; unknown charges remain reserved. Includes only the listed newly authorized scouting runs, not earlier historical experiments."
    if budget['remaining_usd'] < -1e-8:
        raise RuntimeError('campaign_budget_exceeded')
    (destination / "scout-budget.json").write_text(json.dumps(budget, indent=2) + '\n')
    contrasts = {}
    for regimen, cfg, report, offset in reports:
        for name, contrast in report['contrasts'].items():
            target = contrasts.setdefault(regimen, {}).setdefault(name, dict(planned_pairs=0, complete_pairs=0, pair_differences=[]))
            target['planned_pairs'] += cfg['pairs']
            target['complete_pairs'] += contrast['complete_pairs']
            target['pair_differences'] += [dict(d, replication=d['replication']+offset) for d in contrast['pair_differences']]
    for group in contrasts.values():
        for contrast in group.values():
            contrast['means'] = {k: fmean(d[k] for d in contrast['pair_differences'])
                                 if contrast['complete_pairs'] == contrast['planned_pairs'] else None
                                 for k in ('accuracy', 'pass_rate', 'pair_gain')}
            values = contrast['pair_differences']
            contrast['leave_one_pair_out_means'] = {
                k: [fmean(d[k] for j, d in enumerate(values) if j != i) for i in range(len(values))]
                if len(values) > 1 and contrast['complete_pairs'] == contrast['planned_pairs'] else None
                for k in ('accuracy', 'pass_rate', 'pair_gain')
            }
    (destination / "scout-results.json").write_text(json.dumps(dict(aggregates=aggregates, pairs=pairs, contrasts=contrasts), indent=2) + '\n')
    for name, values in [('scout-pairs.csv', pairs), ('scout-arms.csv', aggregates)]:
        with (destination / name).open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    regimens = list(offsets)
    arms = ['L1', 'L2', 'L3', 'L4', 'A1', 'A2', 'M1', 'M2']
    colors = {'none': '#2563a6', 'low': '#b64b32'}
    fig, axes = plt.subplots(3, len(regimens), figsize=(12, 9), squeeze=False, sharex=True)
    for col, regimen in enumerate(regimens):
        for row_index, (metric, label, limits) in enumerate([
                ('accuracy', 'Correct / completed evaluation', (-.05, 1.05)),
                ('pass_rate', 'Pass / completed evaluation', (-.05, 1.05)),
                ('pair_gain', 'Mean combined Alice and Bob score', (-4.2, 2.2))]):
            ax = axes[row_index, col]
            for x, arm in enumerate(arms):
                rows = [r for r in pairs if r['regimen'] == regimen and r['arm'] == arm]
                for i, r in enumerate(rows):
                    if r[metric] is not None:
                        complete = r['status'] == 'completed' and r['input_audit'] and r['action_audit']
                        ax.scatter(x + (i - (len(rows) - 1) / 2) * .09, r[metric],
                                   marker='o' if complete else 'x', s=42,
                                   color=colors.get(regimen, 'black'), alpha=.85, zorder=3)
                if rows and all(r['status'] == 'completed' and r['input_audit'] and r['action_audit'] for r in rows):
                    mean = fmean(r[metric] for r in rows)
                    ax.plot([x-.25, x+.25], [mean, mean], color='black', lw=2)
            ax.set(ylim=limits, xticks=range(len(arms)), xticklabels=arms)
            ax.grid(axis='y', alpha=.2)
            ax.spines[['top', 'right']].set_visible(False)
            if col == 0:
                ax.set_ylabel(label)
            if row_index == 0:
                ax.set_title('No thinking — 4 pairs per arm' if regimen == 'none' else 'Low reasoning — 4 A1/M2 pairs; 2 A2/L3 pairs')
            if metric == 'pair_gain':
                ax.axhline(0, color='gray', linestyle='--', lw=1)
    fig.suptitle('Exploratory order signal screen', fontsize=17, y=.98)
    fig.text(.5, .015, 'Eight planned evaluation rounds per pair. Dots: complete pairs; crosses: incomplete subsets. Bars: means only when all pairs complete.\nL1/L2: group actual/random; L3/L4: individual actual/random; A1/A2: authorized actual/random; M1/M2: memoryless restricted/authorized.', ha='center', fontsize=9)
    fig.tight_layout(rect=[0, .065, 1, .95])
    for suffix in ('png', 'pdf'):
        fig.savefig(destination / f'scout-results.{suffix}', dpi=180)
    print(json.dumps(budget, indent=2))
    print(json.dumps(aggregates, indent=2))


if __name__ == '__main__':
    main()
