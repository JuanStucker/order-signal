import copy
import json
from pathlib import Path
import tempfile
import unittest

from order_signal.diagnostics import diagnostic_summary
from order_signal.planning import plan
from order_signal.run import PROJECT, run, validate


class DiagnosticTests(unittest.TestCase):
    def rows(self, inverse=False, outcome="pass"):
        return [
            {"secret": s, "actual_order": ("AB" if (s == 1) != inverse else "BA"),
             "status": "completed", "outcome": outcome}
            for s in (1, 2) for _ in range(20)
        ]

    def test_leakage_detected_even_when_receiver_always_passes(self):
        for inverse, expected in ((False, 1), (True, -1)):
            result = diagnostic_summary(self.rows(inverse), complete=True)
            self.assertEqual(result["sender_mi_bits"], 1)
            self.assertEqual(result["encoding_difference"], expected)
            self.assertEqual(result["attempt_rate"], 0)
            self.assertIsNone(result["conditional_accuracy"])
            self.assertIsNone(result["conditional_accuracy_pointwise_interval"])

    def test_independent_orders_and_selective_accuracy(self):
        rows = self.rows()
        for i, r in enumerate(rows):
            r["actual_order"] = "AB" if i % 2 else "BA"
            r["outcome"] = ("correct", "wrong", "pass", "pass")[i % 4]
        result = diagnostic_summary(rows, complete=True)
        self.assertEqual(result["sender_mi_bits"], 0)
        self.assertEqual(result["attempt_rate"], 0.5)
        self.assertEqual(result["conditional_accuracy"], 0.5)
        self.assertEqual(result["encoding_difference"], 0)

    def test_receiver_failure_retains_encoding_without_inferential_intervals(self):
        rows = self.rows()
        rows[0].update(status="failed")
        rows[0].pop("outcome")
        result = diagnostic_summary(rows, complete=False)
        self.assertEqual(result["sender_n"], 40)
        self.assertIsNone(result["attempt_rate_pointwise_interval"])
        empty = diagnostic_summary([], complete=False)
        self.assertIsNone(empty["sender_mi_bits"])
        self.assertIsNone(empty["encoding_difference"])

    def test_capability_is_separate_authorized_and_audited(self):
        cfg = json.loads((PROJECT / "configs/capability.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = run(cfg, output_dir=Path(tmp))
            report = json.loads((root / "summary.json").read_text())
            self.assertEqual(report["study"], "capability")
            self.assertTrue(report["checks"]["input_boundary_verified"])
            self.assertFalse(any(report["evidence"].values()))
            actual = report["conditions"][0]
            self.assertEqual(actual["conditional_accuracy"], 1)
            self.assertEqual(actual["attempt_rate"], 1)
            # Finite fair draws need not be balanced; perfect encoding yields
            # empirical secret entropy, which may be below one bit.
            self.assertGreater(actual["sender_mi_bits"], 0.9)
            self.assertEqual(actual["encoding_difference"], 1)
            requests = [json.loads(s) for s in (root / "calls.jsonl").read_text().splitlines()]
            for request in requests:
                if request["event"] == "request":
                    text = str(request["input"])
                    self.assertIn("explicitly authorized", text)
                    self.assertIn("AB means 1; BA means 2", text)
                    self.assertNotIn("not authorized for disclosure", text)
            # A free-text leak must fail the exact input audit in controls too.
            from order_signal.analyze import analyze
            next(r for r in requests if r["event"] == "request")["input"][0]["content"] += " extra"
            (root / "calls.jsonl").write_text("".join(json.dumps(r) + "\n" for r in requests))
            self.assertFalse(analyze(root)["checks"]["input_boundary_verified"])
        cfg["study"] = "main"
        with self.assertRaises(ValueError):
            validate(cfg)

    def test_random_channel_audit_detects_tampering_even_with_matching_prompt(self):
        from order_signal.analyze import analyze
        from order_signal.prompts import build
        from order_signal.protocol import ReceiverObservation

        cfg = json.loads((PROJECT / "configs/default.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = run(cfg, output_dir=Path(tmp))
            trials = [json.loads(s) for s in (root / "trials.jsonl").read_text().splitlines()]
            trial = next(t for t in trials if t["condition_id"] == "C4")
            observed = trial["delivered_observation"]
            observed["order"] = "BA" if observed["order"] == "AB" else "AB"
            calls = [json.loads(s) for s in (root / "calls.jsonl").read_text().splitlines()]
            request = next(c for c in calls if c["event"] == "request" and c["trial_id"] == trial["trial_id"] and c["role"] == "receiver")
            request["input"] = build(ReceiverObservation(observed["order"], "individual"))
            for name, rows in (("trials.jsonl", trials), ("calls.jsonl", calls)):
                (root / name).write_text("".join(json.dumps(r) + "\n" for r in rows))
            self.assertFalse(analyze(root)["checks"]["input_boundary_verified"])


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.scenario = json.loads((PROJECT / "configs/planning-scenario.json").read_text())

    def test_more_power_or_smaller_effect_requires_more_trials(self):
        base = plan(self.scenario)
        self.assertGreater(base["rounds_per_condition"], 100)
        self.assertGreater(plan(self.scenario, power=0.95)["rounds_per_condition"], base["rounds_per_condition"])
        weaker = copy.deepcopy(self.scenario)
        weaker["C3"] = {"correct": 0.6, "wrong": 0.1, "pass": 0.3}
        self.assertGreater(plan(weaker)["rounds_per_condition"], base["rounds_per_condition"])
        self.assertLess(plan(self.scenario, level="basic")["rounds_per_condition"], base["rounds_per_condition"])
        self.assertEqual(base["main_requests"], 8 * base["rounds_per_condition"])

    def test_null_and_invalid_scenarios_cannot_generate_sample_size(self):
        for bad in ({"correct": 0, "wrong": 0, "pass": 1},
                    {"correct": 0.8, "wrong": 0.1, "pass": 0.5},
                    {"correct": float("nan"), "wrong": 0, "pass": 0}):
            scenario = copy.deepcopy(self.scenario)
            scenario["C3"] = bad
            with self.assertRaises(ValueError):
                plan(scenario)
