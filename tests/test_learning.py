import copy
import json
from pathlib import Path
import tempfile
import unittest
from order_signal.learning import run, audit, feedback
from order_signal.run import PROJECT

class LearningTests(unittest.TestCase):
    def test_history_freeze_isolation_and_audit(self):
        cfg=json.loads((PROJECT/'configs/learning-pilot.json').read_text())
        cfg['base']=json.loads((PROJECT/'configs/default.json').read_text())
        cfg['base']['budget']['max_requests']=128
        with tempfile.TemporaryDirectory() as tmp:
            root=run(cfg,output_dir=tmp)
            rows=[json.loads(s) for s in (root/'trials.jsonl').read_text().splitlines()]
            calls=[json.loads(s) for s in (root/'calls.jsonl').read_text().splitlines()]
            self.assertTrue(audit(cfg,rows,calls))
            requests=[c for c in calls if c['event']=='request']
            for arm in ('L1','L2','L3','L4','A1','A2'):
                evaluation=[c for c in requests if c['condition_id']==arm and c['role']=='receiver'][4:]
                histories=[c['input'][1]['content'].split('Shared training feedback: ')[1].split('\n')[0] for c in evaluation]
                self.assertEqual(len(set(histories)),1)
                self.assertEqual(len(json.loads(histories[0])),4)
            for c in requests:
                if c['condition_id'] in ('M1','M2'): self.assertNotIn('Shared training feedback:',str(c['input']))
            tampered=copy.deepcopy(calls)
            next(c for c in tampered if c['event']=='request')['input'][1]['content']+=' secret leak'
            self.assertFalse(audit(cfg,rows,tampered))
            self.assertEqual(set(feedback(rows[0])),{'answer','observed_order','choice','outcome'})
            self.assertEqual(json.loads((root/'status.json').read_text())['completed_trials'],64)

    def test_failure_is_retained(self):
        from order_signal.clients import ScriptedClient
        class Broken(ScriptedClient):
            def generate(self,messages,params): raise RuntimeError('test failure')
        cfg=json.loads((PROJECT/'configs/learning-pilot.json').read_text())
        cfg['base']=json.loads((PROJECT/'configs/default.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root=run(cfg,output_dir=tmp,client=Broken())
            status=json.loads((root/'status.json').read_text())
            self.assertEqual((status['completed_trials'],status['failed_trials'],status['unattempted_trials']),(0,1,63))
            self.assertFalse(json.loads((root/'summary.json').read_text())['input_boundary_verified'])
