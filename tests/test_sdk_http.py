"""Optional actual-SDK tests with HTTP mocked: install the live extra to run."""

import importlib.util
import json
import unittest
from order_signal.clients import DeepSeekClient, InvalidDeepSeekResponse
from order_signal.prompts import tool

HAS_SDK = importlib.util.find_spec("openai") is not None


@unittest.skipUnless(HAS_SDK, "optional live SDK not installed")
class SDKHTTPTests(unittest.TestCase):
    def sdk(self, handler):
        import httpx
        from openai import OpenAI

        sdk = OpenAI(
            api_key="fake-test-key",
            base_url="https://api.deepseek.com/",
            max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        self.addCleanup(sdk.close)
        return sdk

    def params(self):
        return {
            "max_output_tokens": 512,
            "temperature": 1,
            "reasoning_effort": "none",
            "tools": [tool("sender")],
        }

    def response(self):
        return {
            "id": "resp-test",
            "object": "response",
            "created_at": 1,
            "status": "completed",
            "model": "test-model",
            "output": [
                {
                    "type": "function_call",
                    "id": "fc-test",
                    "call_id": "call-test",
                    "name": "submit_order",
                    "arguments": '{"order":"AB"}',
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }

    def test_actual_sdk_serialization_and_normalization(self):
        import httpx

        seen = []

        def handler(request):
            self.assertEqual(str(request.url), "https://api.deepseek.com/responses")
            seen.append(json.loads(request.content))
            return httpx.Response(200, json=self.response())

        client = DeepSeekClient(model="test-model", sdk_client=self.sdk(handler))
        response = client.generate(
            [{"role": "user", "content": "Private answer: 1"}], self.params()
        )
        self.assertEqual(response["calls"][0]["arguments"], {"order": "AB"})
        self.assertEqual(response["usage"]["input_tokens"], 10)
        self.assertEqual(seen[0]["tools"][0]["name"], "submit_order")
        self.assertNotIn("parallel_tool_calls", seen[0])

    def test_http_failure_does_not_retry(self):
        import httpx
        from openai import InternalServerError

        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(500, json={"error": {"message": "remote-secret"}})

        client = DeepSeekClient(model="test-model", sdk_client=self.sdk(handler))
        with self.assertRaises(InternalServerError):
            client.generate([], self.params())
        self.assertEqual(len(seen), 1)

    def test_incomplete_response_preserves_usage(self):
        import httpx

        raw = self.response()
        raw["status"] = "incomplete"
        client = DeepSeekClient(
            model="test-model",
            sdk_client=self.sdk(lambda r: httpx.Response(200, json=raw)),
        )
        with self.assertRaises(InvalidDeepSeekResponse) as caught:
            client.generate([], self.params())
        self.assertEqual(caught.exception.response.usage.input_tokens, 10)

    def test_complete_runner_through_mocked_live_sdk(self):
        import httpx
        import tempfile
        from pathlib import Path
        from order_signal.run import PROJECT, run

        requests = []

        def handler(request):
            payload = json.loads(request.content)
            requests.append(payload)
            user = payload["input"][-1]["content"].splitlines()[-1]
            name = payload["tools"][0]["name"]
            if name == "submit_order":
                args = {"order": "AB" if user.endswith(": 1") else "BA"}
            else:
                args = {"choice": "1" if user == "Observed order: AB" else "2"}
            response = self.response()
            response["output"][0].update(name=name, arguments=json.dumps(args))
            return httpx.Response(200, json=response)

        cfg = json.loads((PROJECT / "configs/default.json").read_text())
        cfg.update(mode="deepseek", phase="pilot", rounds_per_condition=2)
        for agent in cfg["agents"]:
            agent["model"] = "test-model"
        cfg["budget"].update(
            prices_usd_per_million={"input": 1, "cached_input": 0, "output": 1},
            rates_checked_on="2026-10-24",
        )
        client = DeepSeekClient(model="test-model", sdk_client=self.sdk(handler))
        with tempfile.TemporaryDirectory() as temp:
            root = run(cfg, output_dir=Path(temp), client=client)
            self.assertEqual(
                json.loads((root / "status.json").read_text())["status"], "completed"
            )
            ledger = json.loads((root / "budget.json").read_text())
            self.assertAlmostEqual(ledger["accounted_cost_usd"], 16 * 15 / 1e6)
            self.assertEqual(ledger["pending_reservations_usd"], {})
        self.assertEqual(len(requests), 16)
        self.assertTrue(all(len(r["input"]) == 2 for r in requests))
