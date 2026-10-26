import copy
import json
import tempfile
import unittest

from order_signal import payoff, phase2, prompts, restraint as rs, screen
from order_signal.run import PROJECT


def scripted_config():
    cfg = json.loads((PROJECT / 'configs/payoff.json').read_text())
    cfg.update(mode='scripted', phase='verification')
    for job in cfg['jobs']:
        job['repeats_per_secret'] = 4
    return cfg


class PayoffPromptTests(unittest.TestCase):
    def test_anchor_is_the_phase2_anchor(self):
        for p in rs.PRESENTATIONS:
            self.assertEqual(payoff.sender_messages('anchor', 1, p), phase2.sender_messages('anchor', 0, 1, p))

    def test_no_harm_is_the_phase1_cell(self):
        self.assertEqual(payoff.sender_messages('no-harm', 2), screen.sender_messages('no-harm', 2))

    def test_each_cell_changes_only_its_payoff_sentence(self):
        anchor = payoff.sender_messages('anchor', 1)
        self.assertIn(payoff.PASS, prompts.RULES)
        for cell, change in payoff.CHANGES.items():
            if change is None:
                continue
            m = payoff.sender_messages(cell, 1)
            self.assertEqual(m[1], anchor[1])
            self.assertEqual(m[0]['content'].replace(change[1], change[0]), anchor[0]['content'])

    def test_legit_cells_keep_reversed_listing_flips(self):
        rev = payoff.sender_messages('legit-equal', 1, 'reversed-first')[0]['content']
        self.assertIn('Alice submits BA or AB', rev)
        self.assertIn(payoff.LEGIT_EQUAL, rev)


class PayoffScreenTests(unittest.TestCase):
    def test_screen_config_fits_remaining_budget(self):
        cfg = json.loads((PROJECT / 'configs/payoff-screen.json').read_text())
        self.assertEqual(cfg['version'], 'payoff-v2')
        self.assertEqual([j['cell'] for j in cfg['jobs']], ['anchor', 'high-harm', 'legit-dominant'])
        self.assertLessEqual(cfg['ceiling_usd'], 1.98)
        self.assertEqual(sum(len(j['tasks']) for j in payoff.prepare(copy.deepcopy(cfg))), 96)

    def test_v1_rejects_legit_dominant(self):
        cfg = scripted_config()
        cfg['jobs'][0]['cell'] = 'legit-dominant'
        with self.assertRaises(ValueError):
            payoff.prepare(cfg)

    def test_scripted_screen_tests_only_planned_contrasts(self):
        cfg = json.loads((PROJECT / 'configs/payoff-screen.json').read_text())
        cfg.update(mode='scripted', phase='verification')
        for job in cfg['jobs']:
            job['repeats_per_secret'] = 4
        with tempfile.TemporaryDirectory() as tmp:
            report = json.loads((payoff.execute(cfg, output_dir=tmp) / 'summary.json').read_text())
            self.assertTrue(report['complete'])
            self.assertEqual(set(report['claims']), {'high-harm-vs-anchor', 'legit-dominant-vs-anchor'})


class PayoffRunTests(unittest.TestCase):
    def test_scripted_run_audits_and_summarizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = payoff.execute(copy.deepcopy(scripted_config()), output_dir=tmp)
            report = json.loads((root / 'summary.json').read_text())
            self.assertTrue(report['complete'])
            self.assertTrue(all(j['audit'] for j in report['jobs']))
            self.assertEqual(set(report['claims']), {f'{c}-vs-anchor' for c in payoff.CONTRASTS if c != 'legit-dominant'})
            self.assertEqual(report['claims']['legit-equal-vs-anchor']['estimate'], 0)
            self.assertTrue(payoff.resume(root)['complete'])


if __name__ == '__main__':
    unittest.main()
