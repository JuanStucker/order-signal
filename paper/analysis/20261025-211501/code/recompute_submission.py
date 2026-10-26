"""Freeze local evidence and recompute submission results, without model calls.

Run: paper/.venv/bin/python paper/recompute_submission.py
Recompute a frozen snapshot: add --snapshot paper/analysis/<timestamp>
Existing experiment directories and summaries are never changed.
"""
import argparse
import csv
import hashlib
import importlib.util
import itertools
import json
import math
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from scipy.stats import fisher_exact

PAPER = Path(__file__).resolve().parent
PROJECT = PAPER.parent / "order_signal"
OUTPUTS = PROJECT / "outputs"


def read(path):
    return json.loads(path.read_text())


def rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def snapshot():
    now = datetime.now(ZoneInfo("Europe/Berlin"))
    target = PAPER / "analysis" / now.strftime("%Y%m%d-%H%M%S")
    target.mkdir(parents=True, exist_ok=False)
    manifest = {"capture_started": now.isoformat(), "files": [], "runs": []}

    def copy(src, dest):
        data = src.read_bytes()
        omitted = False
        if src.suffix == ".jsonl":
            lines = data.splitlines(keepends=True)
            for i, line in enumerate(lines):
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    if i == len(lines) - 1 and not line.endswith(b"\n"):
                        data = b"".join(lines[:-1])
                        omitted = True
                    else:
                        raise
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        manifest["files"].append({"source": str(src.relative_to(PAPER.parent)),
                                  "snapshot": str(dest.relative_to(target)),
                                  "sha256": hashlib.sha256(data).hexdigest(),
                                  "bytes": len(data), "partial_line_omitted": omitted})

    for run in sorted(OUTPUTS.iterdir()):
        if not run.is_dir() or not (run / "plan.json").exists():
            continue
        plan = read(run / "plan.json")
        if plan.get("version") not in {"restraint-probes-v1", "screen-v1", "phase2-v1", "single-decision-probes-v1"}:
            continue
        if read(run / "config.json").get("mode") != "deepseek":
            continue
        manifest["runs"].append(run.name)
        for src in sorted(run.rglob("*")):
            if src.is_file() and src.suffix in {".json", ".jsonl"}:
                copy(src, target / "raw" / run.name / src.relative_to(run))
    # Preserve repeated-pair evidence used for the observed positive control.
    for src in sorted(OUTPUTS.rglob("trials.jsonl")):
        records = rows(src)
        cfg = src.parent / "config.json"
        if (records and records[0].get("version") == "repeated-pair-pilot-v1"
                and cfg.exists() and read(cfg)["base"]["mode"] == "deepseek"):
            copy(src, target / "pairs" / src.relative_to(OUTPUTS))
            copy(cfg, target / "pairs" / cfg.relative_to(OUTPUTS))
    for src in sorted((PROJECT / "src" / "order_signal").glob("*.py")):
        copy(src, target / "code" / "order_signal" / src.name)
    for src in sorted((PROJECT / "research").glob("*PLAN.md")):
        copy(src, target / "plans" / src.name)
    copy(PROJECT / "research" / "reanalyze_conventions.py", target / "code" / "reanalyze_conventions.py")
    copy(Path(__file__), target / "code" / Path(__file__).name)
    manifest["capture_finished"] = datetime.now(ZoneInfo("Europe/Berlin")).isoformat()
    save(target / "manifest.json", manifest)
    return target, manifest


def independent_encoding(records):
    table = [[sum(r["current"] == s and r["value"] == o for r in records)
              for o in ("AB", "BA")] for s in (1, 2)]
    n = [sum(row) for row in table]
    if min(n) == 0:
        return None
    point = table[0][0] / n[0] - table[1][0] / n[1]
    adjusted = [(table[i][0] + 1) / (n[i] + 2) for i in range(2)]
    var = sum(adjusted[i] * (1 - adjusted[i]) / (n[i] + 2) for i in range(2))
    return dict(table=table, difference=point, variance=var,
                ci95=[point - 1.96 * math.sqrt(var), point + 1.96 * math.sqrt(var)],
                fisher_p=float(fisher_exact(table).pvalue))


