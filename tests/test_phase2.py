import copy
import json
import tempfile
import unittest

from order_signal import learning, phase2, prompts, restraint as rs, screen
from order_signal.protocol import SenderObservation
from order_signal.run import PROJECT


def scripted_config():
    cfg = json.loads((PROJECT / 'configs/phase2.json').read_text())
    cfg.update(mode='scripted', phase='verification')
    for job in cfg['jobs']:
        if 'repeats_per_secret_per_wording' in job:
            job['repeats_per_secret_per_wording'] = 2
        if 'templates' in job:
            job['templates'] = 2
    return cfg


class WordingTests(unittest.TestCase):
    def test_wording_zero_reproduces_phase1_prompts(self):
        same = {'anchor': 'anchor', 'explicit': 'explicit-rule', 'no-stake': 'no-stake'}
        for s in (1, 2):
            for p in rs.PRESENTATIONS:
                for cell, old in same.items():
                    self.assertEqual(phase2.sender_messages(cell, 0, s, p), screen.sender_messages(old, s, p))
                self.assertEqual(phase2.sender_messages('v3', 0, s, p)[0]['content'],
                                 rs.present(prompts.build(SenderObservation(s, 'individual'))[0]['content'], p))
                self.assertEqual(phase2.sender_messages('v3', 0, s)[1],
                                 prompts.build(SenderObservation(s, 'individual'))[1])

    def test_every_wording_is_distinct_and_variants_change_only_their_sentence(self):
        for table in (phase2.AWARENESS, phase2.DISCLOSURE, phase2.OBJECTIVE, phase2.EXPLICIT, phase2.GENERAL,
                      phase2.NO_STAKE, phase2.V3_CONFIDENTIALITY, phase2.V3_ROLE, phase2.V3_OBJECTIVE):
            self.assertEqual(len(set(table)), phase2.WORDINGS)
        for k in range(phase2.WORDINGS):
            anchor = phase2.sender_messages('anchor', k, 1)
            for cell, new, old in (('explicit', phase2.DISCLOSURE[k] + ' ' + phase2.EXPLICIT[k], phase2.DISCLOSURE[k]),
                                   ('general', phase2.DISCLOSURE[k] + ' ' + phase2.GENERAL[k], phase2.DISCLOSURE[k]),
                                   ('no-stake', phase2.NO_STAKE[k], screen.PAYOFFS)):
                m = phase2.sender_messages(cell, k, 1)
                self.assertEqual(m[1], anchor[1])
                self.assertEqual(m[0]['content'].replace(new, old), anchor[0]['content'])
            un = phase2.sender_messages('unflagged', k, 1)
            self.assertNotIn('ordered record', un[0]['content'])
            self.assertEqual(un[0]['content'].replace('activity log', 'ordered record').replace(
                'Bob receives the ordered record', 'Bob receives an ordered record'), anchor[0]['content'])

    def test_general_rule_does_not_name_the_channel(self):
        for text in phase2.GENERAL:
            self.assertNotIn('order', text.lower())
            self.assertNotIn('action', text.lower())
        for text in phase2.EXPLICIT:
            self.assertIn('order', text.lower())

    def test_all_wordings_flip_under_reversed_presentation(self):
        for cell in phase2.SPEC_CELLS:
            for k in range(phase2.WORDINGS):
                rev = phase2.sender_messages(cell, k, 1, 'reversed-first')[0]['content']
                self.assertIn('Alice submits BA or AB', rev)
                self.assertIn('chooses 2, 1, or pass', rev)


class FeedbackTests(unittest.TestCase):
    def test_histories_show_successful_decoding(self):
        tpl = dict(answers=[1, 2, 2, 1], reversed_slot={1: 0, 2: 0})
        nat, rev = phase2.success_history('natural', tpl), phase2.success_history('reversed', tpl)
        self.assertEqual([r['observed_order'] for r in nat], ['AB', 'BA', 'BA', 'AB'])
        self.assertEqual([r['observed_order'] for r in rev], ['BA', 'AB', 'AB', 'BA'])
        self.assertTrue(all(r['outcome'] == 'correct' and r['choice'] == str(r['answer']) for r in nat + rev))
        self.assertEqual(phase2.success_history('empty', tpl), [])

    def test_feedback_prompt_is_anchor_with_learning_memory_framing(self):
        m = phase2.feedback_messages('explicit', [], 2)
        self.assertNotIn('single round', m[0]['content'])
        self.assertIn(phase2.EXPLICIT[0], m[0]['content'])
        self.assertTrue(m[0]['content'].endswith(phase2.MEMORY))
        l3 = learning.build(SenderObservation(1, 'individual'), rs.L3, [], 'evaluation')
        self.assertIn(phase2.MEMORY, l3[0]['content'])
        self.assertEqual(m[1]['content'], phase2.OBJECTIVE[0] + '\nPhase: evaluation\nShared training feedback: []\n'
                         'Current hidden answer: 2')

    def test_feedback_tasks_are_balanced(self):
        job = dict(id='f', study='feedback', prompt='anchor', templates=3)
        tasks = phase2.feedback_tasks(job, 5)
        self.assertEqual(len(tasks), 3 * 3 * 2 * 2)
        for p in rs.PRESENTATIONS:
            self.assertEqual(sum(t['presentation'] == p for t in tasks), len(tasks) // 2)


class AnalysisTests(unittest.TestCase):
    def test_holm_is_step_down(self):
        out = phase2.holm(dict(a=0.001, b=0.03, c=0.01))
        self.assertTrue(out['a']['rejected'])  # 0.001 <= 0.05 / 3
        self.assertTrue(out['c']['rejected'])  # 0.01 <= 0.05 / 2
        self.assertTrue(out['b']['rejected'])  # 0.03 <= 0.05 / 1
        out = phase2.holm(dict(a=0.001, b=0.03, c=0.04))
        self.assertFalse(out['b']['rejected'])  # 0.03 > 0.05 / 2
        self.assertFalse(out['c']['rejected'])  # step-down stops at b

    def test_tost(self):
        self.assertLess(phase2.tost(0.0, 0.05), 0.002)
        self.assertGreater(phase2.tost(0.1, 0.1), 0.3)


class Phase2RunTests(unittest.TestCase):
    def test_scripted_run_audits_and_summarizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = phase2.execute(copy.deepcopy(scripted_config()), output_dir=tmp)
            report = json.loads((root / 'summary.json').read_text())
            self.assertTrue(report['complete'])
            self.assertTrue(all(j['audit'] for j in report['jobs']))
            claims = report['specification']['claims']
            self.assertEqual(set(claims), {'anchor-leaks', 'v3-leaks', 'explicit-closes', 'explicit-vs-anchor',
                                           'general-vs-anchor', 'no-stake-vs-anchor', 'unflagged-vs-anchor'})
            # The scripted client always encodes naturally: everything leaks, nothing closes.
            self.assertTrue(claims['anchor-leaks']['confirmed'])
            self.assertFalse(claims['explicit-closes']['confirmed'])
            self.assertEqual(report['arm3_gate']['natural_minus_reversed'], 0)
            again = phase2.resume(root)
            self.assertTrue(again['complete'])
            self.assertEqual(again['requests'], report['requests'])


if __name__ == '__main__':
    unittest.main()
