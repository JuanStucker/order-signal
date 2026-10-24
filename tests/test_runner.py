import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from order_signal.clients import ScriptedClient
from order_signal.run import PROJECT, run, schedule


def config():
    return json.loads((PROJECT / "configs/default.json").read_text())


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def test_complete_scripted_run_audit_and_summary(self):
        root = run(config(), output_dir=self.path)
        status = json.loads((root / "status.json").read_text())
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["requests"], 160)
        rows = [json.loads(s) for s in (root / "trials.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), 80)
        summary = json.loads((root / "summary.json").read_text())
        self.assertFalse(any(summary["evidence"].values()))
        self.assertTrue(summary["checks"]["input_boundary_verified"])
        for row in summary["conditions"]:
            if row["condition"] in ("C1", "C3"):
                self.assertEqual(row["pair_gain"], 2)
                self.assertEqual(row["organization_loss"], 3)
            else:
                self.assertLess(row["pair_gain"], 2)
        logs = [json.loads(s) for s in (root / "calls.jsonl").read_text().splitlines()]
        requests = [r for r in logs if r["event"] == "request"]
        receiver_systems = set()
        for request in requests:
            self.assertEqual(len(request["input"]), 2)
            self.assertNotIn("condition_id", json.dumps(request["input"]))
            if request["role"] == "receiver":
                trial = next(r for r in rows if r["trial_id"] == request["trial_id"])
                self.assertEqual(
                    request["input"][1]["content"].splitlines()[-1],
                    "Observed order: " + trial["delivered_observation"]["order"],
                )
                receiver_systems.add(request["input"][0]["content"])
        self.assertEqual(len(receiver_systems), 1)
        ledger = json.loads((root / "budget.json").read_text())
        self.assertEqual(ledger["accounted_cost_usd"], 0)
        self.assertEqual(ledger["pending_reservations_usd"], {})
        self.assertTrue((root / "source/uv.lock").is_file())
        self.assertTrue((root / "summary.csv").is_file())

    def test_balanced_schedule_independent_random_streams(self):
        a = config()
        b = copy.deepcopy(a)
        b["seeds"]["channel"] += 100
        self.assertEqual(schedule(a), schedule(b))
        b["seeds"]["schedule"] += 100
        self.assertEqual(
            [t["secret"] for t in schedule(a)], [t["secret"] for t in schedule(b)]
        )
        self.assertNotEqual(
            [t["condition_id"] for t in schedule(a)],
            [t["condition_id"] for t in schedule(b)],
        )
        for cid in ("C1", "C2", "C3", "C4"):
            self.assertEqual(sum(t["condition_id"] == cid for t in schedule(a)), 20)

    def test_failure_is_not_pass_or_replenished(self):
        class BadReceiver(ScriptedClient):
            def generate(self, messages, params):
                response = super().generate(messages, params)
                if params["tools"][0]["name"] == "submit_choice":
                    response["calls"][0]["arguments"]["extra"] = "invalid"
                return response

        root = run(config(), output_dir=self.path, client=BadReceiver())
        status = json.loads((root / "status.json").read_text())
        self.assertEqual(
            (status["status"], status["failed_trials"], status["requests"]),
            ("incomplete", 1, 2),
        )
        trials = [
            json.loads(s) for s in (root / "trials.jsonl").read_text().splitlines()
        ]
        self.assertEqual(len(trials), 1)
        self.assertEqual(trials[0]["status"], "failed")
        self.assertIn("execution", trials[0])
        self.assertNotIn("rewards", trials[0])
        self.assertNotIn("choice", trials[0])
        summary = json.loads((root / "summary.json").read_text())
        self.assertTrue(
            all(r["pair_gain_interval"] is None for r in summary["conditions"])
        )

    def test_budget_stop_mid_round_retains_executed_action(self):
        cfg = config()
        cfg["budget"]["max_requests"] = 1
        root = run(cfg, output_dir=self.path)
        trial = json.loads((root / "trials.jsonl").read_text())
        self.assertEqual(trial["requests"], 1)
        self.assertIn("execution", trial)
        self.assertNotIn("rewards", trial)

    def test_invalid_configs_rejected_before_output(self):
        changes = [
            lambda c: c.update(num_agents=3),
            lambda c: c["agents"][1].update(model="other"),
            lambda c: c["conditions"][0].update(delivery="masked"),
            lambda c: c["generation"].update(retries=2),
            lambda c: c["budget"].update(ceiling_usd=float("nan")),
            lambda c: c.update(rounds_per_condition=True),
            lambda c: c.update(mode="deepseek", phase="pilot"),
        ]
        for change in changes:
            cfg = config()
            change(cfg)
            with self.assertRaises(ValueError):
                run(cfg, output_dir=self.path)
        self.assertEqual(list(self.path.iterdir()), [])

    def test_clean_copy_without_sdk_credentials_network_or_colosseum(self):
        isolated = self.path / "standalone"
        shutil.copytree(PROJECT / "src", isolated / "src")
        shutil.copytree(PROJECT / "configs", isolated / "configs")
        for filename in ("pyproject.toml", "uv.lock", "SOURCE_PROVENANCE.json"):
            shutil.copy(PROJECT / filename, isolated / filename)
        script = """
import sys, json, socket, importlib.abc
from pathlib import Path
sys.path.insert(0, str(Path.cwd()/"src"))
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'openai','httpx','colosseum','experiments','terrarium','llm_server'}:
            raise AssertionError('forbidden dependency: '+fullname)
sys.meta_path.insert(0, Block())
def audit(event, args):
    if event == 'open' and 'colosseum' in str(args[0]):
        raise AssertionError('forbidden checkout access')
sys.addaudithook(audit)
def no_network(*a, **kw):
    raise AssertionError('network forbidden')
socket.socket = no_network
from order_signal.run import run
root = run(json.loads(Path('configs/default.json').read_text()))
assert json.loads((root/'status.json').read_text())['status'] == 'completed'
print('isolated offline success')
"""
        result = subprocess.run(
            [sys.executable, "-I", "-c", script],
            cwd=isolated,
            env={"PATH": os.defpath},
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("isolated offline success", result.stdout)


if __name__ == "__main__":
    unittest.main()
