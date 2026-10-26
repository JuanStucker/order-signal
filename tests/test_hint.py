import copy
import json
import tempfile
import unittest

from order_signal import hint, phase2, restraint as rs
from order_signal.run import PROJECT


def scripted_config():
    cfg = json.loads((PROJECT / 'configs/hint.json').read_text())
    cfg.update(mode='scripted', phase='verification')
    for job in cfg['jobs']:
        job['repeats_per_secret_per_wording'] = 2
    return cfg


class PromptTests(unittest.TestCase):
    def test_anchor_is_phase2_anchor(self):
        for k in range(hint.WORDINGS):
            for s in (1, 2):
                for p in rs.PRESENTATIONS:
                    self.assertEqual(hint.sender_messages('anchor', k, s, p), phase2.sender_messages('anchor', k, s, p))

    def test_wording_zero_reproduces_low_reasoning_cells(self):
        for s in (1, 2):
            for p in rs.PRESENTATIONS:
                self.assertEqual(hint.sender_messages('nohint', 0, s, p), rs.sender_messages('aw0-matched-plain', s, p))
                self.assertEqual(hint.sender_messages('authorized', 0, s, p),
                                 rs.sender_messages('aw1-matched-plain-auth', s, p))

    def test_nohint_removes_only_the_hint(self):
        for k in range(hint.WORDINGS):
            anchor = hint.sender_messages('anchor', k, 1)
            m = hint.sender_messages('nohint', k, 1)
            self.assertEqual(m[1], anchor[1])
            awareness = phase2.AWARENESS[k].format(record='ordered record')
            self.assertEqual(awareness + ' ' + m[0]['content'], anchor[0]['content'])
            self.assertNotIn('Bob is', m[0]['content'].split(rs.CHANNEL_SENTENCE)[0])
            self.assertIn(rs.CHANNEL_SENTENCE, m[0]['content'])
            self.assertIn(phase2.DISCLOSURE[k], m[0]['content'])

    def test_authorized_changes_only_the_permission(self):
        self.assertEqual(len(set(hint.PERMISSIONS)), hint.WORDINGS)
        for k in range(hint.WORDINGS):
            anchor = hint.sender_messages('anchor', k, 1)
            m = hint.sender_messages('authorized', k, 1)
            self.assertEqual(m[1], anchor[1])
            self.assertEqual(m[0]['content'].replace(hint.PERMISSIONS[k], phase2.DISCLOSURE[k]), anchor[0]['content'])
            self.assertNotIn(phase2.DISCLOSURE[k], m[0]['content'])

    def test_all_wordings_flip_under_reversed_presentation(self):
        for cell in hint.CELLS:
            for k in range(hint.WORDINGS):
                rev = hint.sender_messages(cell, k, 1, 'reversed-first')[0]['content']
                self.assertIn('Alice submits BA or AB', rev)
                self.assertIn('chooses 2, 1, or pass', rev)

    def test_tasks_are_balanced(self):
        jobs = hint.prepare(copy.deepcopy(json.loads((PROJECT / 'configs/hint.json').read_text())))
        sizes = {j['cell']: len(j['tasks']) for j in jobs}
        self.assertEqual(sizes, dict(anchor=80, nohint=80, authorized=40))
        for j in jobs:
            for k in range(hint.WORDINGS):
                for s in (1, 2):
                    for p in rs.PRESENTATIONS:
                        n = sum(t['wording'] == k and t['current'] == s and t['presentation'] == p for t in j['tasks'])
                        self.assertEqual(n, j['repeats_per_secret_per_wording'] // 2)

    def test_caps_within_authorized_total(self):
        cfg = json.loads((PROJECT / 'configs/hint.json').read_text())
        self.assertLessEqual(sum(j['ceiling_usd'] for j in cfg['jobs']), 2.4 + 1e-12)
        self.assertEqual(cfg['ceiling_usd'], 2.4)


class HintRunTests(unittest.TestCase):
    def test_scripted_run_audits_and_summarizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = hint.execute(copy.deepcopy(scripted_config()), output_dir=tmp)
            report = json.loads((root / 'summary.json').read_text())
            self.assertTrue(report['complete'])
            self.assertTrue(all(j['audit'] for j in report['jobs']))
            claims = report['analysis']['claims']
            self.assertEqual(set(claims), {'nohint-leaks', 'authorized-leaks', 'hint-effect'})
            # The scripted client always encodes naturally, whatever the prompt: no hint effect.
            self.assertTrue(claims['nohint-leaks']['confirmed'])
            self.assertTrue(claims['authorized-leaks']['confirmed'])
            self.assertFalse(claims['hint-effect']['confirmed'])
            again = hint.resume(root)
            self.assertTrue(again['complete'])
            self.assertEqual(again['requests'], report['requests'])


if __name__ == '__main__':
    unittest.main()
