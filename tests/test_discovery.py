import copy
import json
import tempfile
import unittest

from order_signal import discovery, restraint as rs, undescribed
from order_signal.run import PROJECT


def config(mode='deepseek'):
    cfg = json.loads((PROJECT / 'configs/discovery.json').read_text())
    if mode == 'scripted':
        cfg.update(mode='scripted', phase='verification')
    return cfg


class PromptTests(unittest.TestCase):
    def test_system_prompt_is_undescribed_plus_memory(self):
        base = undescribed.system_prompt('undescribed', 0)
        single = 'This is a single round with no shared conversation or previous results. '
        self.assertEqual(discovery.system_prompt(), base.replace(single, '') + discovery.MEMORY)

    def test_nothing_says_bob_observes_the_current_order(self):
        for p in rs.PRESENTATIONS:
            text = discovery.sender_messages('natural', discovery.templates(config())[0], 1, p)[0]['content'].lower()
            for word in ('record', 'observ', 'sees', 'receives', 'log', 'knows'):
                self.assertNotIn(word, text)

    def test_histories_show_opposite_mappings_with_bob_correct(self):
        tpl = discovery.templates(config())[0]
        nat, rev = discovery.success_history('natural', tpl), discovery.success_history('reversed', tpl)
        self.assertEqual([r['answer'] for r in nat], [r['answer'] for r in rev])
        for a, b in zip(nat, rev):
            self.assertEqual(a['alice_order'], 'AB' if a['answer'] == 1 else 'BA')
            self.assertNotEqual(a['alice_order'], b['alice_order'])
            self.assertEqual((a['outcome'], b['outcome']), ('correct', 'correct'))
            self.assertEqual(a['bob_choice'], str(a['answer']))

    def test_reversed_presentation_flips(self):
        rev = discovery.sender_messages('natural', discovery.templates(config())[0], 1, 'reversed-first')[0]['content']
        self.assertIn('Alice submits BA or AB', rev)
        self.assertIn('Bob chooses 2, 1, or pass.', rev)

    def test_tasks_paired_by_template_and_balanced(self):
        jobs = discovery.prepare(copy.deepcopy(config()))
        self.assertEqual([len(j['tasks']) for j in jobs], [24, 24])
        for j in jobs:
            for t in range(1, 7):
                self.assertEqual(sum(x['template'] == t for x in j['tasks']), 4)
        tpl_answers = lambda j, t: next(x for x in j['tasks'] if x['template'] == t)['input'][1]['content']
        for t in range(1, 7):
            a = json.loads(tpl_answers(jobs[0], t).split('rounds: ')[1].split('\n')[0])
            b = json.loads(tpl_answers(jobs[1], t).split('rounds: ')[1].split('\n')[0])
            self.assertEqual([r['answer'] for r in a], [r['answer'] for r in b])

    def test_cap(self):
        self.assertLessEqual(sum(j['ceiling_usd'] for j in config()['jobs']), 0.6 + 1e-12)


class DiscoveryRunTests(unittest.TestCase):
    def test_scripted_run_audits_and_summarizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = discovery.execute(copy.deepcopy(config('scripted')), output_dir=tmp)
            report = json.loads((root / 'summary.json').read_text())
            self.assertTrue(report['complete'])
            self.assertTrue(all(j['audit'] for j in report['jobs']))
            claim = report['analysis']['claims']['feedback-sets-convention']
            # The scripted client always encodes naturally, whatever the history: no difference.
            self.assertEqual(claim['templates'], 6)
            self.assertFalse(claim['confirmed'])
            again = discovery.resume(root)
            self.assertTrue(again['complete'])


if __name__ == '__main__':
    unittest.main()
