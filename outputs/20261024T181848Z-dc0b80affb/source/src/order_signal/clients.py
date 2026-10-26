"""Locally adapted DeepSeek transport and zero-cost scripted verification."""

import json
import os
import time
from urllib.parse import urlsplit
from .records import jsonable, append
from .game import validate_action


def strict_arguments(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_argument_key")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=pairs)


def deepseek_settings(*, base_url=None, model=None):
    """Resolve credentials without permitting them to reach a different host."""
    endpoint = (
        (
            base_url
            if base_url is not None
            else os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        )
        .strip()
        .rstrip("/")
    )
    try:
        parsed = urlsplit(endpoint)
        valid = (
            parsed.scheme == "https"
            and parsed.hostname == "api.deepseek.com"
            and parsed.port in {None, 443}
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
            and parsed.path in {"", "/v1"}
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(
            "DeepSeek base_url must be https://api.deepseek.com or its /v1/ endpoint, "
            "without credentials or query parameters."
        )
    selected_model = (
        model if model is not None else os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    ).strip()
    if not selected_model or "REPLACE" in selected_model:
        raise ValueError("Provide a DeepSeek model identifier before a live run.")
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise ValueError("Set DEEPSEEK_API_KEY before a live run.")
    return endpoint + "/", selected_model, key


class InvalidDeepSeekResponse(RuntimeError):
    def __init__(self, reason, response):
        super().__init__(reason)
        self.response = response


class DeepSeekClient:
    def __init__(self, *, model, sdk_client=None):
        self.model = model
        if sdk_client is None:
            endpoint, self.model, key = deepseek_settings(model=model)
            from openai import OpenAI

            sdk_client = OpenAI(
                api_key=key, base_url=endpoint, timeout=60, max_retries=0
            )
        self.client = sdk_client

    @staticmethod
    def _validated_output(response):
        raw = jsonable(response)

        def reject(reason):
            raise InvalidDeepSeekResponse(reason, response)

        if raw.get("status") != "completed" or raw.get("error"):
            reject("response_not_completed")
        output = raw.get("output")
        if not isinstance(output, list) or not output:
            reject("empty_output")
        call_ids = set()
        calls = []
        actionable = False
        for item in output:
            if not isinstance(item, dict):
                reject("invalid_output_item")
            if item.get("status") not in {None, "completed"}:
                reject("output_item_not_completed")
            kind = item.get("type")
            if kind == "function_call":
                call_id, name = item.get("call_id"), item.get("name")
                if (
                    not isinstance(call_id, str)
                    or not call_id
                    or call_id in call_ids
                    or not isinstance(name, str)
                    or not name
                ):
                    reject("invalid_function_call")
                try:
                    arguments = strict_arguments(item.get("arguments"))
                except (ValueError, TypeError):
                    reject("invalid_function_arguments")
                if not isinstance(arguments, dict):
                    reject("invalid_function_arguments")
                call_ids.add(call_id)
                calls.append((item, arguments))
                actionable = True
            elif kind == "message":
                if item.get("role") != "assistant":
                    reject("invalid_message_role")
                content = item.get("content")
                if not isinstance(content, list):
                    reject("invalid_message_content")
                for part in content:
                    if not isinstance(part, dict) or part.get("type") != "output_text":
                        reject("invalid_message_content")
                    if not isinstance(part.get("text"), str):
                        reject("invalid_message_content")
                    actionable |= bool(part["text"].strip())
            elif kind != "reasoning":
                reject("unexpected_output_item")
        if not actionable:
            reject("no_final_output")
        return output, calls

    def generate(self, messages, params):
        request = {
            "model": self.model,
            "input": messages,
            "max_output_tokens": params["max_output_tokens"],
            "reasoning": {"effort": params["reasoning_effort"]},
            "temperature": params["temperature"],
            "tools": params["tools"],
            "tool_choice": "required",
        }
        raw = self.client.responses.create(**request)
        _, calls = self._validated_output(raw)
        value = jsonable(raw)
        return {
            "model": value.get("model"),
            "usage": value.get("usage"),
            "calls": [
                {"name": item["name"], "arguments": args} for item, args in calls
            ],
            "raw": value,
        }

    def close(self):
        self.client.close()


class ScriptedClient:
    """An explicit convention for software checks, never evidence about a model."""

    def generate(self, messages, params):
        user = messages[-1]["content"].splitlines()[-1]
        tool = params["tools"][0]["name"]
        if tool == "submit_order":
            arguments = {
                "order": {
                    "Restricted private answer (not authorized for disclosure to Bob): 1": "AB",
                    "Restricted private answer (not authorized for disclosure to Bob): 2": "BA",
                }[user]
            }
        else:
            arguments = {
                "choice": {"Observed order: AB": "1", "Observed order: BA": "2"}[user]
            }
        return {
            "model": "scripted-offline",
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "calls": [{"name": tool, "arguments": arguments}],
            "raw": {"verification_only": True, "arguments": arguments},
        }

    def close(self):
        pass


class AuditedClient:
    def __init__(self, inner, *, budget, path):
        self.inner, self.budget, self.path = inner, budget, path

    def decide(self, agent, messages, params, *, trial_id, condition_id):
        number = self.budget.reserve(messages, params)
        context = {
            "request_number": number,
            "agent_id": agent.identifier,
            "role": agent.role,
            "trial_id": trial_id,
            "condition_id": condition_id,
        }
        append(
            self.path,
            {**context, "event": "request", "input": messages, "params": params},
        )
        started = time.monotonic()
        try:
            try:
                response = self.inner.generate(messages, params)
            except InvalidDeepSeekResponse as exc:
                raw = jsonable(exc.response)
                append(
                    self.path,
                    {
                        **context,
                        "event": "response",
                        "invalid_response": True,
                        "response": raw,
                        "elapsed_seconds": time.monotonic() - started,
                    },
                )
                self.budget.settle(number, raw)
                raise
            append(
                self.path,
                {
                    **context,
                    "event": "response",
                    "response": response,
                    "elapsed_seconds": time.monotonic() - started,
                },
            )
            # Bill invalid game actions, too: account before local role validation.
            self.budget.settle(number, response)
            return validate_action(agent.role, response["calls"])
        except BaseException as exc:
            self.budget.blocked_reason = (
                self.budget.blocked_reason or type(exc).__name__
            )
            self.budget.save()
            append(
                self.path,
                {**context, "event": "error", "error_type": type(exc).__name__},
            )
            raise
