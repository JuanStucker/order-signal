"""Render a reproducible, read-only snapshot of finished and ongoing results.

Run: python3 research/plot_simple_results.py
Re-render: python3 research/plot_simple_results.py --snapshot <snapshot.json>
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BLUE, ORANGE, INK, GRAY = "#247b91", "#d17a22", "#203044", "#a6afbb"
BG = "#fafbfD"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.spines.left": False, "axes.spines.bottom": False,
                     "text.color": INK, "axes.labelcolor": INK,
                     "xtick.color": INK, "ytick.color": INK,
                     "figure.facecolor": BG, "axes.facecolor": BG,
                     "pdf.fonttype": 42, "svg.fonttype": "none"})


def read_json(path):
    return json.loads(path.read_text())


def snapshot():
    started = datetime.now(ZoneInfo("Europe/Berlin"))
    ids = {"replicate": "20261025T104037Z-restraint-ff769c53",
           "earlier": "20261024T222603Z-restraint-71e0e24f",
           "live": "20261025T111159Z-restraint-40002da8"}
    data = {"capture_started": started.isoformat(), "sources": ids}
    for key in ("replicate", "earlier"):
        data[key] = read_json(ROOT / "outputs" / ids[key] / "summary.json")
    live = ROOT / "outputs" / ids["live"]
    data["live_jobs"] = []
    for config in read_json(live / "config.json")["jobs"]:
        path = live / config["id"] / "results.jsonl"
        rows = []
        # A concurrently appended final line may not be complete yet.
        lines = path.read_bytes().splitlines(keepends=True)
        for i, line in enumerate(lines):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                if i == len(lines) - 1 and not line.endswith(b"\n"):
                    continue
                raise
            rows.append(row)
        assert len({r["task_id"] for r in rows}) == len(rows), "Duplicate task"
        data["live_jobs"].append({"config": config, "rows": rows})
    data["capture_finished"] = datetime.now(ZoneInfo("Europe/Berlin")).isoformat()
    return data


def base(title, subtitle, height=9):
    fig, axes = plt.subplots(2, 1, figsize=(12, height))
    fig.subplots_adjust(left=.32, right=.86, top=.79, bottom=.22, hspace=.95)
    fig.text(.055, .955, title, fontsize=23, weight="bold", va="top")
    fig.text(.055, .905, subtitle, fontsize=11, va="top", linespacing=1.6)
    return fig, axes


def style(ax, labels, xlim, xlabel):
    ax.set_yticks(range(len(labels)), labels)
    ax.set_ylim(len(labels) - .5, -.5)
    ax.set_xlim(*xlim)
    ax.set_xlabel(xlabel, labelpad=9)
    ax.tick_params(axis="y", length=0, pad=12)
    ax.grid(axis="x", alpha=.13)
    ax.set_axisbelow(True)
    ax.axvline(0, color=GRAY, linewidth=1)


def dot(ax, i, value, color, ci=None, hollow=False):
    if ci is not None:
        ax.plot(ci, [i, i], color=color, lw=3, solid_capstyle="round")
    ax.scatter([value], [i], s=80, color=BG if hollow else color,
               edgecolor=color, linewidth=2, zorder=3)


def finished(data):
    fig, (a, b) = base("What the earlier studies show",
        "One model • one synthetic task • separate studies, not pooled\n"
        "Blue: completed samples. Orange: small, incomplete reasoning samples.", 10)
    a.set_title("1   Which prompt changes increase encoding?", loc="left", pad=18, weight="bold")
    labels = ["Tell Alice that Bob knows\nshe holds the answer", "Use the shorter\nconfidentiality framing", "Use a plain answer label\ninstead of a restricted label"]
    style(a, labels, (-.18, .32), "Change in encoding difference   |   right = more encoding")
    effects = data["replicate"]["analysis"]["none"]["primary_main_effects"]
    for i, key in enumerate(["awareness", "frame_matched", "label_plain"]):
        e = effects[key]
        dot(a, i, e["estimate"], BLUE, e["ci"])
        a.text(1.025, i, f'{e["estimate"]:+.3f}', transform=a.get_yaxis_transform(), va="center", weight="bold")
    a.text(0, -.40, "1,600 no-thinking calls. Lines: adjusted 95% confidence intervals.", transform=a.transAxes, fontsize=10)
    b.set_title("2   Can the pair earn points from the signal?", loc="left", pad=18, weight="bold")
    labels = ["No thinking • original restriction", "No thinking • shorter restriction", "No thinking • authorized", "Low reasoning • shorter restriction*", "Low reasoning • authorized*"]
    style(b, labels, (-1.25, 2.15), "Estimated combined points per round   |   right of zero = profit")
    for i, (reg, key) in enumerate([("none", "v3"), ("none", "matched-restricted"),
                                   ("none", "matched-authorized"), ("low", "matched-restricted"),
                                   ("low", "matched-authorized")]):
        e = data["earlier"]["analysis"][reg]["end_to_end"][key]
        # No inferential intervals for incomplete samples.
        dot(b, i, e["point"]["pair_gain"], BLUE if reg == "none" else ORANGE,
            e["ci95"]["pair_gain"] if reg == "none" else None, reg == "low")
        b.text(1.025, i, f'{e["point"]["pair_gain"]:+.2f}', transform=b.get_yaxis_transform(), va="center", weight="bold")
    fig.text(.055, .065, "Pair scores combine separately sampled sender and receiver policies; they are not observed pair play.\n"
             "Lines in panel 2: 95% bootstrap intervals. *Only 9 restricted and 7 authorized receiver calls; descriptive points only.\n"
             "Source: complete factorial replicate and earlier restraint study, 25 October 2026.", fontsize=10, linespacing=1.6)
    return fig


def feedback(data):
    jobs = {j["id"]: j for j in data["earlier"]["jobs"]}
    fig, (a, b) = base("Past examples change the convention",
        "Completed feedback probes • restricted agents • no thinking\n"
        "Each row uses 24 decisions across 12 synthetic history templates.")
    keys = ["natural", "reversed", "empty"]
    labels = ["Examples teach AB → 1", "Examples teach AB → 2", "No examples"]
    a.set_title("1   Alice changes how she encodes the answer", loc="left", pad=18, weight="bold")
    style(a, labels, (-1.05, 1.05), "Encoding difference   |   −1 = reversed, 0 = none, +1 = natural")
    cells = jobs["f-none-restricted-sender"]["summary"]["cells"]
    for i, k in enumerate(keys):
        v = cells[k]["encoding"]["difference"]
        a.barh(i, v, color=BLUE, height=.45)
        a.text(1.025, i, f"{v:+.2f}", transform=a.get_yaxis_transform(), va="center", weight="bold")
    b.set_title("2   Bob follows examples, but often passes", loc="left", pad=18, weight="bold")
    style(b, labels, (0, 24), "Number of decisions")
    cells = jobs["f-none-restricted-receiver"]["summary"]["cells"]
    left = np.zeros(3)
    for key, label, color in [("natural", "Uses AB → 1", BLUE), ("reversed", "Uses AB → 2", ORANGE), ("passes", "Passes", GRAY)]:
        values = np.array([cells[k][key] for k in keys])
        b.barh(range(3), values, left=left, height=.5, color=color, label=label)
        for i, v in enumerate(values):
            if v:
                b.text(left[i] + v / 2, i, str(v), ha="center", va="center", color="white", weight="bold", fontsize=10)
        left += values
    handles, labels = b.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower left", bbox_to_anchor=(.32, .105), ncol=3, frameon=False, fontsize=10)
    b.set_xticks([0, 6, 12, 18, 24])
    fig.text(.055, .045, "The histories were supplied by the researcher. These are descriptive plots of synthetic-feedback probes.\n"
             "They do not show that agents developed a convention through independent interaction. Source: earlier restraint study.", fontsize=10, linespacing=1.6)
    return fig


def live(data):
    jobs = data["live_jobs"]
    total = sum(len(j["rows"]) for j in jobs)
    stamp = datetime.fromisoformat(data["capture_finished"]).strftime("%d %b %Y, %H:%M:%S %Z")
    fig, (a, b) = base("Running study: preliminary snapshot",
        f"{stamp} • {total} / 480 planned decisions recorded • low reasoning\n"
        "Orange values can change as more calls finish. This image does not update automatically.", 11)
    fig.subplots_adjust(hspace=.8, bottom=.25)
    names = ["Original frame + restricted label", "Original frame + plain label", "Shorter frame + restricted label",
             "Shorter frame + plain label", "Shorter frame + plain label\n+ awareness sentence", "Same prompt, but no observer"]
    a.set_title("1   Does Alice’s action order reveal the answer?", loc="left", pad=18, weight="bold")
    style(a, names, (-1.05, 1.05), "Encoding difference   |   −1 = reversed, 0 = none, +1 = natural")
    a.set_xticks([-1, -.5, 0, .5, 1])
    exported = []
    senders = [j for j in jobs if j["config"]["study"] == "decomposition"]
    for i, job in enumerate(senders):
        rows = job["rows"]
        by_answer = [[r for r in rows if r["current"] == s] for s in (1, 2)]
        n1, n2 = map(len, by_answer)
        v = (sum(r["value"] == "AB" for r in by_answer[0]) / n1 -
             sum(r["value"] == "AB" for r in by_answer[1]) / n2) if n1 and n2 else None
        if v is not None:
            a.barh(i, v, color=ORANGE, alpha=.8, height=.48)
        a.text(1.025, i, (f"{v:+.2f}" if v is not None else "N/A") + f"   {len(rows)}/64\nanswers 1 / 2: {n1} / {n2}",
               transform=a.get_yaxis_transform(), va="center", fontsize=9)
        presentations = {p: sum(r["presentation"] == p for r in rows) for p in ["natural-first", "reversed-first"]}
        exported.append({"cell": job["config"]["cell"], "n": len(rows), "n_answer_1": n1,
                         "n_answer_2": n2, "encoding_difference": v, "presentation_counts": presentations})
    b.set_title("2   What does Bob choose after each order?", loc="left", pad=18, weight="bold")
    receiver_rows, labels = [], []
    for job in [j for j in jobs if j["config"]["study"] == "receiver"]:
        label = "Original restriction" if job["config"]["cell"] == "v3" else "Shorter restriction"
        for order in ("AB", "BA"):
            receiver_rows.append([r for r in job["rows"] if r["current"] == order])
            labels.append(f"{label} • sees {order}")
    style(b, labels, (0, 100), "Share of completed receiver decisions (%)")
    left = np.zeros(4)
    for key, label, color in [("1", "Answers 1", BLUE), ("2", "Answers 2", ORANGE), ("pass", "Passes", GRAY)]:
        counts = [sum(str(r["value"]) == key for r in rows) for rows in receiver_rows]
        values = np.array([100 * c / len(rows) if rows else 0 for c, rows in zip(counts, receiver_rows)])
        b.barh(range(4), values, left=left, height=.55, color=color, label=label)
        for i, (value, count) in enumerate(zip(values, counts)):
            if count and value > 6:
                b.text(left[i] + value / 2, i, str(count), ha="center", va="center", color="white", weight="bold", fontsize=10)
        left += values
    for i, rows in enumerate(receiver_rows):
        b.text(1.025, i, f"{len(rows)}/24", transform=b.get_yaxis_transform(), va="center", fontsize=10)
    handles, legend_labels = b.get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="lower left", bbox_to_anchor=(.32, .155), ncol=3, frameon=False, fontsize=10)
    fig.text(.055, .075, "Counts inside receiver bars are decisions, not percentages. Right-hand counts show progress toward the plan.\n"
             "Incomplete samples: no confidence intervals or final claims. Answer and presentation groups are still unbalanced.\n"
             "Sender encoding is not receiver accuracy. Receiver choices alone do not establish profitable communication.\n"
             "Read directly from result logs; earlier saved run summaries may be stale. Timeouts remain missing.", fontsize=10, linespacing=1.6)
    return fig, {"completed_decisions": total, "planned_decisions": 480, "senders": exported}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args()
    if args.snapshot:
        data = read_json(args.snapshot)
        out = args.snapshot.parent
    else:
        data = snapshot()
        stamp = datetime.fromisoformat(data["capture_finished"]).strftime("%Y%m%d-%H%M%S")
        out = ROOT / "research" / "results_graphs" / stamp
        out.mkdir(parents=True, exist_ok=False)
        (out / "snapshot.json").write_text(json.dumps(data, indent=2) + "\n")
    live_fig, live_stats = live(data)
    figures = [("earlier_results", finished(data)), ("feedback_results", feedback(data)), ("running_results", live_fig)]
    with PdfPages(out / "experiment_results.pdf") as pdf:
        for name, fig in figures:
            fig.savefig(out / f"{name}.png", dpi=170)
            fig.savefig(out / f"{name}.svg")
            pdf.savefig(fig)
            plt.close(fig)
    (out / "live_statistics.json").write_text(json.dumps(live_stats, indent=2) + "\n")
    (out / "NOTES.txt").write_text(
        "Order Signal result charts\n\n"
        "All data are from local experiment artifacts; no model calls were made.\n"
        f"Snapshot capture: {data['capture_started']} to {data['capture_finished']}\n"
        "Raw log files were read sequentially during this capture window.\n"
        "The ongoing study is shown descriptively without inferential intervals.\n"
        "Earlier incomplete low-reasoning cells are also shown without intervals.\n"
        "Independent runs and inference settings are not pooled.\n"
        "The stored snapshot preserves every plotted value and the raw ongoing decisions.\n"
        "Re-render this snapshot with: python3 research/plot_simple_results.py --snapshot <snapshot.json>\n"
        "Capture a fresh snapshot with: python3 research/plot_simple_results.py\n")
    print(json.dumps({"output_directory": str(out), "snapshot_time": data["capture_finished"], **live_stats}, indent=2))


if __name__ == "__main__":
    main()
