import copy
import json
import tempfile
import unittest

from order_signal import probes, prompts, restraint as rs, screen
from order_signal.protocol import SenderObservation
from order_signal.run import PROJECT


def scripted_config():
    cfg = json.loads((PROJECT / 'configs/screen-phase1.json').read_text())
    cfg.update(mode='scripted', phase='verification')
    for job in cfg['jobs']:
        for key, value in (('repeats_per_secret', 4), ('repeats_per_order', 4), ('templates', 2)):
            if key in job:
                job[key] = value
    return cfg


class ScreenPromptTests(unittest.TestCase):
    def test_anchor_is_the_24_october_matched_restricted_prompt(self):
        for s in (1, 2):
            self.assertEqual(screen.sender_messages('anchor', s), probes.permission_messages('matched_restricted', s))

    def test_each_variant_changes_only_its_sentence(self):
        anchor = screen.sender_messages('anchor', 2)
        swaps = {'explicit-rule': (probes.PERMISSION['matched_restricted'] + ' ' + screen.EXPLICIT_RULE,
                                   probes.PERMISSION['matched_restricted']),
                 'know-only': (screen.KNOW_ONLY, probes.AWARENESS),
                 'record-only': (screen.RECORD_ONLY, probes.AWARENESS),
                 'no-stake': (screen.NO_STAKE, screen.PAYOFFS),
                 'no-harm': (screen.NO_HARM, screen.PAYOFFS)}
        for cell, (new, old) in swaps.items():
            m = screen.sender_messages(cell, 2)
            self.assertEqual(m[1], anchor[1])
            self.assertIn(new, m[0]['content'])
            self.assertEqual(m[0]['content'].replace(new, old), anchor[0]['content'])

    def test_v3_nochan_removes_only_the_observation(self):
        v3 = prompts.build(SenderObservation(1, 'individual'))
        m = screen.sender_messages('v3-nochan', 1)
        self.assertEqual(m[1], v3[1])
        self.assertNotIn('ordered record', m[0]['content'])
        self.assertEqual(m[0]['content'].replace(rs.NO_CHANNEL_SENTENCE, rs.CHANNEL_SENTENCE), v3[0]['content'])

    def test_uninformed_receiver_changes_only_awareness(self):
        base = rs.receiver_messages('matched-restricted', 'AB')
        m = screen.receiver_messages('uninformed', 'AB')
        self.assertEqual(m[1], base[1])
        self.assertEqual(m[0]['content'].replace(screen.UNINFORMED, probes.AWARENESS), base[0]['content'])

    def test_all_prompts_flip_under_reversed_presentation(self):
        for cell in screen.SENDER_CELLS:
            rev = screen.sender_messages(cell, 1, 'reversed-first')[0]['content']
            self.assertIn('Alice submits BA or AB', rev)
            self.assertIn('drawn fairly from 2 and 1', rev)
        self.assertIn('Choose 2, 1, or pass', screen.receiver_messages('uninformed', 'BA', 'reversed-first')[0]['content'])

    def test_feedback_tasks_pair_every_template_with_both_presentations(self):
        for study, role in (('feedback-restricted', 'sender'), ('feedback-conflict', 'receiver')):
            job = dict(id='f', study=study, role=role, regimen='none', templates=2)
            tasks = screen.feedback_tasks(job, 7)
            for p in rs.PRESENTATIONS:
                self.assertEqual(sum(t['presentation'] == p for t in tasks), len(tasks) // 2)
            rev = [t for t in tasks if t['presentation'] == 'reversed-first']
            self.assertTrue(all('Alice submits BA or AB' in t['input'][0]['content'] for t in rev))
            self.assertTrue(all(t['tool']['parameters']['properties'][
                'order' if role == 'sender' else 'choice']['enum'][0] in ('BA', '2') for t in rev))


class ScreenRunTests(unittest.TestCase):
    def test_scripted_run_audits_and_summarizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = screen.execute(copy.deepcopy(scripted_config()), output_dir=tmp)
            report = json.loads((root / 'summary.json').read_text())
            self.assertTrue(report['complete'])
            self.assertTrue(all(j['audit'] for j in report['jobs']))
            # The scripted client always encodes naturally.
            self.assertEqual(report['contrasts_vs_anchor']['explicit-rule']['estimate'], 0)
            fb = next(j for j in report['jobs'] if j['id'] == 'f-none-restricted-sender')
            self.assertEqual(fb['summary']['primary']['templates'], 2)
            again = screen.resume(root)
            self.assertTrue(again['complete'])
            self.assertEqual(again['requests'], report['requests'])


if __name__ == '__main__':
    unittest.main()
