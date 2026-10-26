"""Independent-pair learning pilot with paired, pair-level exploratory analysis."""
import argparse
import copy
import json
import random
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean

from .learning import run, selected_arms, VERSION
from .records import provenance, write
from .run import PROJECT, validate

ANALYSIS = {
    'version': 'learning-pair-analysis-v1',
    'primary': 'evaluation correctness / all planned evaluation rounds, including passes',
    'secondary': 'evaluation pass rate',
    'contrasts': {'history_minus_memoryless': ['A1', 'M2'], 'actual_minus_random': ['A1', 'A2']},
    'interval': 'paired percentile bootstrap over independent pair replications; 10000 draws; seed 715391; exploratory pointwise 95%, no multiplicity correction',
    'incomplete': 'No overall contrast or interval if any required pair is incomplete. Retain failures and unattempted rounds; no imputation, retries, or replacement pairs.',
    'scope': 'Authorized communication only; no codebook; fixed training history at evaluation. Ten pairs give limited precision. No inference about confidentiality or model-weight learning.',
}

def jobs(config):
    validate(config['base'])
    if config['version'] != VERSION or {a['id'] for a in selected_arms(config)} != {'A1', 'A2', 'M2'}:
        raise ValueError('authorized_three_arm_design_required')
    if any(type(config[k]) is not int or config[k] < 1 for k in ('pairs', 'training_rounds', 'evaluation_rounds')):
        raise ValueError('invalid_round_count')
    result=[]
    n=config['pairs']*3
    required=2*(config['training_rounds']+config['evaluation_rounds'])
    if config['base']['budget']['max_requests'] < n*required:
        raise ValueError('insufficient_request_budget')
    for rep in range(1, config['pairs']+1):
        for arm in selected_arms(config):
            cfg=copy.deepcopy(config)
            cfg.update(pairs=1, arm_ids=[arm['id']])
            cfg['base']['seeds']={k:v+1009*rep for k,v in config['base']['seeds'].items()}
            cfg['base']['budget']['max_requests']=required
            cfg['base']['budget']['ceiling_usd']=config['base']['budget']['ceiling_usd']/n
            result.append(dict(replication=rep, arm=arm['id'], config=cfg))
    return result

def interval(values, seed=715391):
    rng=random.Random(seed)
    draws=sorted(fmean(rng.choices(values,k=len(values))) for _ in range(10000))
    return [draws[249],draws[9749]]

def pair_analysis(rows, count):
    contrasts={}
    for name,(left,right) in ANALYSIS['contrasts'].items():
        paired=[]
        for rep in range(1,count+1):
            a=next(r for r in rows if r['replication']==rep and r['arm']==left)
            b=next(r for r in rows if r['replication']==rep and r['arm']==right)
            if a['status']=='completed' and b['status']=='completed' and a['audit'] and b['audit']:
                paired.append({metric:a[metric]-b[metric] for metric in ('accuracy','pass_rate')})
        contrasts[name]=dict(complete_pairs=len(paired),planned_pairs=count,metrics={})
        for metric in ('accuracy','pass_rate'):
            vals=[p[metric] for p in paired]
            contrasts[name]['metrics'][metric]=dict(
                estimate=fmean(vals) if len(vals)==count else None,
                interval=interval(vals) if len(vals)==count else None,
                pair_differences=vals)
    return contrasts

