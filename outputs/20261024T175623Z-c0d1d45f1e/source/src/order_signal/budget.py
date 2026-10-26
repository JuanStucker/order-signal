"""Fail-closed request/cost accounting for the bounded DeepSeek pilot."""

from __future__ import annotations

import json
import math
from pathlib import Path

from order_signal.records import jsonable


class DollarRequestBudget:
    def __init__(self, limit, *, ceiling_usd, prices, path):
        if type(limit) is not int or limit <= 0:
            raise ValueError("Request limit must be a positive integer")
        if not math.isfinite(ceiling_usd) or ceiling_usd <= 0:
            raise ValueError("Dollar ceiling must be positive and finite")
        self.limit, self.ceiling = limit, ceiling_usd
        self.prices = dict(prices)
        for key in ("input", "cached_input", "output"):
            if not math.isfinite(self.prices[key]) or self.prices[key] < 0:
                raise ValueError("Prices must be finite and nonnegative")
        if self.prices["input"] < self.prices["cached_input"]:
            raise ValueError("Uncached price must bound cached price")
        self.path = Path(path)
        self.used = 0
        self.accounted = 0.0
        self.pending = {}
        self.responses = 0
        self.models = set()
        self.overrun = False
        self.blocked_reason = None
        self.save()

    def save(self):
        payload = {
            "ceiling_usd": self.ceiling,
            "max_requests": self.limit,
            "requests": self.used,
            "responses": self.responses,
            "accounted_cost_usd": self.accounted,
            "pending_reservations_usd": self.pending,
            "committed_cost_usd": self.accounted + sum(self.pending.values()),
            "prices_usd_per_million": self.prices,
            "response_models": sorted(self.models),
            "overrun": self.overrun,
            "blocked_reason": self.blocked_reason,
            "basis": "Configured peak rates, not invoice. Reserve serialized UTF-8 bytes + 2048 input framing tokens and full output cap; reconcile returned usage. Unknown charges retain reservations. SDK retries disabled.",
        }
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def reserve(self, input, params):
        if self.blocked_reason or self.overrun or self.used >= self.limit:
            raise RuntimeError("Request/cost limit reached; no further model call")
        cap = params.get("max_output_tokens", params.get("max_tokens"))
        if type(cap) is not int or cap <= 0:
            raise ValueError("A positive output cap is required")
        request_bytes = len(
            json.dumps(
                jsonable({"input": input, "params": params}), ensure_ascii=False
            ).encode("utf-8")
        )
        reservation = (
            (request_bytes + 2048) * self.prices["input"] + cap * self.prices["output"]
        ) / 1e6
        if self.accounted + sum(self.pending.values()) + reservation > self.ceiling:
            raise RuntimeError("Next request would exceed dollar ceiling")
        self.used += 1
        self.pending[str(self.used)] = reservation
        self.save()
        return self.used

    def settle(self, number, response):
        value = jsonable(response)
        model = value.get("model")
        valid_model = isinstance(model, str) and bool(model.strip())
        if valid_model:
            self.models.add(model)
        self.responses += 1
        usage = value.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        inp, out = usage.get("input_tokens"), usage.get("output_tokens")
        details = usage.get("input_tokens_details")
        cached = (details or {}).get("cached_tokens", 0) if details is None or isinstance(details, dict) else None
        valid = (
            all(type(n) is int and n >= 0 for n in (inp, out, cached)) and cached <= inp
        )
        if valid:
            cost = (
                (inp - cached) * self.prices["input"]
                + cached * self.prices["cached_input"]
                + out * self.prices["output"]
            ) / 1e6
            self.accounted += cost
            self.pending.pop(str(number))
        self.overrun = self.accounted + sum(self.pending.values()) > self.ceiling
        self.save()
        if not valid:
            self.blocked_reason = "invalid_usage"
            self.save()
            raise RuntimeError("Missing or invalid token usage; reservation retained")
        if self.overrun:
            raise RuntimeError("Returned usage exceeded cost ceiling; stopping")
        if not valid_model:
            self.blocked_reason = "missing_model_identity"
            self.save()
            raise RuntimeError("Missing returned model identifier; stopping")
        if len(self.models) > 1:
            self.blocked_reason = "model_changed"
            self.save()
            raise RuntimeError("Returned model identifier changed; stop pooling")
