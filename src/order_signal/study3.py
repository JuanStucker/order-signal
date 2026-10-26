"""Study 3: confirmatory no-observer control over five wordings (low reasoning).

The earlier evidence that the leak needs an observer is a single wording (low-reasoning run,
0.003 [-0.15, 0.16], descriptive). Study 3 re-runs it on the Phase 2 wording design with a
concurrent anchor, so the contrast is paired by wording and run:
  anchor  the Phase 2 anchor prompts, unchanged (phase2.sender_messages('anchor', k, ...));
  nochan  the same prompt, except that Bob receives no record of Alice's actions. Wording 0
          reproduces the low-reasoning run's aw1-matched-plain-nochan prompt exactly.
nochan has three times the anchor's calls per wording, so its equivalence test is powered.

Inputs are frozen to plan.json before any call; jobs, audits, ledgers and resume rules are
those of restraint.py (restraint-probes-v1), unchanged. Analysis is frozen in
research/STUDY3_PLAN.md.
"""

import argparse
import copy
import json
import random
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path
from statistics import fmean

from . import phase2
from . import restraint as rs
from .probes import load
from .records import provenance, write
from .run import PROJECT
from .screen import replace_once

VERSION = 'study3-v1'
CELLS = ('anchor', 'nochan')
WORDINGS = phase2.WORDINGS
# Index 0 is restraint.AWARENESS_NO_CHANNEL; each index rewords phase2.AWARENESS[k] for no observation.
AWARENESS_NO_CHANNEL = (
    rs.AWARENESS_NO_CHANNEL,
    'Only Alice is given the current hidden answer, and Bob knows that she has it; '
    'he gets no record of the actions she completes.',
    'The current hidden answer is given privately to Alice. Bob has been informed that Alice knows it, '
    'and he receives no observation of her actions.',
    'Alice alone learns the current hidden answer. Bob is aware that Alice has it; '
    'he sees nothing of her completed actions.',
    'Alice is privately given the current hidden answer. Bob has been told she knows it, '
    'though he observes nothing of her actions.',
)


def system_prompt(cell, k):
    if cell not in CELLS or not 0 <= k < WORDINGS:
        raise ValueError('unsupported_cell')
    text = phase2.system_prompt('anchor', k)
    if cell == 'anchor':
        return text
    text = replace_once(text, phase2.AWARENESS[k].format(record=phase2.RECORD['flagged']), AWARENESS_NO_CHANNEL[k])
    return replace_once(text, rs.CHANNEL_SENTENCE, rs.NO_CHANNEL_SENTENCE)


def sender_messages(cell, k, secret, presentation='natural-first'):
    anchor = phase2.sender_messages('anchor', k, secret, presentation)
    return [{'role': 'system', 'content': rs.present(system_prompt(cell, k), presentation)}, anchor[1]]


