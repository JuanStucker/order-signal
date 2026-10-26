"""Budgeted independent-pair screening; descriptive selection data, never final data."""

import argparse
import copy
import json
import random
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean

from .diagnostics import diagnostic_summary
from .game import checklist_valid, metrics, score, validate_action
from .learning import audit, run, selected_arms
from .records import provenance, write
from .run import PROJECT, validate


CONTRASTS = {
    "authorized_history": {"A1": 1, "M2": -1},
    "authorized_channel": {"A1": 1, "A2": -1},
    "restricted_history": {"L3": 1, "M1": -1},
    "restricted_individual_channel": {"L3": 1, "L4": -1},
    "restricted_group_channel": {"L1": 1, "L2": -1},
    "objective_channel_interaction": {"L3": 1, "L4": -1, "L1": -1, "L2": 1},
    "authorization_bundle": {"A1": 1, "L3": -1},
}


def jobs(config):
    validate(config["base"])
    if config["base"]["phase"] != "pilot" and config["base"]["mode"] != "scripted":
        raise ValueError("scouting_is_pilot_only")
    arms = selected_arms(config)
    if any(type(config[k]) is not int or config[k] < 1
           for k in ("pairs", "training_rounds", "evaluation_rounds")):
        raise ValueError("invalid_round_count")
    total = config["pairs"] * len(arms)
    requests = 2 * (config["training_rounds"] + config["evaluation_rounds"])
    if total * requests > config["base"]["budget"]["max_requests"]:
        raise ValueError("insufficient_request_budget")
    result = []
    for rep in range(1, config["pairs"] + 1):
        for arm in arms:
            cfg = copy.deepcopy(config)
            cfg.update(pairs=1, arm_ids=[arm["id"]])
            cfg["base"]["seeds"] = {
                key: value + 1009 * rep for key, value in config["base"]["seeds"].items()
            }
            cfg["base"]["budget"]["ceiling_usd"] /= total
            cfg["base"]["budget"]["max_requests"] = requests
            result.append(dict(replication=rep, arm=arm["id"], config=cfg))
    random.Random(config["base"]["seeds"]["schedule"]).shuffle(result)
    return result


def action_audit(config, records, calls):
    """Independently link returned actions to execution, payoffs and outcomes."""
    responses = {(c["trial_id"], c["role"]): c for c in calls if c["event"] == "response"}
    try:
        for row in records:
            if row["status"] != "completed":
                continue
            sender = responses[(row["trial_id"], "sender")]["response"]
            receiver = responses[(row["trial_id"], "receiver")]["response"]
            if validate_action("sender", sender["calls"]) != row["actual_order"]:
                return False
            if validate_action("receiver", receiver["calls"]) != row["choice"]:
                return False
            if not checklist_valid(row):
                return False
            rewards = score(row["secret"], row["choice"], *[a["id"] for a in config["base"]["agents"]])
            outcome = "pass" if row["choice"] == "pass" else (
                "correct" if row["choice"] == str(row["secret"]) else "wrong")
            if row["rewards"] != rewards or row["metrics"] != metrics(rewards) or row["outcome"] != outcome:
                return False
    except (KeyError, TypeError, ValueError):
        return False
    return True


