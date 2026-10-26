"""Phase 2 Block B: repeated restricted pair play under the matched prompt (exploratory).

Each pair plays consecutive rounds with shared feedback: after every round both agents see the
past answer, Bob's delivered order, his choice and the outcome (learning.feedback, unchanged).
Arms, all with the Phase 2 wording-0 prompts and the learning memory framing:
  matched-actual    anchor prompt; Bob sees Alice's order;
  matched-shuffled  anchor prompt; Bob sees an independent random order (control for his profit);
  explicit-seeded   explicit-rule prompt for both agents; history starts with four seeded rounds of
                    successful natural encoding. Runs only if the Phase 2 feedback gate passes.
Pairs share their answer schedule across arms and alternate symbol listing (odd natural-first).
No retries: a pair stops at its first failure and is reported incomplete.
"""

import argparse
import copy
import json
import random
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean

from . import phase2, prompts
from . import restraint as rs
from .budget import DollarRequestBudget
from .clients import AuditedClient, DeepSeekClient, ScriptedClient
from .learning import feedback
from .probes import MATCHED_SENDER_TEMPLATE, load, sign_flip_p, template
from .protocol import Agent, ReceiverObservation, SenderObservation, play
from .records import append, provenance, write
from .run import PROJECT

VERSION = 'pairplay-v1'
ARMS = {'matched-actual': dict(prompt='anchor', delivery='actual', seeded=False),
        'matched-shuffled': dict(prompt='anchor', delivery='random', seeded=False),
        'explicit-seeded': dict(prompt='explicit', delivery='actual', seeded=True)}
AGENTS = (Agent('alice', 'sender', 'Alice'), Agent('bob', 'receiver', 'Bob'))
RECEIVER_ROLE = prompts.ROLES['receiver']


def presentation(pair):
    return 'natural-first' if pair % 2 else 'reversed-first'


def messages(arm, observation, history, pres):
    """Sender: the Phase 2 prompt for the arm. Receiver: the same rule text with Bob's role."""
    a = ARMS[arm]
    system = phase2.system_prompt(a['prompt'], 0, single_round=False)
    context = 'Phase: training\nShared training feedback: ' + json.dumps(history, sort_keys=True) + '\n'
    if isinstance(observation, SenderObservation):
        current = MATCHED_SENDER_TEMPLATE.format(secret=observation.secret)
    else:
        system = phase2.replace_once(system, rs.MATCHED_SENDER_ROLE, RECEIVER_ROLE)
        current = prompts.RECEIVER_TEMPLATE.format(order=observation.order)
    return [{'role': 'system', 'content': rs.present(system + phase2.MEMORY, pres)},
            {'role': 'user', 'content': phase2.OBJECTIVE[0] + '\n' + context + current}]


def seed_history(pair, seed):
    tpl = template(random.Random(seed + 7919 * pair))
    return phase2.success_history('natural', tpl)


def schedule(config):
    out = []
    for pair in range(1, config['pairs'] + 1):
        rng = random.Random(config['seed'] + pair)
        secrets = [rng.choice((1, 2)) for _ in range(config['rounds'])]
        for arm in config['arms']:
            out.append(dict(id=f'{arm}-p{pair}', arm=arm, pair=pair, presentation=presentation(pair),
                            secrets=secrets, channel_seed=config['seed'] + 104729 * pair,
                            initial_history=seed_history(pair, config['seed']) if ARMS[arm]['seeded'] else []))
    return out


def params(config, role, pres):
    return dict(**config['generation'], tools=[rs.tool(role, pres)], stream=True)


