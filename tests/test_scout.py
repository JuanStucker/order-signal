import copy
import json
import tempfile
import unittest

from order_signal.learning import schedule
from order_signal.run import PROJECT
from order_signal.scout import action_audit, execute, jobs


class ScoutTests(unittest.TestCase):
    def config(self):
        config = json.loads((PROJECT / 'configs/learning-pilot.json').read_text())
        config['base'] = json.loads((PROJECT / 'configs/default.json').read_text())
        config.update(pairs=2, training_rounds=2, evaluation_rounds=2, arm_ids=['A1', 'A2', 'L3'])
        return config

    def test_caps_and_matched_independent_jobs(self):
        config = self.config()
        tasks = jobs(config)
        self.assertEqual(len(tasks), 6)
        self.assertAlmostEqual(sum(t['config']['base']['budget']['ceiling_usd'] for t in tasks), 1)
        self.assertEqual(sum(t['config']['base']['budget']['max_requests'] for t in tasks), 48)
        for rep in (1, 2):
            draws = [[r['secret'] for r in schedule(t['config'])] for t in tasks if t['replication'] == rep]
            self.assertTrue(all(d == draws[0] for d in draws))
        seeds = {t['config']['base']['seeds']['secrets'] for t in tasks}
        self.assertEqual(len(seeds), 2)
        config['base']['budget']['max_requests'] = 47
        with self.assertRaises(ValueError):
            jobs(config)

    def test_audit_detects_changed_action_and_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = execute(self.config(), tmp, workers=3)
            report = json.loads((root / 'summary.json').read_text())
            self.assertTrue(report['complete'])
            self.assertEqual(report['completed_trials'], 24)
            self.assertEqual(report['committed_cost_usd'], 0)
            self.assertEqual(report['contrasts']['authorization_bundle']['means']['accuracy'], 0)
            path = root / report['pairs'][0]['path']
            cfg = json.loads((path / 'config.json').read_text())
            records = [json.loads(s) for s in (path / 'trials.jsonl').read_text().splitlines()]
            calls = [json.loads(s) for s in (path / 'calls.jsonl').read_text().splitlines()]
            changed = copy.deepcopy(records)
            changed[0]['metrics']['pair_gain'] += 1
            self.assertFalse(action_audit(cfg, changed, calls))
            changed = copy.deepcopy(records)
            changed[0]['actual_order'] = 'BA' if changed[0]['actual_order'] == 'AB' else 'AB'
            self.assertFalse(action_audit(cfg, changed, calls))
