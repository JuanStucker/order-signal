import copy
import json
import tempfile
import unittest

from order_signal import hint, restraint as rs, undescribed
from order_signal.run import PROJECT


def scripted_config():
    cfg = json.loads((PROJECT / 'configs/undescribed.json').read_text())
    cfg.update(mode='scripted', phase='verification')
    for job in cfg['jobs']:
        job['repeats_per_secret_per_wording'] = 2
    return cfg


class PromptTests(unittest.TestCase):
    def test_changes_only_the_channel_sentence_of_nohint(self):
        for k in range(undescribed.WORDINGS):
            for s in (1, 2):
                base = hint.sender_messages('nohint', k, s)
                m = undescribed.sender_messages('undescribed', k, s)
                self.assertEqual(m[1], base[1])
                self.assertEqual(m[0]['content'].replace(undescribed.UNDESCRIBED_SENTENCE, rs.CHANNEL_SENTENCE),
                                 base[0]['content'])

    def test_nothing_describes_what_bob_observes(self):
        for k in range(undescribed.WORDINGS):
            for p in rs.PRESENTATIONS:
                text = undescribed.sender_messages('undescribed', k, 1, p)[0]['content'].lower()
                for word in ('record', 'observ', 'sees', 'receives', 'log', 'knows'):
                    self.assertNotIn(word, text)

    def test_all_wordings_flip_under_reversed_presentation(self):
        for k in range(undescribed.WORDINGS):
            rev = undescribed.sender_messages('undescribed', k, 1, 'reversed-first')[0]['content']
            self.assertIn('Alice submits BA or AB', rev)
            self.assertIn('Bob chooses 2, 1, or pass.', rev)

    def test_tasks_are_balanced(self):
        jobs = undescribed.prepare(copy.deepcopy(json.loads((PROJECT / 'configs/undescribed.json').read_text())))
        self.assertEqual([len(j['tasks']) for j in jobs], [60])
        for k in range(undescribed.WORDINGS):
            for s in (1, 2):
                for p in rs.PRESENTATIONS:
                    n = sum(t['wording'] == k and t['current'] == s and t['presentation'] == p for t in jobs[0]['tasks'])
                    self.assertEqual(n, 3)

    def test_cap_within_remaining_credit(self):
        cfg = json.loads((PROJECT / 'configs/undescribed.json').read_text())
        self.assertLessEqual(sum(j['ceiling_usd'] for j in cfg['jobs']), 0.85 + 1e-12)


class UndescribedRunTests(unittest.TestCase):
    def test_scripted_run_audits_and_summarizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = undescribed.execute(copy.deepcopy(scripted_config()), output_dir=tmp)
            report = json.loads((root / 'summary.json').read_text())
            self.assertTrue(report['complete'])
            self.assertTrue(all(j['audit'] for j in report['jobs']))
            self.assertEqual(set(report['analysis']['claims']), {'undescribed-leaks'})
            # The scripted client always encodes naturally, whatever the prompt.
            self.assertTrue(report['analysis']['claims']['undescribed-leaks']['confirmed'])
            again = undescribed.resume(root)
            self.assertTrue(again['complete'])
            self.assertEqual(again['requests'], report['requests'])


if __name__ == '__main__':
    unittest.main()
