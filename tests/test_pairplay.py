import json
import tempfile
import unittest

from order_signal import pairplay, phase2, restraint as rs, screen
from order_signal.protocol import ReceiverObservation, SenderObservation


def scripted_config(arms=('matched-actual', 'matched-shuffled', 'explicit-seeded')):
    return dict(version=pairplay.VERSION, mode='scripted', phase='verification', model='scripted', seed=11,
                pairs=2, rounds=3, arms=list(arms), ceiling_per_pair_usd=0.5, ceiling_usd=3.0,
                prices_usd_per_million=dict(input=1.32, cached_input=0.044, output=3.96),
                generation=dict(max_output_tokens=1024, temperature=1.0, reasoning_effort='low'))


class PromptTests(unittest.TestCase):
    def test_sender_and_receiver_differ_only_in_role_and_current_line(self):
        s = pairplay.messages('matched-actual', SenderObservation(1, 'individual'), [], 'natural-first')
        r = pairplay.messages('matched-actual', ReceiverObservation('AB', 'individual'), [], 'natural-first')
        self.assertEqual(s[0]['content'].replace(rs.MATCHED_SENDER_ROLE, pairplay.RECEIVER_ROLE), r[0]['content'])
        self.assertTrue(s[1]['content'].endswith('Current hidden answer: 1'))
        self.assertTrue(r[1]['content'].endswith('Observed order: AB'))
        self.assertNotIn('single round', s[0]['content'])

    def test_sender_prompt_matches_feedback_probe_except_phase(self):
        h = [dict(answer=1, observed_order='AB', choice='1', outcome='correct')]
        for arm, prompt in (('matched-actual', 'anchor'), ('explicit-seeded', 'explicit')):
            mine = pairplay.messages(arm, SenderObservation(2, 'individual'), h, 'reversed-first')
            probe = phase2.feedback_messages(prompt, h, 2, 'reversed-first')
            self.assertEqual(mine[0], probe[0])
            self.assertEqual(mine[1]['content'], probe[1]['content'].replace('Phase: evaluation', 'Phase: training'))

    def test_explicit_rule_reaches_both_agents(self):
        r = pairplay.messages('explicit-seeded', ReceiverObservation('BA', 'individual'), [], 'natural-first')
        self.assertIn(screen.EXPLICIT_RULE, r[0]['content'])

    def test_schedule_shares_secrets_and_alternates_listing(self):
        jobs = pairplay.schedule(scripted_config())
        p1 = [j for j in jobs if j['pair'] == 1]
        self.assertEqual(len({tuple(j['secrets']) for j in p1}), 1)
        self.assertEqual({j['presentation'] for j in jobs if j['pair'] == 2}, {'reversed-first'})
        seeded = [j for j in jobs if j['arm'] == 'explicit-seeded']
        self.assertTrue(all(len(j['initial_history']) == 4 for j in seeded))
        self.assertTrue(all(not j['initial_history'] for j in jobs if j['arm'] != 'explicit-seeded'))


class RunTests(unittest.TestCase):
    def test_scripted_run_audits_and_summarizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pairplay.execute(scripted_config(), output_dir=tmp)
            report = json.loads((root / 'summary.json').read_text())
            self.assertTrue(report['complete'])
            self.assertTrue(all(p['audit'] for p in report['pairs']))
            # Scripted agents use the natural convention: actual delivery always wins.
            self.assertEqual(report['arms']['matched-actual']['accuracy'], 1)
            self.assertEqual(report['actual_minus_shuffled']['pair_gain']['pairs'], 2)

    def test_audit_detects_altered_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pairplay.execute(scripted_config(('matched-actual',)), output_dir=tmp)
            path = root / 'matched-actual-p1'
            rows = [json.loads(l) for l in (path / 'trials.jsonl').read_text().splitlines()]
            rows[0]['delivered_observation']['order'] = 'BA' if rows[0]['actual_order'] == 'AB' else 'AB'
            (path / 'trials.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
            job = next(j for j in json.loads((root / 'plan.json').read_text())['jobs'] if j['id'] == 'matched-actual-p1')
            self.assertFalse(pairplay.audit(job, path, json.loads((root / 'config.json').read_text())))


if __name__ == '__main__':
    unittest.main()