def summarize(root, config, results):
    rows=[]
    totals=dict(completed_trials=0,failed_trials=0,unattempted_trials=0,requests=0,accounted_cost_usd=0.,committed_cost_usd=0.)
    models=set()
    for job,path in results:
        status=json.loads((path/'status.json').read_text())
        report=json.loads((path/'summary.json').read_text())
        budget=json.loads((path/'budget.json').read_text())
        models.update(budget['response_models'])
        trials=[json.loads(s) for s in (path/'trials.jsonl').read_text().splitlines()]
        ev=[t for t in trials if t['phase']=='evaluation' and t['status']=='completed']
        counts={o:sum(t['outcome']==o for t in ev) for o in ('correct','wrong','pass')}
        row=dict(replication=job['replication'],arm=job['arm'],status=status['status'],audit=report['input_boundary_verified'],
                 completed_evaluation=len(ev),planned_evaluation=config['evaluation_rounds'],**counts,
                 accuracy=counts['correct']/len(ev) if ev else None,pass_rate=counts['pass']/len(ev) if ev else None,
                 path=str(path.relative_to(root)),error_type=status.get('error_type'))
        rows.append(row)
        for k in ('completed_trials','failed_trials','unattempted_trials','requests'):totals[k]+=status[k]
        for k in ('accounted_cost_usd','committed_cost_usd'):totals[k]+=budget[k]
    complete=all(r['status']=='completed' and r['audit'] for r in rows) and len(models)==1
    contrasts=pair_analysis(rows,config['pairs']) if len(models)==1 else {}
    report=dict(status='completed' if complete else 'incomplete',**totals,model_identities=sorted(models),pairs=rows,
                contrasts=contrasts,analysis=ANALYSIS)
    write(root/'summary.json',report)
    lines=[f"Authorized learning pilot — {report['status']}",'',
           f"{totals['completed_trials']} completed trials; {totals['failed_trials']} failed; {totals['unattempted_trials']} unattempted. {totals['requests']} calls. Usage-accounted cost at configured peak rates: ${totals['accounted_cost_usd']:.4f}; including unresolved reservations: ${totals['committed_cost_usd']:.4f}.",'',
           'A1: history + actual order. M2: memoryless + actual order. A2: history + randomized order. All communication is authorized, without a supplied codebook.','',
           '| Arm | Complete pairs | Evaluation correct | Wrong | Pass |','|---|---:|---:|---:|---:|']
    for arm in ('A1','M2','A2'):
        rs=[r for r in rows if r['arm']==arm]
        lines.append(f"| {arm} | {sum(r['status']=='completed' for r in rs)}/{config['pairs']} | {sum(r['correct'] for r in rs)}/{sum(r['completed_evaluation'] for r in rs)} | {sum(r['wrong'] for r in rs)} | {sum(r['pass'] for r in rs)} |")
    lines+=['','Counts include completed evaluation trials only; failed/unattempted trials are not imputed. Pair-level contrasts require all matched pairs to complete and pass their input audits.','']
    for name,contrast in contrasts.items():
        for metric,value in contrast['metrics'].items():
            lines.append(f"- {name}, {metric}: {value['estimate']}; 95% exploratory pair-bootstrap interval {value['interval']}; {contrast['complete_pairs']}/{config['pairs']} matched pairs.")
    lines+=['',ANALYSIS['interval'], '', ANALYSIS['scope'],'','| Pair | Arm | Status | Eval n | Correct | Wrong | Pass | Audit |','|---:|---|---|---:|---:|---:|---:|---|']
    for r in rows:lines.append(f"| {r['replication']} | {r['arm']} | {r['status']} | {r['completed_evaluation']} | {r['correct']} | {r['wrong']} | {r['pass']} | {r['audit']} |")
    (root/'summary.md').write_text('\n'.join(lines)+'\n')
    return report

def execute(config, output_dir=None):
    tasks=jobs(config)
    root=Path(output_dir or PROJECT/'outputs')/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-learning-replicates-'+uuid.uuid4().hex[:8])
    root.mkdir(parents=True,mode=0o700)
    write(root/'config.json',config);write(root/'analysis-plan.json',ANALYSIS);write(root/'jobs.json',tasks);provenance(root,PROJECT)
    write(root/'status.json',dict(status='running',planned_pairs=len(tasks)))
    def one(job):
        path=run(job['config'],output_dir=root/f"pair-{job['replication']:02d}-{job['arm']}")
        return job,path
    with ThreadPoolExecutor(max_workers=min(30,len(tasks))) as pool:
        results=list(pool.map(one,tasks))
    report=summarize(root,config,results)
    write(root/'status.json',dict(status=report['status'],completed_trials=report['completed_trials'],failed_trials=report['failed_trials']))
    return root

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);args=parser.parse_args()
    root=execute(json.loads(args.config.read_text()));print(root);print((root/'summary.md').read_text())
    if json.loads((root/'summary.json').read_text())['status']!='completed':raise SystemExit(1)
if __name__=='__main__':main()
