import copy
import json
import random
import tempfile
import unittest

from order_signal import probes
from order_signal.run import PROJECT


def scripted_config():
    cfg = json.loads((PROJECT / 'configs/probes.json').read_text())
    cfg.update(mode='scripted', phase='verification')
    for job in cfg['jobs']:
        job.update(templates=2) if job['study'] == 'feedback' else job.update(repeats_per_secret=2)
    return cfg


class ProbeTests(unittest.TestCase):
    def test_feedback_cells_change_only_history_mapping(self):
        tpl = probes.template(random.Random(3))
        nat, rev = probes.history('natural', tpl), probes.history('reversed', tpl)
        scr = probes.history('scrambled', tpl)
        self.assertEqual([r['answer'] for r in nat], [r['answer'] for r in rev])
        self.assertTrue(all(probes.natural_order(r['answer']) == r['observed_order'] for r in nat))
        self.assertTrue(all(probes.natural_order(r['answer']) != r['observed_order'] for r in rev))
        for answer in (1, 2):
            orders = [r['observed_order'] for r in scr if r['answer'] == answer]
            self.assertEqual(sorted(orders), ['AB', 'BA'])
        self.assertEqual(probes.history('empty', tpl), [])

    def test_receiver_inputs_hide_answers_and_share_text(self):
        job = dict(id='x', study='feedback', role='receiver', regimen='none', templates=3)
        tasks = probes.feedback_tasks(job, 11)
        self.assertEqual(len(tasks), 3 * 4 * 2)
        for task in tasks:
            self.assertEqual(task['input'][-1]['content'].splitlines()[-1], 'Observed order: ' + task['current'])
            self.assertNotIn('Authorized answer', json.dumps(task['input']))
        systems = {json.dumps(t['input'][0]) for t in tasks}
        self.assertEqual(len(systems), 1)
        empty = [t for t in tasks if t['cell'] == 'empty']
        self.assertTrue(all('Shared training feedback: []' in t['input'][-1]['content'] for t in empty))

    def test_matched_permission_differs_by_one_sentence(self):
        a = probes.permission_messages('matched_authorized', 1)
        r = probes.permission_messages('matched_restricted', 1)
        self.assertEqual(a[1], r[1])
        self.assertEqual(a[0]['content'].replace(probes.PERMISSION['matched_authorized'], ''),
                         r[0]['content'].replace(probes.PERMISSION['matched_restricted'], ''))
        self.assertIn('Bob is told that Alice knows it', r[0]['content'])
        self.assertIn('Restricted private answer', probes.permission_messages('original_restricted', 2)[1]['content'])

    def test_ceiling_and_phase_validation(self):
        cfg = scripted_config()
        cfg['jobs'][0]['ceiling_usd'] = 99
        with self.assertRaises(ValueError):
            probes.prepare(cfg)
        cfg = scripted_config()
        cfg['phase'] = 'final'
        with self.assertRaises(ValueError):
            probes.prepare(cfg)

    def test_scripted_run_audits_and_summarizes(self):
        cfg = scripted_config()
        with tempfile.TemporaryDirectory() as tmp:
            root = probes.execute(copy.deepcopy(cfg), output_dir=tmp)
            report = json.loads((root / 'summary.json').read_text())
            self.assertTrue(report['complete'])
            for job in report['jobs']:
                self.assertTrue(job['audit'])
                if job['study'] == 'feedback':
                    # The scripted client always uses the natural convention.
                    self.assertEqual(job['summary']['cells']['reversed']['mean_direction'], 1)
                else:
                    self.assertEqual(job['summary']['encoding_difference'], 1)
            # Tampering with a saved request input must fail the audit.
            plan = json.loads((root / 'plan.json').read_text())
            calls = root / plan['jobs'][0]['id'] / 'calls.jsonl'
            lines = calls.read_text().splitlines()
            first = json.loads(lines[0])
            first['input'][0]['content'] += ' tampered'
            calls.write_text('\n'.join([json.dumps(first)] + lines[1:]) + '\n')
            self.assertFalse(probes.audit(plan['jobs'][0], root / plan['jobs'][0]['id']))

    def test_sign_flip_p(self):
        self.assertAlmostEqual(probes.sign_flip_p([1, 1, 1, 1, 1]), 2 / 32)
        self.assertEqual(probes.sign_flip_p([0, 0]), 1.0)


if __name__ == '__main__':
    unittest.main()
