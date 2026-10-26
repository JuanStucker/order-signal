"""Post-hoc convention and sender-dependence re-analysis of existing live learning runs.

No API calls. Reads every completed or partial repeated-pair run under outputs/,
derives the order-answer mapping that the delivered training feedback implies,
and compares it with the evaluation-phase conventions of Alice and Bob. Also
reports per-pair sender secret-by-order tables with two-sided Fisher exact
p-values. All results are exploratory and were specified after seeing the data.
"""

import argparse
import json
import re
from math import comb
from pathlib import Path

NATURAL = {(1, 'AB'), (2, 'BA')}
AUTHORIZED = {'A1', 'A2', 'M2'}
MEMORY = {'L1', 'L2', 'L3', 'L4', 'A1', 'A2'}


def natural(secret, order):
    return (int(secret), order) in NATURAL


def fisher(table):
    """Two-sided Fisher exact p for [[a, b], [c, d]] (sum of tables no more likely)."""
    (a, b), (c, d) = table
    r1, c1, n = a + b, a + c, a + b + c + d
    if n == 0 or r1 in (0, n) or c1 in (0, n):
        return None
    prob = lambda x: comb(c1, x) * comb(n - c1, r1 - x) / comb(n, r1)
    observed = prob(a)
    return min(1., sum(prob(x) for x in range(max(0, r1 + c1 - n), min(r1, c1) + 1)
                       if prob(x) <= observed * (1 + 1e-9)))


def mapping(rows, key):
    """Return natural/reversed/tie/none for rows of (secret, order)."""
    nat = sum(natural(r['secret'], key(r)) for r in rows)
    rev = len(rows) - nat
    return dict(natural=nat, reversed=rev,
                label='none' if not rows else 'natural' if nat > rev else 'reversed' if rev > nat else 'tie')


def sender_convention(rows):
    m = mapping(rows, lambda r: r['actual_order'])
    m['majority'] = m['label']
    orders = {r['actual_order'] for r in rows}
    if not rows:
        m['label'] = 'none'
    elif len(orders) == 1:
        # A constant order carries no answer information, whatever the secret counts.
        m['label'] = m['majority'] = 'constant-' + orders.pop()
    elif m['reversed'] == 0:
        m['label'] = 'natural'
    elif m['natural'] == 0:
        m['label'] = 'reversed'
    else:
        m['label'] = 'mixed-' + m['label']
    return m


def receiver_convention(rows):
    attempts = [r for r in rows if r['choice'] in ('1', '2')]
    nat = sum((int(r['choice']), r['delivered_observation']['order']) in NATURAL for r in attempts)
    rev = len(attempts) - nat
    constant = len({r['choice'] for r in attempts}) == 1 and len({r['delivered_observation']['order'] for r in attempts}) > 1
    return dict(attempts=len(attempts), natural=nat, reversed=rev,
                majority='none' if not attempts else 'constant' if constant
                else 'natural' if nat > rev else 'reversed' if rev > nat else 'tie',
                label='none' if not attempts else 'natural' if nat == len(attempts)
                else 'reversed' if nat == 0 else 'mixed')


def table(rows):
    t = [[0, 0], [0, 0]]
    for r in rows:
        t[int(r['secret']) - 1][r['actual_order'] == 'BA'] += 1
    return t


def runs(outputs):
    for path in sorted(outputs.rglob('trials.jsonl')):
        rows = [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
        rows = [r for r in rows if r.get('version') == 'repeated-pair-pilot-v1' and r.get('status') == 'completed']
        cfg_path = path.parent / 'config.json'
        if not rows or not cfg_path.exists():
            continue
        cfg = json.loads(cfg_path.read_text())
        if cfg['base']['mode'] != 'deepseek':
            continue
        yield path.parent, cfg, rows


def analyze(outputs):
    pairs = []
    for root, cfg, rows in runs(outputs):
        regimen = cfg['base']['generation']['reasoning_effort']
        for arm in sorted({r['condition_id'] for r in rows}):
            for pair in sorted({r['pair'] for r in rows if r['condition_id'] == arm}):
                rs = sorted((r for r in rows if r['condition_id'] == arm and r['pair'] == pair), key=lambda r: r['round'])
                train = [r for r in rs if r['phase'] == 'training']
                ev = [r for r in rs if r['phase'] == 'evaluation']
                implied = mapping(train, lambda r: r['delivered_observation']['order']) if arm in MEMORY else None
                sender_ev = sender_convention(ev)
                sender_tr = sender_convention(train)
                receiver_ev = receiver_convention(ev)
                follows = None
                if implied and implied['label'] in ('natural', 'reversed') and sender_ev['majority'] in ('natural', 'reversed'):
                    follows = sender_ev['majority'] == implied['label']
                match = re.search(r'pair-(\d+)-', str(root))
                pair = int(match.group(1)) if match else pair
                pairs.append(dict(
                    run=str(root.relative_to(outputs.parent)), regimen=regimen, arm=arm, pair=pair,
                    authorized=arm in AUTHORIZED, memory=arm in MEMORY, delivery=cfg['base'].get('delivery') or (
                        'random' if arm in ('L2', 'L4', 'A2') else 'actual'),
                    training_rounds=len(train), evaluation_rounds=len(ev),
                    history_implied=implied, sender_training=sender_tr, sender_evaluation=sender_ev,
                    receiver_evaluation=receiver_ev, sender_follows_history=follows,
                    receiver_follows_history=(receiver_ev['majority'] == implied['label']
                                              if implied and implied['label'] in ('natural', 'reversed')
                                              and receiver_ev['majority'] in ('natural', 'reversed') else None),
                    sender_table_all=table(rs), sender_fisher_p_all=fisher(table(rs)),
                    sender_table_eval=table(ev), sender_fisher_p_eval=fisher(table(ev))))
    return pairs


def markdown(pairs):
    lines = ['| Run | Regimen | Arm | Pair | History implies | Alice train | Alice eval | Bob eval | Alice follows | Bob follows | Fisher p (all Alice) |',
             '|---|---|---|---:|---|---|---|---|---|---|---:|']
    for p in pairs:
        h = p['history_implied']
        hl = f"{h['label']} ({h['natural']}/{h['reversed']})" if h else '—'
        st, se, re_ = p['sender_training'], p['sender_evaluation'], p['receiver_evaluation']
        fp = p['sender_fisher_p_all']
        lines.append(f"| {Path(p['run']).parts[1][:24]} | {p['regimen']} | {p['arm']} | {p['pair']} | {hl} | "
                     f"{st['label']} | {se['label']} ({se['natural']}/{se['reversed']}) | "
                     f"{re_['label']} ({re_['natural']}/{re_['reversed']}) | {fmt(p['sender_follows_history'])} | "
                     f"{fmt(p['receiver_follows_history'])} | {'—' if fp is None else f'{fp:.3f}'} |")
    return '\n'.join(lines)


def fmt(v):
    return '—' if v is None else 'yes' if v else 'no'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outputs', type=Path, default=Path(__file__).resolve().parents[1] / 'outputs')
    args = parser.parse_args()
    pairs = analyze(args.outputs.resolve())
    destination = Path(__file__).resolve().parent
    (destination / 'convention-reanalysis.json').write_text(json.dumps(pairs, indent=2) + '\n')
    (destination / 'convention-reanalysis-table.md').write_text(markdown(pairs) + '\n')
    print(markdown(pairs))


if __name__ == '__main__':
    main()
