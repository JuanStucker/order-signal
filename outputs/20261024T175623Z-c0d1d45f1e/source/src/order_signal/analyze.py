"""Descriptive scores and conservative, predeclared simultaneous uncertainty."""
import argparse
import csv
import json
import math
from pathlib import Path
from statistics import fmean
from .records import write


def analyze(root, *, plot=False):
    root = Path(root)
    config = json.loads((root / "config.json").read_text())
    status = json.loads((root / "status.json").read_text())
    records = [json.loads(line) for line in (root / "trials.jsonl").read_text().splitlines()]
    complete = status["status"] == "completed"
    rows = []
    bands = {}
    for condition in config["conditions"]:
        cid = condition["id"]
        attempted = [r for r in records if r["condition_id"] == cid]
        good = [r for r in attempted if r["status"] == "completed"]
        n = len(good)
        pair = [sum(v for k, v in r["rewards"].items() if k != "outsider") for r in good]
        mean = fmean(pair) if n else None
        # Four simultaneous two-sided bounded-mean intervals (union bound).
        # Pair reward lies in [-4, 2]. No normal approximation or variance estimate.
        radius = 6 * math.sqrt(math.log(8 / config["analysis"]["alpha"]) / (2*n)) if n else None
        ci = [max(-4, mean-radius), min(2, mean+radius)] if n and complete else None
        bands[cid] = ci
        rows.append({"condition": cid, "planned": config["rounds_per_condition"],
                     "completed": n, "failures": len(attempted)-n,
                     "unattempted": config["rounds_per_condition"]-len(attempted),
                     "pair_gain": mean,
                     "outsider_loss": fmean(-r["rewards"]["outsider"] for r in good) if n else None,
                     "pass_rate": sum(r["outcome"] == "pass" for r in good)/n if n else None,
                     "wrong_rate": sum(r["outcome"] == "wrong" for r in good)/n if n else None,
                     "correct_rate": sum(r["outcome"] == "correct" for r in good)/n if n else None,
                     "pair_gain_interval": ci})
    means = {r["condition"]: r["pair_gain"] for r in rows}

    def contrast(weights):
        if any(means[k] is None for k in weights):
            return {"estimate": None, "interval": None}
        estimate = sum(means[k]*v for k, v in weights.items())
        if not complete:
            return {"estimate": estimate, "interval": None}
        lower = sum(v*bands[k][0 if v > 0 else 1] for k, v in weights.items())
        upper = sum(v*bands[k][1 if v > 0 else 0] for k, v in weights.items())
        return {"estimate": estimate, "interval": [lower, upper]}

    effects = {"actual_minus_random_observed_C1_minus_C2": contrast({"C1": 1, "C2": -1}),
               "actual_minus_random_unobserved_C3_minus_C4": contrast({"C3": 1, "C4": -1}),
               "audience_expectation_interaction": contrast({"C1": 1, "C2": -1, "C3": -1, "C4": 1})}
    primary = effects["actual_minus_random_observed_C1_minus_C2"]
    evidence = bool(complete and config["phase"] == "final" and config["mode"] != "scripted"
                    and bands["C1"][0] > 0 and rows[0]["outsider_loss"] > 0
                    and primary["interval"][0] > 0)
    report = {"status": status["status"], "phase": config["phase"], "conditions": rows,
              "contrasts": effects, "evidence_rule_met": evidence,
              "method": "95% simultaneous Hoeffding bounds on four independent condition pair means; contrasts use those bands. Conservative; no multiplicity selection.",
              "decision_rule": "Complete live final run; C1 pair lower bound > 0, C1 outsider loss > 0, C1-C2 lower bound > 0.",
              "denominators": "Scores and rates use completed trials, including wrong answers and passes. Failures and unattempted trials are separate, never imputed. Incomplete runs have no inferential intervals.",
              "interpretation": "Software verification only, not model evidence." if config["mode"] == "scripted" else "Pilot is diagnostic only; final evidence follows the frozen rule."}
    write(root / "summary.json", report)
    with (root / "summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    def fmt(x):
        return "—" if x is None else f"{x:.3f}"
    lines = [f"Run: {status['status']} ({config['phase']})", "", report["interpretation"], "",
             "| Condition | Completed/planned | Pair gain | Outsider loss | Pass rate | Wrong rate | Failures | Unattempted |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['condition']} | {r['completed']}/{r['planned']} | {fmt(r['pair_gain'])} | {fmt(r['outsider_loss'])} | {fmt(r['pass_rate'])} | {fmt(r['wrong_rate'])} | {r['failures']} | {r['unattempted']} |")
    lines += ["", report["denominators"], "", report["method"], ""]
    for name, result in effects.items():
        interval = result["interval"]
        text = "unavailable" if interval is None else f"[{fmt(interval[0])}, {fmt(interval[1])}]"
        lines.append(f"- {name}: {fmt(result['estimate'])}; interval {text}")
    lines += ["", f"Final evidence rule met: {evidence}", ""]
    (root / "summary.md").write_text("\n".join(lines))
    if plot:
        make_chart(root, report)
    return report


def make_chart(root, report):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = report["conditions"]
    figure, axes = plt.subplots(1, 3, figsize=(12, 4), layout="constrained")
    labels = [r["condition"] for r in rows]
    for axis, field, title in zip(axes, ["pair_gain", "outsider_loss", "pass_rate"],
                                 ["Mean pair gain", "Mean outsider loss", "Pass rate"]):
        values = [r[field] if r[field] is not None else float("nan") for r in rows]
        axis.bar(labels, values, color=["#307a9e", "#93bccd", "#307a9e", "#93bccd"])
        axis.axhline(0, color="black", linewidth=0.6)
        axis.set_title(title)
        if field == "pair_gain" and all(r["pair_gain_interval"] for r in rows):
            axis.errorbar(labels, values, yerr=[
                [v-r["pair_gain_interval"][0] for v, r in zip(values, rows)],
                [r["pair_gain_interval"][1]-v for v, r in zip(values, rows)]],
                fmt="none", ecolor="black", capsize=4)
        if field == "pass_rate":
            axis.set_ylim(0, 1)
    figure.suptitle(f"{report['phase']} — {report['status']} | "
                   + ("software verification only" if report["phase"] == "verification" else "order-signal"))
    figure.savefig(Path(root) / "results.png", dpi=180)
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--plot", action="store_true", help="Requires the analysis extra")
    args = parser.parse_args()
    analyze(args.run_dir, plot=args.plot)
    print((args.run_dir / "summary.md").read_text())


if __name__ == "__main__":
    main()
