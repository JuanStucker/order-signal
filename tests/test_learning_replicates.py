import copy
import json
from pathlib import Path
import tempfile
import unittest
from order_signal.learning import schedule
from order_signal.learning_replicates import jobs, pair_analysis, execute
from order_signal.run import PROJECT

class ReplicateTests(unittest.TestCase):
    def config(self):
        c=json.loads((PROJECT/'configs/learning-preflight.json').read_text())
        c['base']=json.loads((PROJECT/'configs/default.json').read_text())
        c.update(pairs=2,training_rounds=2,evaluation_rounds=2)
        return c

    def test_independent_matched_schedules_and_budget(self):
        c=self.config();tasks=jobs(c)
        self.assertEqual(len(tasks),6)
        self.assertLessEqual(sum(j['config']['base']['budget']['ceiling_usd'] for j in tasks),c['base']['budget']['ceiling_usd']+1e-12)
        seeds=[]
        for rep in (1,2):
            selected=[j for j in tasks if j['replication']==rep]
            draws=[[t['secret'] for t in schedule(j['config'])] for j in selected]
            self.assertTrue(all(d==draws[0] for d in draws))
            seeds.append(selected[0]['config']['base']['seeds']['secrets'])
        self.assertNotEqual(*seeds)

    def test_pair_level_contrasts_and_incomplete_gate(self):
        rows=[dict(replication=i,arm=a,status='completed',audit=True,accuracy=v,pass_rate=1-v)
              for i in (1,2) for a,v in [('A1',1.),('A2',0.),('M2',.5)]]
        r=pair_analysis(rows,2)
        self.assertEqual(r['history_minus_memoryless']['metrics']['accuracy']['estimate'],.5)
        self.assertEqual(r['actual_minus_random']['metrics']['accuracy']['interval'],[1.,1.])
        rows[0]['status']='incomplete'
        self.assertIsNone(pair_analysis(rows,2)['history_minus_memoryless']['metrics']['accuracy']['estimate'])

    def test_offline_execution_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=execute(self.config(),tmp)
            r=json.loads((root/'summary.json').read_text())
            self.assertEqual(r['status'],'completed')
            self.assertEqual(r['completed_trials'],24)
            self.assertEqual(r['requests'],48)
            self.assertEqual(len(r['pairs']),6)
            self.assertTrue(all(p['audit'] for p in r['pairs']))
            self.assertEqual(r['contrasts']['history_minus_memoryless']['metrics']['accuracy']['estimate'],0.)
            self.assertTrue((root/'analysis-plan.json').exists())
