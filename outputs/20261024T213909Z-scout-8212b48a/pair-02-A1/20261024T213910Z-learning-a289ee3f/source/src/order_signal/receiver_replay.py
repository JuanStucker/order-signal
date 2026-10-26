"""Exploratory receiver-only channel forks from frozen completed learning pairs."""

import argparse
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .budget import DollarRequestBudget
from .clients import AuditedClient, DeepSeekClient
from .game import metrics, score
from .learning import ARMS, audit, build, feedback
from .protocol import Agent, ReceiverObservation
from .records import append, provenance, write
from .run import PROJECT


def prepare(source, seed):
    cfg = json.loads((source / 'config.json').read_text())
    rows = [json.loads(s) for s in (source / 'trials.jsonl').read_text().splitlines()]
    calls = [json.loads(s) for s in (source / 'calls.jsonl').read_text().splitlines()]
    if cfg['arm_ids'] != ['A1'] or not audit(cfg, rows, calls):
        raise ValueError('requires_complete_audited_A1_pair')
    history = [feedback(r) for r in rows if r['phase'] == 'training']
    arm = next(a for a in ARMS if a['id'] == 'A1')
    channel = random.Random(seed)
    tasks = []
    for row in rows:
        if row['phase'] != 'evaluation':
            continue
        for delivery, order in [('actual', row['actual_order']), ('random', channel.choice(('AB', 'BA')))]:
            tasks.append(dict(trial_id=row['trial_id'] + '-' + delivery, source_trial_id=row['trial_id'],
                              secret=row['secret'], actual_order=row['actual_order'], delivery=delivery,
                              order=order, input=build(ReceiverObservation(order, 'individual'), arm, history, 'evaluation')))
    random.Random(seed + 100003).shuffle(tasks)
    return cfg, tasks


def execute(sources, destination):
    # Freeze every replay task and source reference before any model calls.
    prepared = [prepare(source, 784103 + 1009*i) for i, source in enumerate(sources)]
    destination.mkdir(parents=True, mode=0o700, exist_ok=False)
    provenance(destination, PROJECT)
    write(destination / 'plan.json', dict(
        ceiling_usd=.4, sources=[str(s.resolve()) for s in sources],
        jobs=[dict(replication=i+1, seed=784103+1009*i, tasks=t) for i, (_, t) in enumerate(prepared)],
        interpretation='Adaptive exploratory decoder forks conditional on two selected histories; pair-level descriptive results only.'))

    def one(index):
        cfg, tasks = prepared[index]
        root = destination / f'pair-{index+1:02d}'
        root.mkdir(mode=0o700)
        prices = cfg['base']['budget']['prices_usd_per_million']
        budget = DollarRequestBudget(len(tasks), ceiling_usd=.4/len(sources), prices=prices, path=root/'budget.json')
        inner = DeepSeekClient(model=cfg['base']['agents'][1]['model'], timeout=180)
        client = AuditedClient(inner, budget=budget, path=root/'calls.jsonl')
        agent = Agent(**{k: v for k, v in [('identifier', cfg['base']['agents'][1]['id']), ('role', 'receiver'), ('display_name', 'Bob')]})
        from .prompts import tool
        params = dict(**cfg['base']['generation'], tools=[tool('receiver')], stream=True)
        results, error = [], None
        try:
            for task in tasks:
                choice = client.decide(agent, task['input'], params, trial_id=task['trial_id'], condition_id=task['delivery'])
                rewards = score(task['secret'], choice)
                result = dict(**{k: v for k, v in task.items() if k != 'input'}, choice=choice, rewards=rewards,
                              metrics=metrics(rewards), outcome='pass' if choice=='pass' else ('correct' if choice==str(task['secret']) else 'wrong'))
                results.append(result)
                append(root/'trials.jsonl', result)
        except Exception as exc:
            error = type(exc).__name__
        finally:
            inner.close()
        calls = [json.loads(s) for s in (root/'calls.jsonl').read_text().splitlines()] if (root/'calls.jsonl').exists() else []
        requests = [c for c in calls if c['event']=='request']
        boundary = len(results)==len(tasks) and len(requests)==len(tasks) and all(
            c['input']==t['input'] and c['params']==params and c['trial_id']==t['trial_id']
            for c,t in zip(requests,tasks))
        summary = dict(replication=index+1, complete=len(results)==len(tasks) and boundary,
                       input_audit=boundary, error_type=error, completed=len(results), planned=len(tasks), arms={})
        for delivery in ('actual','random'):
            rs = [r for r in results if r['delivery']==delivery]
            counts = {k:sum(r['outcome']==k for r in rs) for k in ('correct','wrong','pass')}
            summary['arms'][delivery] = dict(n=len(rs), **counts,
                matching_actual_order=sum(r['order']==r['actual_order'] for r in rs),
                accuracy=counts['correct']/len(rs) if rs else None,
                pair_gain=sum(r['metrics']['pair_gain'] for r in rs)/len(rs) if rs else None)
        write(root/'summary.json',summary)
        return summary

    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        summaries = list(pool.map(one, range(len(sources))))
    budgets = [json.loads(p.read_text()) for p in destination.glob('pair-*/budget.json')]
    report = dict(pairs=summaries, complete=all(s['complete'] for s in summaries),
                  **{k:sum(b[k] for b in budgets) for k in ('requests','accounted_cost_usd','committed_cost_usd')},
                  model_identities=sorted({m for b in budgets for m in b['response_models']}))
    report['complete'] &= len(report['model_identities']) == 1
    write(destination/'summary.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sources', nargs='+', type=Path, required=True)
    p.add_argument('--destination',type=Path,required=True)
    args=p.parse_args()
    if len(args.sources)!=2:
        raise ValueError('this_diagnostic_requires_two_histories')
    print(json.dumps(execute(args.sources,args.destination),indent=2))


if __name__=='__main__':
    main()