def independent_gain(alice, bob, draws=20000):
    a = np.array([[sum(r["current"] == s and r["value"] == o for r in alice)
                   for o in ("AB", "BA")] for s in (1, 2)])
    b = np.array([[sum(r["current"] == o and r["value"] == c for r in bob)
                   for c in ("1", "2", "pass")] for o in ("AB", "BA")])
    def calc(pa, pb):
        correct = .5 * (pa[..., 0, 0] * pb[..., 0, 0] + pa[..., 0, 1] * pb[..., 1, 0]
                        + pa[..., 1, 0] * pb[..., 0, 1] + pa[..., 1, 1] * pb[..., 1, 1])
        wrong = .5 * (pa[..., 0, 0] * pb[..., 0, 1] + pa[..., 0, 1] * pb[..., 1, 1]
                      + pa[..., 1, 0] * pb[..., 0, 0] + pa[..., 1, 1] * pb[..., 1, 0])
        return 2 * (correct - 2 * wrong)
    pa, pb = a / a.sum(axis=1)[:, None], b / b.sum(axis=1)[:, None]
    rng = np.random.default_rng(20261025)
    aa = np.stack([rng.multinomial(int(n), p, draws) / n for n, p in zip(a.sum(axis=1), pa)], axis=1)
    bb = np.stack([rng.multinomial(int(n), p, draws) / n for n, p in zip(b.sum(axis=1), pb)], axis=1)
    return {"point": float(calc(pa, pb)), "independent_bootstrap_ci95": np.quantile(calc(aa, bb), [.025, .975]).tolist(),
            "replicates": draws, "seed": 20261025}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path)
    args = parser.parse_args()
    if args.snapshot:
        target = args.snapshot.resolve()
        manifest = read(target / 'manifest.json')
    else:
        target, manifest = snapshot()
    sys.path.insert(0, str(target / "code"))
    from order_signal import restraint as rs, screen, phase2, probes
    reports, inventory, cell_table, checks = {}, [], [], []
    for name in manifest["runs"]:
        root = target / "raw" / name
        plan, cfg = read(root / "plan.json"), read(root / "config.json")
        for job in plan["jobs"]:
            records = rows(root / job["id"] / "results.jsonl")
            assert len({r["task_id"] for r in records}) == len(records), (name, job["id"], "duplicate")
            tasks = {t["task_id"]: t for t in job["tasks"]}
            for r in records:
                task = tasks[r["task_id"]]
                for key in ("current", "cell", "presentation", "wording", "template"):
                    if key in r and key in task:
                        assert r[key] == task[key], (name, job["id"], key)
            if job["tasks"][0]["role"] == "sender":
                cells = sorted({r.get("cell", job.get("cell", "all")) for r in records})
                for cell in cells:
                    subset = [r for r in records if r.get("cell", job.get("cell", "all")) == cell]
                    e = independent_encoding(subset)
                    if e:
                        ref = rs.encoding(rs.sender_table(subset))
                        assert math.isclose(e["difference"], ref["difference"], abs_tol=1e-12)
                        assert math.isclose(e["variance"], ref["variance"], abs_tol=1e-12)
                        if ref["fisher_p"] is not None:
                            assert math.isclose(e["fisher_p"], ref["fisher_p"], abs_tol=1e-10)
                        cell_table.append({"run": name, "job": job["id"], "cell": cell,
                                           "n": len(subset), "planned_job": len(job["tasks"]),
                                           "regimen": job["regimen"], **e})
            status_file = root / job["id"] / "status.json"
            status = read(status_file) if status_file.exists() else None
            inventory.append({"run": name, "job": job["id"], "observed": len(records),
                              "planned": len(job["tasks"]), "seed": job["seed"],
                              "missing_by_rule": len(status.get("abandoned", [])) if status else 0,
                              "finished": bool(status and rs.resolved(status)),
                              "audit": rs.audit(job, root / job["id"], cfg) if plan["version"] != "single-decision-probes-v1" else None})
        all_status = all((root / j["id"] / "status.json").exists() for j in plan["jobs"])
        if plan["version"] == "restraint-probes-v1":
            reports[name] = rs.summarize(root)
        elif plan["version"] == "screen-v1":
            reports[name] = screen.summarize(root)
        elif plan["version"] == "single-decision-probes-v1":
            reports[name] = probes.summarize(root)
        elif plan["version"] == "phase2-v1":
            entries = [x for x in inventory if x["run"] == name]
            # Never run the seven-claim family on a subset of finished cells.
            complete = all(x["finished"] and x["audit"] for x in entries)
            if all_status and complete:
                reports[name] = phase2.summarize(root)
            else:
                reports[name] = {"complete": False, "observed": sum(x["observed"] for x in entries),
                                 "planned": sum(x["planned"] for x in entries),
                                 "note": "Ongoing snapshot. Descriptive counts only; no claims or stopping decision.",
                                 "jobs": entries}
        if plan["version"] == "restraint-probes-v1" and "111159" in name:
            for label, sender, receiver in [("matched", "d-low-aw1-matched-plain", "r-low-matched-restricted"),
                                             ("v3", "d-low-aw0-v3-rlabel", "r-low-v3")]:
                a, b = rows(root / sender / "results.jsonl"), rows(root / receiver / "results.jsonl")
                g = independent_gain(a, b)
                reference = reports[name]["analysis"]["low"]["end_to_end"]["matched-restricted" if label == "matched" else "v3"]
                assert math.isclose(g["point"], reference["point"]["pair_gain"], abs_tol=1e-12)
                checks.append({"kind": "independent_expected_gain", "run": name, "pairing": label, **g})
            # Enumerate all two-order assignments for the six missing sender decisions.
            jobs = [j for j in plan["jobs"] if j["study"] == "decomposition"]
            scenarios = []
            for assignments in itertools.product(("AB", "BA"), repeat=len(jobs)):
                enc = {}
                for job, value in zip(jobs, assignments):
                    rr = rows(root / job["id"] / "results.jsonl")
                    absent = read(root / job["id"] / "status.json")["abandoned"]
                    assert len(absent) == 1
                    t = next(t for t in job["tasks"] if t["task_id"] == absent[0])
                    enc[job["cell"]] = rs.encoding(rs.sender_table(rr + [{"current": t["current"], "value": value}]))
                fx = rs.frame_label_effects(enc)["frame_matched"]
                scenarios.append({"frame_effect": fx["estimate"], "frame_lower_ci": fx["ci"][0],
                                  "matched_encoding": enc["aw1-matched-plain"]["difference"],
                                  "v3_encoding": enc["aw0-v3-rlabel"]["difference"]})
            checks.append({"kind": "missing_sender_sensitivity", "assignments": len(scenarios),
                           **{key: [min(s[key] for s in scenarios), max(s[key] for s in scenarios)] for key in scenarios[0]}})

    spec = importlib.util.spec_from_file_location("conventions", target / "code" / "reanalyze_conventions.py")
    conventions = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conventions)
    pair_analysis = conventions.analyze(target / "pairs")
    save(target / "conventions.json", pair_analysis)
    positive = []
    for path in sorted((target / "pairs").rglob("trials.jsonl")):
        if not any(name in str(path) for name in ("213450Z-scout", "213909Z-scout")):
            continue
        cfg = read(path.parent / "config.json")
        records = [r for r in rows(path) if r["status"] == "completed" and r["phase"] == "evaluation"]
        if not records or cfg["base"]["generation"]["reasoning_effort"] != "low":
            continue
        if records[0]["condition_id"] in ("A1", "M2"):
            counts = Counter(r["outcome"] for r in records)
            positive.append({"source": str(path.relative_to(target)), "arm": records[0]["condition_id"],
                             "seeds": cfg["base"].get("seeds"), "n": len(records), "counts": dict(counts),
                             "pair_gain": (2*counts["correct"] - 4*counts["wrong"])/len(records)})
    result = {"capture_started": manifest["capture_started"], "capture_finished": manifest["capture_finished"],
              "runs": reports, "inventory": inventory, "sender_cells": cell_table,
              "independent_checks": checks, "observed_positive_control": positive}
    save(target / "recomputed.json", result)
    with (target / "sender_cells.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=cell_table[0].keys())
        writer.writeheader()
        writer.writerows(cell_table)
    with (target / "run_inventory.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=inventory[0].keys())
        writer.writeheader()
        writer.writerows(inventory)
    (PAPER / "analysis" / "LATEST.txt").write_text(str(target) + "\n")
    print(json.dumps({"output": str(target), "captured": manifest["capture_finished"],
                      "runs": {k: {"complete": v["complete"], "observed": sum(x["observed"] for x in inventory if x["run"] == k),
                                   "planned": sum(x["planned"] for x in inventory if x["run"] == k)} for k, v in reports.items()},
                      "independent_checks": checks, "positive_control_pairs": positive}, indent=2))


if __name__ == "__main__":
    main()
