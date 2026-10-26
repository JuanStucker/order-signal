"""Conservative sufficient sample sizes for the frozen joint evidence gates.

Uses Hoeffding concentration, not a normal approximation or an empirical power
estimate. Scenarios specify expected correct/wrong/pass probabilities per arm.
"""

import argparse
import json
import math
from pathlib import Path

from .analyze import FAMILY_SIZE, RANGES, WEIGHTS
from .versions import VERSIONS


def plan(scenario, *, power=0.8, level="stronger"):
    if not 0 < power < 1 or level not in ("basic", "stronger"):
        raise ValueError("invalid_power_or_evidence_level")
    if set(scenario) != {"C1", "C2", "C3", "C4"}:
        raise ValueError("scenario_requires_four_conditions")
    means = {}
    for cid, probabilities in scenario.items():
        if set(probabilities) != {"correct", "wrong", "pass"}:
            raise ValueError("scenario_requires_correct_wrong_pass_probabilities")
        if any(type(p) not in (int, float) or not math.isfinite(p) or p < 0 for p in probabilities.values()):
            raise ValueError("invalid_probability")
        if not math.isclose(sum(probabilities.values()), 1, abs_tol=1e-12, rel_tol=0):
            raise ValueError("probabilities_must_sum_to_one")
        means[cid] = {
            "pair_gain": 2 * probabilities["correct"] - 4 * probabilities["wrong"],
            "group_loss": probabilities["correct"],
        }
    gates = [
        ("positive_private_gain", "pair_gain", {"C3": 1}),
        ("private_channel_gain", "pair_gain", WEIGHTS["private_channel_C3_minus_C4"]),
    ]
    if level == "stronger":
        gates += [
            ("objective_interaction", "pair_gain", WEIGHTS["incentive_interaction"]),
            ("stipulated_loss_channel_effect", "group_loss", WEIGHTS["private_channel_C3_minus_C4"]),
            ("positive_stipulated_loss", "group_loss", {"C3": 1}),
        ]
    alpha = 0.05
    beta_gate = (1 - power) / len(gates)
    details = []
    for name, field, weights in gates:
        delta = sum(w * means[cid][field] for cid, w in weights.items())
        if delta <= 0:
            raise ValueError(f"scenario_does_not_satisfy_gate:{name}")
        width = RANGES[field][1] - RANGES[field][0]
        # Unclipped lower CI = estimate - a/sqrt(n). With probability at
        # least 1-beta_gate, estimate >= expectation - b/sqrt(n).
        a = width * sum(abs(w) for w in weights.values()) * math.sqrt(math.log(2 * FAMILY_SIZE / alpha) / 2)
        b = width * math.sqrt(sum(w * w for w in weights.values()) * math.log(1 / beta_gate) / 2)
        n = math.floor(((a + b) / delta) ** 2) + 1
        details.append({"gate": name, "expected_effect": delta, "sufficient_n_per_condition": n})
    n = max(g["sufficient_n_per_condition"] for g in details)
    return {
        **VERSIONS,
        "purpose": "Scenario-based planning, not a final-run authorization or observed power estimate",
        "scenario": scenario,
        "evidence_level": level,
        "target_joint_power": power,
        "alpha": alpha,
        "rounds_per_condition": n,
        "main_trials": 4 * n,
        "main_requests": 8 * n,
        "gates": details,
        "assumptions": "Independent trials with the specified fixed outcome probabilities; complete valid live run and passing input audit. Conservative sufficient bound using a union bound over gate failures; clipped intervals can require fewer trials. Does not include capability-control calls, failures, or cost. Choose substantively meaningful effects before final sampling; do not estimate them from selectively successful pilots.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--power", type=float, default=0.8)
    parser.add_argument("--level", choices=("basic", "stronger"), default="stronger")
    args = parser.parse_args()
    print(json.dumps(plan(json.loads(args.scenario.read_text()), power=args.power, level=args.level), indent=2))


if __name__ == "__main__":
    main()
