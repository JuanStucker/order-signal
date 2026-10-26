import copy
import json
import random
import tempfile
import unittest

from order_signal import probes, prompts, restraint as rs
from order_signal.protocol import ReceiverObservation, SenderObservation
from order_signal.run import PROJECT


def scripted_config():
    cfg = json.loads((PROJECT / 'configs/restraint-probes.json').read_text())
    cfg.update(mode='scripted', phase='verification')
    for job in cfg['jobs']:
        for key, value in (('repeats_per_secret', 4), ('repeats_per_order', 4), ('templates', 2)):
            if key in job:
                job[key] = value
    return cfg


class RestraintPromptTests(unittest.TestCase):
    def test_corners_reproduce_earlier_prompts_exactly(self):
        for s in (1, 2):
            self.assertEqual(rs.sender_messages('aw0-v3-rlabel', s), prompts.build(SenderObservation(s, 'individual')))
            self.assertEqual(rs.sender_messages('aw1-matched-plain', s), probes.permission_messages('matched_restricted', s))
            self.assertEqual(rs.sender_messages('aw1-matched-plain-auth', s),
                             probes.permission_messages('matched_authorized', s))
        for o in ('AB', 'BA'):
            self.assertEqual(rs.receiver_messages('v3', o), prompts.build(ReceiverObservation(o, 'individual')))
        self.assertEqual(rs.tool('sender', 'natural-first'), prompts.tool('sender'))

    def test_each_factor_changes_only_its_text(self):
        base = rs.sender_messages('aw0-v3-rlabel', 2)
        aware = rs.sender_messages('aw1-v3-rlabel', 2)
        self.assertEqual(aware[1], base[1])
        self.assertEqual(aware[0]['content'], probes.AWARENESS + ' ' + base[0]['content'])
        plain = rs.sender_messages('aw0-v3-plain', 2)
        self.assertEqual(plain[0], base[0])
        self.assertTrue(plain[1]['content'].endswith('Current hidden answer: 2'))
        nouse = rs.sender_messages('aw0-v3-nouse-rlabel', 2)
        self.assertEqual(nouse[1], base[1])
        self.assertEqual(nouse[0]['content'].replace(rs.CONFIDENTIALITY_NO_USE, prompts.CONFIDENTIALITY), base[0]['content'])
        self.assertNotIn('do not use', nouse[0]['content'])

    def test_no_channel_removes_only_the_observation(self):
        with_channel = rs.sender_messages('aw1-matched-plain', 1)[0]['content']
        without = rs.sender_messages('aw1-matched-plain-nochan', 1)[0]['content']
        self.assertNotIn('ordered record', without)
        self.assertEqual(without.replace(rs.NO_CHANNEL_SENTENCE, rs.CHANNEL_SENTENCE)
                         .replace(rs.AWARENESS_NO_CHANNEL, probes.AWARENESS), with_channel)
        with self.assertRaises(ValueError):
            rs.parse_cell('aw0-matched-plain-nochan')
        with self.assertRaises(ValueError):
            rs.parse_cell('aw1-v3-rlabel-auth')

    def test_reversed_presentation_flips_symbols_and_enum(self):
        for cell in rs.SENDER_CELLS:
            nat = rs.sender_messages(cell, 1)[0]['content']
            rev = rs.sender_messages(cell, 1, 'reversed-first')[0]['content']
            self.assertIn('Alice submits BA or AB', rev)
            self.assertIn('drawn fairly from 2 and 1', rev)
            self.assertEqual(len(nat), len(rev))
        for cell in rs.RECEIVER_CELLS:
            self.assertIn('Choose 2, 1, or pass', rs.receiver_messages(cell, 'AB', 'reversed-first')[0]['content'])
        self.assertEqual(rs.tool('sender', 'reversed-first')['parameters']['properties']['order']['enum'], ['BA', 'AB'])
        self.assertEqual(rs.tool('receiver', 'reversed-first')['parameters']['properties']['choice']['enum'],
                         ['2', '1', 'pass'])

    def test_conflict_histories_are_three_to_one_complements(self):
        tpl = rs.conflict_template(random.Random(5))
        nat, rev = rs.conflict_history('majority-natural', tpl), rs.conflict_history('majority-reversed', tpl)
        n = sum(probes.natural_order(r['answer']) == r['observed_order'] for r in nat)
        self.assertEqual(n, 3)
        self.assertTrue(all(a['observed_order'] != b['observed_order'] for a, b in zip(nat, rev)))

    def test_tasks_balance_presentation_and_hide_answers_from_receivers(self):
        job = dict(id='x', study='decomposition', cell='aw1-matched-plain', regimen='none', repeats_per_secret=6)
        tasks = rs.sender_tasks(job)
        for s in (1, 2):
            for p in rs.PRESENTATIONS:
                self.assertEqual(sum(t['current'] == s and t['presentation'] == p for t in tasks), 3)
        job = dict(id='y', study='feedback-restricted', role='receiver', regimen='none', templates=2)
        for t in rs.feedback_tasks(job, 3):
            self.assertNotIn('private answer', t['input'][-1]['content'])
            self.assertTrue(t['input'][-1]['content'].endswith('Observed order: ' + t['current']))

    def test_scripted_run_audits_summarizes_and_detects_tampering(self):
        cfg = scripted_config()
        with tempfile.TemporaryDirectory() as tmp:
            root = rs.execute(copy.deepcopy(cfg), output_dir=tmp)
            report = json.loads((root / 'summary.json').read_text())
            self.assertTrue(report['complete'])
            self.assertTrue(all(j['audit'] for j in report['jobs']))
            none = report['analysis']['none']
            # The scripted client always encodes naturally, so no factor has an effect.
            self.assertEqual(none['primary_main_effects']['awareness']['estimate'], 0)
            self.assertEqual(none['cells']['aw0-v3-rlabel']['difference'], 1)
            self.assertEqual(none['end_to_end']['v3']['point']['accuracy'], 1)
            plan = json.loads((root / 'plan.json').read_text())
            job = plan['jobs'][0]
            calls = root / job['id'] / 'calls.jsonl'
            lines = calls.read_text().splitlines()
            first = json.loads(lines[0])
            first['params']['tools'][0]['parameters']['properties']['order']['enum'].reverse()
            calls.write_text('\n'.join([json.dumps(first)] + lines[1:]) + '\n')
            self.assertFalse(rs.audit(job, root / job['id'], json.loads((root / 'config.json').read_text())))

    def test_ceiling_validation(self):
        cfg = scripted_config()
        cfg['jobs'][0]['ceiling_usd'] = 99
        with self.assertRaises(ValueError):
            rs.prepare(cfg)

    def test_encoding_and_contrast(self):
        e = rs.encoding([[10, 0], [0, 10]])
        self.assertEqual(e['difference'], 1)
        self.assertGreater(e['variance'], 0)
        c = rs.contrast([e], [e], 2)
        self.assertEqual(c['estimate'], 0)