def run_pair(job, config, root, client_factory):
    path = root / job['id']
    path.mkdir(mode=0o700)
    budget = DollarRequestBudget(2 * len(job['secrets']), ceiling_usd=config['ceiling_per_pair_usd'],
                                 prices=config['prices_usd_per_million'], path=path / 'budget.json')
    inner = client_factory()
    client = AuditedClient(inner, budget=budget, path=path / 'calls.jsonl')
    history, rng = list(job['initial_history']), random.Random(job['channel_seed'])
    condition = dict(objective='individual', delivery=ARMS[job['arm']]['delivery'])
    status = dict(status='running', planned=len(job['secrets']), completed=0)
    try:
        for i, secret in enumerate(job['secrets'], 1):
            record = dict(trial_id=f"{job['id']}-r{i}", arm=job['arm'], pair=job['pair'], round=i, secret=secret,
                          presentation=job['presentation'])
            def decide(agent, obs):
                return client.decide(agent, messages(job['arm'], obs, history, job['presentation']),
                                     params(config, agent.role, job['presentation']),
                                     trial_id=record['trial_id'], condition_id=job['arm'])
            play(secret=secret, condition=condition, agents=AGENTS, rng=rng, decide=decide, record=record)
            append(path / 'trials.jsonl', record)
            history.append(feedback(record))
            status['completed'] = i
        status['status'] = 'completed'
    except Exception as exc:
        status.update(status='incomplete', error_type=type(exc).__name__)
    finally:
        inner.close()
        write(path / 'status.json', status)


def audit(job, path, config):
    """Saved requests equal inputs rebuilt from the recorded history; delivery follows the seeded rule."""
    trials = load(path, 'trials.jsonl')
    requests = [c for c in load(path, 'calls.jsonl') if c['event'] == 'request']
    history, rng = list(job['initial_history']), random.Random(job['channel_seed'])
    if len(requests) < 2 * len(trials):
        return False
    for i, t in enumerate(trials):
        if t['secret'] != job['secrets'][i] or t['round'] != i + 1:
            return False
        delivered = t['actual_order'] if ARMS[job['arm']]['delivery'] == 'actual' else rng.choice(('AB', 'BA'))
        if delivered != t['delivered_observation']['order']:
            return False
        obs = (SenderObservation(t['secret'], 'individual'), ReceiverObservation(delivered, 'individual'))
        for call, o, agent in zip(requests[2 * i:2 * i + 2], obs, AGENTS):
            if (call['trial_id'] != t['trial_id'] or call['role'] != agent.role
                    or call['input'] != messages(job['arm'], o, history, job['presentation'])
                    or call['params'] != params(config, agent.role, job['presentation'])):
                return False
        history.append(feedback(t))
    return True


# ---------- analysis (frozen in research/PAIRPLAY_PLAN.md) ----------