def summarize(root):
    config = json.loads((root / "config.json").read_text())
    manifest = json.loads((root / "runs.json").read_text())
    rows, models = [], set()
    totals = dict(requests=0, completed_trials=0, failed_trials=0, unattempted_trials=0,
                  accounted_cost_usd=0., committed_cost_usd=0.)
    for job in manifest:
        path = root / job["path"]
        cfg = json.loads((path / "config.json").read_text())
        status = json.loads((path / "status.json").read_text())
        ledger = json.loads((path / "budget.json").read_text())
        records = [json.loads(s) for s in (path / "trials.jsonl").read_text().splitlines()]
        calls = [json.loads(s) for s in (path / "calls.jsonl").read_text().splitlines()]
        models.update(ledger["response_models"])
        for k in ("requests", "completed_trials", "failed_trials", "unattempted_trials"):
            totals[k] += status[k]
        for k in ("accounted_cost_usd", "committed_cost_usd"):
            totals[k] += ledger[k]
        ev_all = [r for r in records if r["phase"] == "evaluation"]
        ev = [r for r in ev_all if r["status"] == "completed"]
        counts = {k: sum(r["outcome"] == k for r in ev) for k in ("correct", "wrong", "pass")}
        boundary = audit(cfg, records, calls)
        actions = action_audit(cfg, records, calls)
        rows.append(dict(
            replication=job["replication"], arm=job["arm"], path=job["path"],
            status=status["status"], error_type=status.get("error_type"),
            input_audit=boundary, action_audit=actions, eval_n=len(ev),
            planned_eval=config["evaluation_rounds"], **counts,
            accuracy=counts["correct"] / len(ev) if ev else None,
            pass_rate=counts["pass"] / len(ev) if ev else None,
            pair_gain=fmean(r["metrics"]["pair_gain"] for r in ev) if ev else None,
            diagnostics=diagnostic_summary(ev_all, complete=False),
            committed_cost_usd=ledger["committed_cost_usd"],
        ))
    contrasts = {}
    for name, weights in CONTRASTS.items():
        if not set(weights) <= {a["id"] for a in selected_arms(config)}:
            continue
        differences = []
        for rep in range(1, config["pairs"] + 1):
            selected = {r["arm"]: r for r in rows if r["replication"] == rep and r["arm"] in weights}
            if len(selected) == len(weights) and all(
                    r["status"] == "completed" and r["input_audit"] and r["action_audit"]
                    for r in selected.values()):
                differences.append(dict(replication=rep, **{
                    metric: sum(weights[a] * selected[a][metric] for a in weights)
                    for metric in ("accuracy", "pass_rate", "pair_gain")}))
        complete = len(differences) == config["pairs"] and len(models) == 1
        contrasts[name] = dict(complete_pairs=len(differences), pair_differences=differences,
                              means={k: fmean(d[k] for d in differences) if complete else None
                                     for k in ("accuracy", "pass_rate", "pair_gain")})
    report = dict(
        **totals, pairs=sorted(rows, key=lambda r: (r["replication"], r["arm"])),
        model_identities=sorted(models), contrasts=contrasts,
        complete=all(r["status"] == "completed" and r["input_audit"] and r["action_audit"] for r in rows)
                 and len(models) == 1,
        interpretation="Exploratory selection only. Pair is the replication unit. No confidence bands from repeated rounds or tiny-pair percentile bootstrap. Complete-case overall contrasts withheld on any required failure. Authorization contrast also changes awareness and framing. Inference settings compare full generation regimens, including tool choice."
    )
    write(root / "summary.json", report)
    return report


def execute(config, output_dir=None, workers=8):
    tasks = jobs(config)
    root = Path(output_dir or PROJECT / "outputs") / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-scout-" + uuid.uuid4().hex[:8])
    root.mkdir(parents=True, mode=0o700)
    write(root / "config.json", config)
    write(root / "jobs.json", tasks)
    provenance(root, PROJECT)
    write(root / "status.json", dict(status="running", jobs=len(tasks)))
    print(f"SCOUT_ROOT={root}", flush=True)

    def one(job):
        path = run(job["config"], output_dir=root / f"pair-{job['replication']:02d}-{job['arm']}")
        return dict(replication=job["replication"], arm=job["arm"], path=str(path.relative_to(root)))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, tasks))
    write(root / "runs.json", results)
    report = summarize(root)
    write(root / "status.json", dict(status="completed" if report["complete"] else "incomplete"))
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--summarize", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.summarize:
        print(json.dumps(summarize(args.summarize), indent=2))
    else:
        root = execute(json.loads(args.config.read_text()), workers=args.workers)
        print(root)
        report = json.loads((root / "summary.json").read_text())
        print(json.dumps({k: v for k, v in report.items() if k != "pairs"}, indent=2))
        if not report["complete"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
