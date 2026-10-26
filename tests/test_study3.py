import copy
import json
import tempfile
import unittest

from order_signal import phase2, restraint as rs, study3
from order_signal.run import PROJECT


def scripted_config():
    cfg = json.loads((PROJECT / 'configs/study3.json').read_text())
    cfg.update(mode='scripted', phase='verification')
    for job in cfg['jobs']:
        job['repeats_per_secret_per_wording'] = 2
    return cfg


class PromptTests(unittest.TestCase):
    def test_anchor_is_phase2_anchor(self):
        for k in range(study3.WORDINGS):
            for s in (1, 2):
                for p in rs.PRESENTATIONS:
                    self.assertEqual(study3.sender_messages('anchor', k, s, p), phase2.sender_messages('anchor', k, s, p))

    def test_wording_zero_reproduces_low_reasoning_nochan(self):
        for s in (1, 2):
            for p in rs.PRESENTATIONS:
                self.assertEqual(study3.sender_messages('nochan', 0, s, p),
                                 rs.sender_messages('aw1-matched-plain-nochan', s, p))

    def test_nochan_changes_only_the_observation_sentences(self):
        self.assertEqual(len(set(study3.AWARENESS_NO_CHANNEL)), study3.WORDINGS)
        for k in range(study3.WORDINGS):
            anchor = study3.sender_messages('anchor', k, 1)
            m = study3.sender_messages('nochan', k, 1)
            self.assertEqual(m[1], anchor[1])
            restored = m[0]['content'].replace(study3.AWARENESS_NO_CHANNEL[k], phase2.AWARENESS[k].format(
                record='ordered record')).replace(rs.NO_CHANNEL_SENTENCE, rs.CHANNEL_SENTENCE)
            self.assertEqual(restored, anchor[0]['content'])
            self.assertNotIn('ordered record', m[0]['content'])
            self.assertIn(phase2.DISCLOSURE[k], m[0]['content'])

    def test_all_wordings_flip_under_reversed_presentation(self):
        for cell in study3.CELLS:
            for k in range(study3.WORDINGS):
                rev = study3.sender_messages(cell, k, 1, 'reversed-first')[0]['content']
                self.assertIn('Alice submits BA or AB', rev)
                self.assertIn('chooses 2, 1, or pass', rev)

    def test_tasks_are_balanced(self):
        jobs = study3.prepare(copy.deepcopy(json.loads((PROJECT / 'configs/study3.json').read_text())))
        sizes = {j['cell']: len(j['tasks']) for j in jobs}
        self.assertEqual(sizes, dict(anchor=80, nochan=240))
        for j in jobs:
            for k in range(study3.WORDINGS):
                for s in (1, 2):
                    for p in rs.PRESENTATIONS:
                        n = sum(t['wording'] == k and t['current'] == s and t['presentation'] == p for t in j['tasks'])
                        self.assertEqual(n, j['repeats_per_secret_per_wording'] // 2)


class Study3RunTests(unittest.TestCase):
    def test_scripted_run_audits_and_summarizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = study3.execute(copy.deepcopy(scripted_config()), output_dir=tmp)
            report = json.loads((root / 'summary.json').read_text())
            self.assertTrue(report['complete'])
            self.assertTrue(all(j['audit'] for j in report['jobs']))
            claims = report['analysis']['claims']
            self.assertEqual(set(claims), {'anchor-leaks', 'nochan-null', 'channel-effect'})
            # The scripted client always encodes naturally, observed or not: no channel effect.
            self.assertTrue(claims['anchor-leaks']['confirmed'])
            self.assertFalse(claims['nochan-null']['confirmed'])
            self.assertFalse(claims['channel-effect']['confirmed'])
            again = study3.resume(root)
            self.assertTrue(again['complete'])
            self.assertEqual(again['requests'], report['requests'])


if __name__ == '__main__':
    unittest.main()
