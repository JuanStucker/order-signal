"""Adapted Colosseum transport/accounting checks; all calls mocked."""

import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from order_signal.budget import DollarRequestBudget
from order_signal.clients import AuditedClient, DeepSeekClient, deepseek_settings
from order_signal.protocol import Agent
from order_signal.prompts import tool


def body(**changes):
    return {
        "status": "completed",
        "model": "test-model",
        "output": [
            {
                "type": "function_call",
                "call_id": "call-1",
                "name": "submit_order",
                "arguments": '{"order":"AB"}',
            }
        ],
        "usage": {
            "input_tokens": 1000,
            "input_tokens_details": {"cached_tokens": 900},
            "output_tokens": 100,
        },
        **changes,
    }


class TransportBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.budget = DollarRequestBudget(
            3,
            ceiling_usd=1,
            prices={"input": 1.32, "cached_input": 0.044, "output": 3.96},
            path=self.path / "budget.json",
        )
        self.params = {
            "max_output_tokens": 512,
            "temperature": 1,
            "reasoning_effort": "none",
            "tools": [tool("sender")],
        }
        self.agent = Agent("alice", "sender", "Alice")

    def call(self, response):
        sdk = SimpleNamespace(
            responses=SimpleNamespace(create=Mock(return_value=response))
        )
        client = DeepSeekClient(model="test-model", sdk_client=sdk)
        audited = AuditedClient(
            client, budget=self.budget, path=self.path / "calls.jsonl"
        )
        return audited.decide(
            self.agent, [], self.params, trial_id="t", condition_id="C1"
        )

    def test_payload_normalized_and_accounted(self):
        sdk = SimpleNamespace(
            responses=SimpleNamespace(create=Mock(return_value=body()))
        )
        normalized = DeepSeekClient(model="test-model", sdk_client=sdk).generate(
            [], self.params
        )
        self.assertEqual(
            normalized["calls"],
            [{"name": "submit_order", "arguments": {"order": "AB"}}],
        )
        request = sdk.responses.create.call_args.kwargs
        self.assertEqual(
            set(request),
            {
                "model",
                "input",
                "max_output_tokens",
                "reasoning",
                "temperature",
                "tools",
                "tool_choice",
            },
        )
        self.assertEqual(request["tool_choice"], "required")
        self.assertEqual(self.call(body()), "AB")
        self.assertAlmostEqual(
            self.budget.accounted, (100 * 1.32 + 900 * 0.044 + 100 * 3.96) / 1e6
        )
        self.assertEqual(self.budget.pending, {})

    def test_thinking_uses_auto_tool_selection(self):
        sdk = SimpleNamespace(responses=SimpleNamespace(create=Mock(return_value=body())))
        params = {**self.params, "reasoning_effort": "low"}
        DeepSeekClient(model="test-model", sdk_client=sdk).generate([], params)
        self.assertEqual(sdk.responses.create.call_args.kwargs["tool_choice"], "auto")
        self.assertEqual(sdk.responses.create.call_args.kwargs["reasoning"], {"effort": "low"})

    def test_stream_consumes_terminal_response_and_closes(self):
        class Events:
            def __init__(self, terminal=True):
                self.closed = False
                self.terminal = terminal
            def __iter__(self):
                yield SimpleNamespace(type="response.created")
                if self.terminal:
                    yield SimpleNamespace(type="response.completed", response=body())
            def close(self):
                self.closed = True
        for terminal in (True, False):
            events = Events(terminal)
            sdk = SimpleNamespace(responses=SimpleNamespace(create=Mock(return_value=events)))
            client = DeepSeekClient(model="test-model", sdk_client=sdk)
            if terminal:
                result = client.generate([], {**self.params, "stream": True})
                self.assertEqual(result["calls"][0]["arguments"], {"order": "AB"})
            else:
                with self.assertRaisesRegex(RuntimeError, "terminal_response"):
                    client.generate([], {**self.params, "stream": True})
            self.assertTrue(events.closed)
            self.assertTrue(sdk.responses.create.call_args.kwargs["stream"])

    def test_invalid_raw_is_retained_billed_and_stops(self):
        variants = [
            body(status="incomplete"),
            body(output=[]),
            body(error={"message": "remote_error"}),
        ]
        for args in (
            '{"order":',
            "[]",
            '{"order":"AB","extra":1}',
            '{"order":1}',
            '{"order":"bad"}',
        ):
            bad = body()
            bad["output"][0]["arguments"] = args
            variants.append(bad)
        bad = body()
        bad["output"][0]["name"] = "submit_choice"
        variants.append(bad)
        bad = body()
        bad["output"].append({**bad["output"][0], "call_id": "call-2"})
        variants.append(bad)
        for raw in variants:
            with self.subTest(raw=raw):
                self.budget = DollarRequestBudget(
                    3,
                    ceiling_usd=1,
                    prices={"input": 1, "cached_input": 0, "output": 1},
                    path=self.path / "budget.json",
                )
                with self.assertRaises((ValueError, RuntimeError)):
                    self.call(raw)
                self.assertEqual(self.budget.responses, 1)
                self.assertGreater(self.budget.accounted, 0)
                self.assertEqual(self.budget.pending, {})
                with self.assertRaises(RuntimeError):
                    self.call(body())
        logs = [
            json.loads(s) for s in (self.path / "calls.jsonl").read_text().splitlines()
        ]
        self.assertTrue(any(r.get("invalid_response") for r in logs))
        self.assertTrue(
            any(r.get("response", {}).get("raw", {}).get("output") for r in logs)
        )

    def test_missing_usage_retains_reservation(self):
        with self.assertRaises(RuntimeError):
            self.call(body(usage=None))
        self.assertIn("1", self.budget.pending)
        with self.assertRaises(RuntimeError):
            self.call(body())

    def test_request_limit_and_cost_refuse_before_call(self):
        with self.assertRaises(RuntimeError):
            self.budget.reserve([], {"max_output_tokens": 1000000})
        self.assertEqual(self.budget.used, 0)
        for _ in range(3):
            self.call(body())
        with self.assertRaises(RuntimeError):
            self.call(body())
        self.assertEqual(self.budget.used, 3)

    def test_model_identity_change_stops_pooling(self):
        self.call(body())
        with self.assertRaises(RuntimeError):
            self.call(body(model="other"))
        self.assertEqual(self.budget.blocked_reason, "model_changed")

    def test_usage_overrun_and_bad_cached_usage(self):
        for usage in (
            {"input_tokens": 100000000, "output_tokens": 1},
            {
                "input_tokens": 1,
                "output_tokens": 1,
                "input_tokens_details": {"cached_tokens": 2},
            },
        ):
            self.budget = DollarRequestBudget(
                3,
                ceiling_usd=1,
                prices={"input": 1, "cached_input": 0, "output": 1},
                path=self.path / "budget.json",
            )
            with self.assertRaises(RuntimeError):
                self.call(body(usage=usage))
            with self.assertRaises(RuntimeError):
                self.call(body())

    def test_network_failure_no_retry_or_remote_error_logging(self):
        create = Mock(side_effect=ConnectionError("remote-secret"))
        sdk = SimpleNamespace(responses=SimpleNamespace(create=create))
        audited = AuditedClient(
            DeepSeekClient(model="test", sdk_client=sdk),
            budget=self.budget,
            path=self.path / "calls.jsonl",
        )
        for _ in range(2):
            with self.assertRaises((ConnectionError, RuntimeError)):
                audited.decide(
                    self.agent, [], self.params, trial_id="t", condition_id="C1"
                )
        self.assertEqual(create.call_count, 1)
        self.assertIn("1", self.budget.pending)
        self.assertNotIn("remote-secret", (self.path / "calls.jsonl").read_text())

    def test_credentials_and_optional_lazy_sdk(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                deepseek_settings()
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fake"}, clear=True):
            for endpoint in (
                "http://api.deepseek.com",
                "https://evil.example",
                "https://api.deepseek.com?secret",
                "https://u:secret@api.deepseek.com",
                "https://api.deepseek.com:invalid",
            ):
                with self.assertRaises(ValueError):
                    deepseek_settings(base_url=endpoint)
            sdk_module = SimpleNamespace(OpenAI=Mock())
            with patch.dict("sys.modules", {"openai": sdk_module}):
                DeepSeekClient(model="test")
            sdk_module.OpenAI.assert_called_once_with(
                api_key="fake",
                base_url="https://api.deepseek.com/",
                timeout=60,
                max_retries=0,
            )


if __name__ == "__main__":
    unittest.main()


class AdditionalValidationTests(unittest.TestCase):
    setUp = TransportBudgetTests.setUp
    call = TransportBudgetTests.call

    def test_missing_model_is_billed_but_stops(self):
        with self.assertRaises(RuntimeError):
            self.call(body(model=None))
        self.assertGreater(self.budget.accounted, 0)
        self.assertEqual(self.budget.blocked_reason, "missing_model_identity")

    def test_duplicate_json_argument_keys_rejected(self):
        raw = body()
        raw["output"][0]["arguments"] = '{"order":"BA","order":"AB"}'
        with self.assertRaises(RuntimeError):
            self.call(raw)
        self.assertGreater(self.budget.accounted, 0)

    def test_echoed_credentials_redacted_from_raw_audit(self):
        raw = body(status="failed", error={"message": "echo: test-secret-token"})
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-secret-token"}):
            with self.assertRaises(RuntimeError):
                self.call(raw)
        text = (self.path / "calls.jsonl").read_text()
        self.assertNotIn("test-secret-token", text)
        self.assertIn("[REDACTED]", text)
