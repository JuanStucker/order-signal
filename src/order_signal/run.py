"""Sequential runner with independent random streams and fail-closed execution."""

import argparse
import copy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import uuid

from dotenv import load_dotenv

from . import prompts
from .budget import DollarRequestBudget
from .clients import AuditedClient, DeepSeekClient, ScriptedClient
from .protocol import Agent, play
from .records import append, provenance, write
from .versions import VERSIONS, require_versions

PROJECT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT / ".env")
CONDITIONS = [
    {"id": "C1", "objective": "group", "delivery": "actual"},
    {"id": "C2", "objective": "group", "delivery": "random"},
    {"id": "C3", "objective": "individual", "delivery": "actual"},
    {"id": "C4", "objective": "individual", "delivery": "random"},
]

CAPABILITY_CONDITIONS = [
    {"id": "K1", "objective": "individual", "delivery": "actual"},
    {"id": "K2", "objective": "individual", "delivery": "random"},
]


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("unsupported_or_missing_configuration_fields")


def positive_int(value):
    return type(value) is int and value > 0


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate(config):
    exact(
        config,
        [
            "mode",
            "phase",
            "study",
            *VERSIONS,
            "rounds_per_condition",
            "conditions",
            "agents",
            "seeds",
            "generation",
            "budget",
            "analysis",
        ],
    )
    if config["mode"] not in ("scripted", "deepseek"):
        raise ValueError("unsupported_provider")
    if config["phase"] not in ("verification", "pilot", "final"):
        raise ValueError("unsupported_phase")
    if (config["mode"] == "scripted") != (config["phase"] == "verification"):
        raise ValueError("scripted_runs_are_verification_only")
    require_versions(config)
    if not positive_int(config["rounds_per_condition"]):
        raise ValueError("invalid_round_count")
    if config["study"] not in ("main", "capability"):
        raise ValueError("unsupported_study")
    expected_conditions = CONDITIONS if config["study"] == "main" else CAPABILITY_CONDITIONS
    if config["conditions"] != expected_conditions:
        raise ValueError("unsupported_study_conditions")
    if config["study"] == "capability" and config["phase"] == "final":
        raise ValueError("capability_control_is_diagnostic_only")
    agents = config["agents"]
    if not isinstance(agents, list) or len(agents) != 2:
        raise ValueError("exactly_two_agents_required")
    for agent, role, display in zip(agents, ("sender", "receiver"), ("Alice", "Bob")):
        exact(agent, ["id", "role", "display_name", "model"])
        if agent["role"] != role or agent["display_name"] != display:
            raise ValueError("unsupported_role_assignment")
        if (
            not isinstance(agent["id"], str)
            or not agent["id"].isidentifier()
            or agent["id"] == "outsider"
        ):
            raise ValueError("invalid_agent_identifier")
        if not isinstance(agent["model"], str) or not agent["model"].strip():
            raise ValueError("invalid_model")
    if agents[0]["id"] == agents[1]["id"]:
        raise ValueError("duplicate_agent_identifier")
    if agents[0]["model"] != agents[1]["model"]:
        raise ValueError("mixed_models_require_per_model_accounting")
    if config["mode"] == "scripted" and agents[0]["model"] != "scripted-offline":
        raise ValueError("scripted_model_required")
    exact(config["seeds"], ["schedule", "secrets", "channel"])
    if any(type(v) is not int for v in config["seeds"].values()):
        raise ValueError("integer_seeds_required")
    generation = config["generation"]
    exact(generation, ["max_output_tokens", "temperature", "reasoning_effort"])
    if not positive_int(generation["max_output_tokens"]):
        raise ValueError("invalid_output_cap")
    if not finite(generation["temperature"]) or not 0 <= generation["temperature"] <= 2:
        raise ValueError("invalid_temperature")
    if generation["reasoning_effort"] not in ("none", "low"):
        raise ValueError("unsupported_reasoning_effort")
    budget = config["budget"]
    exact(
        budget,
        ["max_requests", "ceiling_usd", "prices_usd_per_million", "rates_checked_on"],
    )
    if not positive_int(budget["max_requests"]):
        raise ValueError("invalid_request_limit")
    if not finite(budget["ceiling_usd"]) or budget["ceiling_usd"] <= 0:
        raise ValueError("invalid_spending_limit")
    prices = budget["prices_usd_per_million"]
    exact(prices, ["input", "cached_input", "output"])
    if (
        any(not finite(v) or v < 0 for v in prices.values())
        or prices["cached_input"] > prices["input"]
    ):
        raise ValueError("invalid_prices")
    if config["mode"] == "scripted":
        if any(prices.values()) or budget["rates_checked_on"] is not None:
            raise ValueError("scripted_usage_must_be_explicitly_zero_cost")
    else:
        if prices["input"] <= 0 or prices["output"] <= 0:
            raise ValueError("live_runs_require_explicit_positive_rates")
        try:
            datetime.strptime(budget["rates_checked_on"], "%Y-%m-%d")
        except (ValueError, TypeError):
            raise ValueError("record_verified_provider_rate_date") from None
    if config["analysis"] != {"method": "hoeffding_simultaneous", "alpha": 0.05}:
        raise ValueError("unsupported_analysis_method")
    return copy.deepcopy(config)


