"""Run independent learning arms concurrently with separate budget ledgers."""
import argparse
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import uuid
from .learning import run, selected_arms
from .records import write
from .run import PROJECT

def batch(config, output_dir=None):
    root=Path(output_dir or PROJECT/'outputs')/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-learning-batch-'+uuid.uuid4().hex[:8])
    root.mkdir(parents=True,mode=0o700)
    write(root/'config.json',config)
    arms=selected_arms(config)
    def one(arm):
        cfg=copy.deepcopy(config)
        cfg['arm_ids']=[arm['id']]
        cfg['base']['budget']['max_requests']=config['base']['budget']['max_requests']//len(arms)
        cfg['base']['budget']['ceiling_usd']=config['base']['budget']['ceiling_usd']/len(arms)
        return run(cfg,output_dir=root)
    with ThreadPoolExecutor(max_workers=len(arms)) as pool:
        paths=list(pool.map(one,arms))
    reports=[json.loads((p/'summary.json').read_text()) for p in paths]
    ledgers=[json.loads((p/'budget.json').read_text()) for p in paths]
    result=dict(status='completed' if all(r['status']['status']=='completed' for r in reports) else 'incomplete',
        runs=[str(p.relative_to(root)) for p in paths],
        completed_trials=sum(r['status']['completed_trials'] for r in reports),
        failed_trials=sum(r['status']['failed_trials'] for r in reports),
        input_boundary_verified=all(r['input_boundary_verified'] for r in reports),
        accounted_cost_usd=sum(b['accounted_cost_usd'] for b in ledgers),
        committed_cost_usd=sum(b['committed_cost_usd'] for b in ledgers),
        requests=sum(b['requests'] for b in ledgers),
        conditions=[row for r in reports for row in r['conditions']],interpretation=reports[0]['interpretation'])
    write(root/'summary.json',result)
    lines=[f"Repeated-pair pilot: {result['status']}",'',result['interpretation'],'',f"Completed trials: {result['completed_trials']}; failures: {result['failed_trials']}; requests: {result['requests']}; input boundary audit: {result['input_boundary_verified']}; accounted cost at configured peak rates: ${result['accounted_cost_usd']:.4f}.",'','| Arm | Phase | n | Correct | Wrong | Pass |','|---|---|---:|---:|---:|---:|']
    for r in result['conditions']: lines.append(f"| {r['id']} | {r['phase']} | {r['n']} | {r['correct']} | {r['wrong']} | {r['pass']} |")
    lines+=['','L1/L2: restricted group actual/random; L3/L4: restricted individual actual/random; A1/A2: authorized learning actual/random; M1/M2: memoryless actual restricted/authorized. All arms retain original payoffs and allow passing.','', 'Each child directory contains its frozen source, configuration, call audit, budget and detailed summary.']
    (root/'summary.md').write_text('\n'.join(lines)+'\n')
    return root

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);args=p.parse_args()
    root=batch(json.loads(args.config.read_text()));print(root);print((root/'summary.md').read_text())
    if json.loads((root/'summary.json').read_text())['status']!='completed':raise SystemExit(1)
if __name__=='__main__':main()