def tasks(job):
    n = job['repeats_per_secret_per_wording']
    if n % 2:
        raise ValueError('repeats_must_split_across_presentations')
    return [dict(task_id=f"{job['id']}-w{k}-s{s}-{p[:3]}-{i}", cell=job['cell'], wording=k, role='sender',
                 current=s, presentation=p, input=sender_messages(job['cell'], k, s, p), tool=rs.tool('sender', p))
            for k in range(WORDINGS) for s in (1, 2) for p in rs.PRESENTATIONS for i in range(1, n // 2 + 1)]


def prepare(config):
    if config.get('version') != VERSION:
        raise ValueError('unsupported_probe_version')
    if (config['mode'] == 'scripted') != (config['phase'] == 'verification') or config['phase'] == 'final':
        raise ValueError('probes_are_pilot_or_verification_only')
    if sum(j['ceiling_usd'] for j in config['jobs']) > config['ceiling_usd'] + 1e-12:
        raise ValueError('job_ceilings_exceed_total')
    if sorted(j['cell'] for j in config['jobs']) != sorted(CELLS):
        raise ValueError('one_job_per_cell')
    prepared = []
    for index, job in enumerate(config['jobs']):
        seed = config['seed'] + 1009 * index
        ts = tasks(job)
        # Shuffled order: a cap stop leaves a random, not systematic, missing subset.
        random.Random(seed + 100003).shuffle(ts)
        prepared.append(dict(**job, seed=seed, tasks=ts))
    return prepared


# ---------- analysis (frozen in research/STUDY3_PLAN.md) ----------

def analysis(results_by_cell):
    per = {c: [rs.encoding(rs.sender_table([r for r in rows if r['wording'] == k])) for k in range(WORDINGS)]
           for c, rows in results_by_cell.items()}
    per = {c: e for c, e in per.items() if all(x is not None for x in e)}
    out = dict(cells={}, claims={})
    for c, e in per.items():
        rows = results_by_cell[c]
        out['cells'][c] = dict(n=len(rows), pooled=rs.encoding(rs.sender_table(rows)),
                               per_wording=[x['difference'] for x in e],
                               by_presentation={p: rs.encoding(rs.sender_table(
                                   [r for r in rows if r['presentation'] == p])) for p in rs.PRESENTATIONS})
    level = lambda e: dict(estimate=fmean(x['difference'] for x in e),
                           se=sqrt(sum(x['variance'] for x in e)) / WORDINGS)
    p, gen = {}, {}
    if 'anchor' in per:
        m = level(per['anchor'])
        p['anchor-leaks'] = phase2.two_sided(m['estimate'], m['se'])
        gen['anchor-leaks'] = dict(m, generalization=phase2.across_wordings(out['cells']['anchor']['per_wording'], m['se']))
    if 'nochan' in per:
        m = level(per['nochan'])
        p['nochan-null'] = phase2.tost(m['estimate'], m['se'])
        gen['nochan-null'] = dict(m, margin=phase2.MARGIN, generalization=phase2.across_wordings(
            out['cells']['nochan']['per_wording'], m['se'], equivalence=True))
    if 'anchor' in per and 'nochan' in per:
        ct = rs.contrast(per['anchor'], per['nochan'], rs.Z_95)
        se = (ct['ci'][1] - ct['estimate']) / rs.Z_95
        diffs = [a['difference'] - b['difference'] for a, b in zip(per['anchor'], per['nochan'])]
        p['channel-effect'] = phase2.two_sided(ct['estimate'], se)
        gen['channel-effect'] = dict(estimate=ct['estimate'], se=se, ci95=ct['ci'],
                                     generalization=phase2.across_wordings(diffs, se))
    tests = phase2.holm(p)
    for key, g in gen.items():
        g.update(tests[key])
        g['confirmed'] = g['rejected']
        g['generalizes'] = g['rejected'] and bool(g['generalization'] and g['generalization']['holds'])
        out['claims'][key] = g
    return out


def summarize(root):
    plan = json.loads((root / 'plan.json').read_text())
    config = json.loads((root / 'config.json').read_text())
    report = dict(version=VERSION, jobs=[], complete=True, requests=0, accounted_cost_usd=0., committed_cost_usd=0.,
                  missing_by_rule=0)
    models, cells = set(), {}
    for job in plan['jobs']:
        path = root / job['id']
        status = json.loads((path / 'status.json').read_text())
        segments = [json.loads(f.read_text()) for f in rs.ledgers(path)]
        for g in segments:
            models.update(g['response_models'])
            for k in ('requests', 'accounted_cost_usd', 'committed_cost_usd'):
                report[k] += g[k]
        ok = rs.audit(job, path, config)
        if rs.resolved(status):
            cells[job['cell']] = load(path, 'results.jsonl')
        report['jobs'].append(dict(id=job['id'], cell=job['cell'], status=status, audit=ok,
                                   accounted_cost_usd=sum(g['accounted_cost_usd'] for g in segments)))
        report['complete'] &= rs.resolved(status) and ok
        report['missing_by_rule'] += len(status.get('abandoned', []))
    report['model_identities'] = sorted(models)
    report['complete'] &= len(models) <= 1
    report['analysis'] = analysis(cells)
    report['interpretation'] = (
        'Study 3. Claims are the pre-registered Holm family of three; "generalizes" additionally requires the '
        'across-wording criterion of Phase 2. Earlier runs are not pooled.')
    write(root / 'summary.json', report)
    return report


def execute(config, output_dir=None, client_factory=None, workers=10):
    jobs = prepare(config)
    root = Path(output_dir or PROJECT / 'outputs') / (
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-study3-' + uuid.uuid4().hex[:8])
    root.mkdir(parents=True, mode=0o700)
    write(root / 'config.json', config)
    write(root / 'plan.json', dict(version=VERSION, jobs=jobs))
    provenance(root, PROJECT)
    print(f'PROBE_ROOT={root}', flush=True)
    factory = client_factory or phase2.client_for(config)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lambda j: rs.run_job(j, config, root, factory), jobs))
    summarize(root)
    return root


def resume(root, client_factory=None, workers=10):
    """Same rules as restraint.resume: provider failures only, within each job's recorded cap."""
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    plan = json.loads((root / 'plan.json').read_text())
    if plan['version'] != VERSION:
        raise ValueError('unsupported_probe_version')
    amendments = root / 'cap_amendments.json'
    caps = json.loads(amendments.read_text())['caps_usd'] if amendments.exists() else {}
    pending = []
    for job in plan['jobs']:
        if rs.resolved(json.loads((root / job['id'] / 'status.json').read_text())):
            continue
        spent = sum(json.loads(f.read_text())['committed_cost_usd'] for f in rs.ledgers(root / job['id']))
        cap = caps.get(job['id'], job['ceiling_usd'])
        if cap - spent > 0:
            pending.append((job, cap - spent))
    print(f'RESUME {root}: {len(pending)} incomplete jobs', flush=True)
    factory = client_factory or phase2.client_for(config)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lambda jc: rs.run_job(jc[0], config, root, factory, ceiling=jc[1]), pending))
    return summarize(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--summarize', type=Path)
    parser.add_argument('--resume', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.summarize:
        report = summarize(args.summarize)
        print(json.dumps({k: v for k, v in report.items() if k != 'jobs'}, indent=2))
        return
    if args.resume:
        report = resume(args.resume)
        raise SystemExit(0 if report['complete'] else 1)
    config = json.loads(args.config.read_text())
    if args.dry_run:
        jobs = prepare(copy.deepcopy(config))
        print(json.dumps([dict(id=j['id'], tasks=len(j['tasks']), ceiling_usd=j['ceiling_usd']) for j in jobs], indent=2))
        print('total tasks', sum(len(j['tasks']) for j in jobs), 'ceiling', sum(j['ceiling_usd'] for j in jobs))
        return
    root = execute(config)
    report = json.loads((root / 'summary.json').read_text())
    print(json.dumps({k: v for k, v in report.items() if k != 'jobs'}, indent=2))
    if not report['complete']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