def schedule(config):
    conditions = config["conditions"] * config["rounds_per_condition"]
    random.Random(config["seeds"]["schedule"]).shuffle(conditions)
    secrets = random.Random(config["seeds"]["secrets"])
    return [
        {
            **VERSIONS,
            "trial_id": f"trial-{i + 1:05d}",
            "condition_id": c["id"],
            "secret": secrets.choice((1, 2)),
        }
        for i, c in enumerate(conditions)
    ]


def run(config, *, output_dir=None, client=None):
    config = validate(config)
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:10]
    )
    root = Path(output_dir or PROJECT / "outputs") / run_id
    root.mkdir(parents=True, mode=0o700)
    write(root / "config.json", config)
    write(root / "prompts.json", prompts.snapshot())
    provenance(root, PROJECT)
    trials = schedule(config)
    write(root / "schedule.json", trials)
    (root / "trials.jsonl").touch()
    (root / "calls.jsonl").touch()
    status = {
        **VERSIONS,
        "run_id": run_id,
        "status": "running",
        "phase": config["phase"],
        "planned_trials": len(trials),
        "completed_trials": 0,
        "failed_trials": 0,
    }
    write(root / "status.json", status)
    b = config["budget"]
    budget = DollarRequestBudget(
        b["max_requests"],
        ceiling_usd=b["ceiling_usd"],
        prices=b["prices_usd_per_million"],
        path=root / "budget.json",
    )
    agents = [Agent(a["id"], a["role"], a["display_name"]) for a in config["agents"]]
    rng = random.Random(config["seeds"]["channel"])
    inner = client
    active = None
    try:
        if inner is None:
            inner = (
                ScriptedClient()
                if config["mode"] == "scripted"
                else DeepSeekClient(model=config["agents"][0]["model"])
            )
        audited = AuditedClient(inner, budget=budget, path=root / "calls.jsonl")
        for trial in trials:
            active = {**trial, "status": "started"}
            before = budget.used

            def decide(agent, observation):
                params = {**config["generation"], "tools": [prompts.tool(agent.role)]}
                return audited.decide(
                    agent,
                    prompts.build(observation, study=config["study"]),
                    params,
                    trial_id=trial["trial_id"],
                    condition_id=trial["condition_id"],
                )

            condition = next(c for c in config["conditions"] if c["id"] == trial["condition_id"])
            play(
                secret=trial["secret"],
                condition=condition,
                agents=agents,
                rng=rng,
                decide=decide,
                record=active,
            )
            if budget.used - before != 2:
                raise RuntimeError("protocol_requires_two_calls")
            active["requests"] = budget.used - before
            append(root / "trials.jsonl", active)
            active = None
            status["completed_trials"] += 1
            write(root / "status.json", status)
        status["status"] = "completed"
    except BaseException as exc:
        status["status"] = "incomplete"
        status["error_type"] = type(exc).__name__
        if active is not None:
            active.update(
                status="failed",
                error_type=type(exc).__name__,
                requests=budget.used - before,
            )
            # A failed trial has no imputed choice or score.
            active.pop("rewards", None)
            active.pop("metrics", None)
            append(root / "trials.jsonl", active)
            status["failed_trials"] += 1
        if not isinstance(exc, (Exception, KeyboardInterrupt)):
            raise
    finally:
        status["requests"] = budget.used
        status["unattempted_trials"] = (
            len(trials) - status["completed_trials"] - status["failed_trials"]
        )
        write(root / "status.json", status)
        if client is None and inner is not None:
            inner.close()
        from .analyze import analyze

        analyze(root)
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT / "configs/default.json")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    root = run(json.loads(args.config.read_text()), output_dir=args.output_dir)
    print(root)
    print((root / "summary.md").read_text())
    if json.loads((root / "status.json").read_text())["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