def pair_metrics(trials):
    if not trials:
        return None
    rows = [dict(current=t['secret'], value=t['actual_order']) for t in trials]
    late = [r for r, t in zip(rows, trials) if t['round'] > len(trials) // 2]
    enc = lambda rs_: rs.encoding(rs.sender_table(rs_))
    direction = lambda rs_: fmean(1 if r['value'] == ('AB' if r['current'] == 1 else 'BA') else -1 for r in rs_)
    return dict(rounds=len(trials), pair_gain=fmean(t['metrics']['pair_gain'] for t in trials),
                accuracy=fmean(t['outcome'] == 'correct' for t in trials),
                pass_rate=fmean(t['outcome'] == 'pass' for t in trials),
                natural_direction=direction(rows), late_natural_direction=direction(late) if late else None,
                encoding=enc(rows))


def summarize(root):
    plan = json.loads((root / 'plan.json').read_text())
    config = json.loads((root / 'config.json').read_text())
    report = dict(version=VERSION, pairs=[], complete=True, requests=0, accounted_cost_usd=0.,
                  committed_cost_usd=0.)
    models, by = set(), {}
    for job in plan['jobs']:
        path = root / job['id']
        status = json.loads((path / 'status.json').read_text())
        ledger = json.loads((path / 'budget.json').read_text())
        models.update(ledger['response_models'])
        for k in ('requests', 'accounted_cost_usd', 'committed_cost_usd'):
            report[k] += ledger[k]
        ok = audit(job, path, config)
        m = pair_metrics(load(path, 'trials.jsonl'))
        report['pairs'].append(dict(id=job['id'], arm=job['arm'], pair=job['pair'], status=status, audit=ok, metrics=m))
        report['complete'] &= status['status'] == 'completed' and ok
        if status['status'] == 'completed' and ok:
            by[(job['arm'], job['pair'])] = m
    report['model_identities'] = sorted(models)
    report['complete'] &= len(models) <= 1
    arms = {}
    for arm in config['arms']:
        ms = [by[(arm, p)] for p in range(1, config['pairs'] + 1) if (arm, p) in by]
        arms[arm] = dict(complete_pairs=len(ms), **{k: fmean(m[k] for m in ms) if ms else None
                                                    for k in ('pair_gain', 'accuracy', 'pass_rate', 'natural_direction')})
    report['arms'] = arms
    if {'matched-actual', 'matched-shuffled'} <= set(config['arms']):
        out = {}
        for metric in ('pair_gain', 'accuracy', 'natural_direction', 'late_natural_direction'):
            diffs = [by[('matched-actual', p)][metric] - by[('matched-shuffled', p)][metric]
                     for p in range(1, config['pairs'] + 1)
                     if ('matched-actual', p) in by and ('matched-shuffled', p) in by]
            out[metric] = dict(pairs=len(diffs), differences=diffs, mean=fmean(diffs) if diffs else None,
                               sign_flip_p=sign_flip_p(diffs) if len(diffs) == config['pairs'] else None)
        report['actual_minus_shuffled'] = out
    report['interpretation'] = ('Exploratory. Pairs are the unit; rounds within a pair are dependent. Primary: '
                                'pair gain, actual minus shuffled, paired by pair, exact sign-flip p.')
    write(root / 'summary.json', report)
    return report


def client_for(config):
    return (ScriptedClient if config['mode'] == 'scripted'
            else lambda: DeepSeekClient(model=config['model'], timeout=300))


def validate(config):
    if config.get('version') != VERSION:
        raise ValueError('unsupported_version')
    if (config['mode'] == 'scripted') != (config['phase'] == 'verification') or config['phase'] == 'final':
        raise ValueError('pilot_or_verification_only')
    if not config['arms'] or any(a not in ARMS for a in config['arms']) or len(set(config['arms'])) != len(config['arms']):
        raise ValueError('invalid_arms')
    if config['pairs'] % 2:
        raise ValueError('pairs_must_split_across_presentations')
    total = config['ceiling_per_pair_usd'] * config['pairs'] * len(config['arms'])
    if total > config['ceiling_usd'] + 1e-12:
        raise ValueError('pair_ceilings_exceed_total')


def execute(config, output_dir=None, client_factory=None, workers=16):
    validate(config)
    jobs = schedule(config)
    root = Path(output_dir or PROJECT / 'outputs') / (
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-pairplay-' + uuid.uuid4().hex[:8])
    root.mkdir(parents=True, mode=0o700)
    write(root / 'config.json', config)
    write(root / 'plan.json', dict(version=VERSION, jobs=jobs))
    provenance(root, PROJECT)
    print(f'PROBE_ROOT={root}', flush=True)
    factory = client_factory or client_for(config)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lambda j: run_pair(j, config, root, factory), jobs))
    summarize(root)
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--summarize', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.summarize:
        report = summarize(args.summarize)
        print(json.dumps({k: v for k, v in report.items() if k != 'pairs'}, indent=2))
        return
    config = json.loads(args.config.read_text())
    if args.dry_run:
        validate(copy.deepcopy(config))
        jobs = schedule(config)
        print(len(jobs), 'pairs', sum(len(j['secrets']) for j in jobs), 'rounds',
              config['ceiling_per_pair_usd'] * len(jobs), 'ceiling')
        return
    root = execute(config)
    report = json.loads((root / 'summary.json').read_text())
    print(json.dumps({k: v for k, v in report.items() if k != 'pairs'}, indent=2))
    if not report['complete']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