if __name__ == '__main__':
    unittest.main()


class APIStatusError(Exception):
    """Stands in for the SDK's 402 insufficient-balance error (matched by class name)."""


class APITimeoutError(Exception):
    pass


class FailingClient(rs.ScriptedClient):
    def __init__(self, after, error):
        self.after, self.error, self.calls = after, error, 0

    def generate(self, messages, params):
        self.calls += 1
        if self.calls > self.after:
            raise self.error('stop')
        return super().generate(messages, params)


class ResumeTests(unittest.TestCase):
    def config(self):
        cfg = scripted_config()
        cfg['jobs'] = [j for j in cfg['jobs'] if j['study'] == 'decomposition'][:2]
        cfg['ceiling_usd'] = sum(j['ceiling_usd'] for j in cfg['jobs'])
        return cfg

    def test_credit_failure_resumes_in_place_and_audits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = rs.execute(self.config(), output_dir=tmp, client_factory=lambda: FailingClient(3, APIStatusError))
            report = json.loads((root / 'summary.json').read_text())
            self.assertFalse(report['complete'])
            self.assertTrue(all(j['audit'] for j in report['jobs']))
            self.assertEqual({j['status']['completed'] for j in report['jobs']}, {3})
            report = rs.resume(root)
            self.assertTrue(report['complete'])
            for j in report['jobs']:
                self.assertTrue(j['audit'])
                self.assertEqual(j['status']['segments'], 2)
                self.assertEqual(j['status']['abandoned'], [])
            # The failed task was re-sent exactly once, immediately on resume.
            calls = rs.load(root / report['jobs'][0]['id'], 'calls.jsonl')
            ids = [c['trial_id'] for c in calls if c['event'] == 'request']
            self.assertEqual(len(ids), len(set(ids)) + 1)

    def test_timeout_is_never_resent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = rs.execute(self.config(), output_dir=tmp, client_factory=lambda: FailingClient(2, APITimeoutError))
            report = rs.resume(root)
            for j in report['jobs']:
                self.assertTrue(j['audit'])
                self.assertEqual(len(j['status']['abandoned']), 1)
                self.assertEqual(j['status']['completed'], j['status']['planned'] - 1)
            # A re-sent request after a non-retryable failure must fail the audit.
            job = json.loads((root / 'plan.json').read_text())['jobs'][0]
            path = root / job['id']
            calls = rs.load(path, 'calls.jsonl')
            failed = next(c for c in calls if c['event'] == 'error')
            first = next(c for c in calls if c['event'] == 'request' and c['trial_id'] == failed['trial_id'])
            with (path / 'calls.jsonl').open('a') as f:
                f.write(json.dumps(first) + '\n')
            self.assertFalse(rs.audit(job, path, json.loads((root / 'config.json').read_text())))
