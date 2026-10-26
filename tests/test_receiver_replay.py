import json
import tempfile
import unittest

from order_signal.learning import run
from order_signal.receiver_replay import prepare
from order_signal.run import PROJECT


class ReplayTests(unittest.TestCase):
    def test_forks_preserve_history_and_hide_current_secret(self):
        cfg = json.loads((PROJECT / 'configs/learning-pilot.json').read_text())
        cfg['base'] = json.loads((PROJECT / 'configs/default.json').read_text())
        cfg.update(pairs=1, training_rounds=2, evaluation_rounds=3, arm_ids=['A1'])
        with tempfile.TemporaryDirectory() as tmp:
            root = run(cfg, output_dir=tmp)
            _, tasks = prepare(root, 784103)
            self.assertEqual(len(tasks), 6)
            histories = set()
            for task in tasks:
                self.assertEqual(task['input'][-1]['content'].splitlines()[-1], 'Observed order: ' + task['order'])
                histories.add(task['input'][-1]['content'].rsplit('\n', 1)[0])
                matching = [t for t in tasks if t['source_trial_id'] == task['source_trial_id']]
                self.assertEqual({t['delivery'] for t in matching}, {'actual', 'random'})
                self.assertEqual(len({t['secret'] for t in matching}), 1)
            self.assertEqual(len(histories), 1)
            cfg['arm_ids'] = ['M2']
            (root / 'config.json').write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):
                prepare(root, 784103)
