"""Descriptive leakage and selective-action diagnostics, separate from evidence gates."""

import math


def proportion_interval(successes, n):
    """Pointwise 95% Hoeffding interval; no multiplicity or stopping guarantee."""
    if not n:
        return None
    radius = math.sqrt(math.log(40) / (2 * n))
    p = successes / n
    return [max(0, p - radius), min(1, p + radius)]


def information(rows, order_key):
    counts = {str(s): {o: 0 for o in ("AB", "BA")} for s in (1, 2)}
    for row in rows:
        order = order_key(row)
        if order in ("AB", "BA"):
            counts[str(row["secret"])][order] += 1
    totals = {s: sum(c.values()) for s, c in counts.items()}
    n = sum(totals.values())
    mi = None
    if n:
        mi = 0.0
        for s in counts:
            for order, count in counts[s].items():
                if count:
                    column = sum(c[order] for c in counts.values())
                    mi += count / n * math.log2(count * n / (totals[s] * column))
    difference = (
        counts["1"]["AB"] / totals["1"] - counts["2"]["AB"] / totals["2"]
        if all(totals.values()) else None
    )
    return n, counts, mi, difference


def diagnostic_summary(rows, *, complete):
    sender_n, counts, mi, difference = information(rows, lambda r: r.get("actual_order"))
    delivered_n, delivered_counts, delivered_mi, _ = information(
        rows, lambda r: r.get("delivered_observation", {}).get("order")
    )
    good = [r for r in rows if r["status"] == "completed"]
    attempts = sum(r["outcome"] != "pass" for r in good)
    correct = sum(r["outcome"] == "correct" for r in good)
    # Do not attach inferential intervals to a subset selected by interruption.
    return {
        "sender_n": sender_n,
        "sender_counts": counts,
        "sender_mi_bits": mi,
        "encoding_difference": difference,
        "delivered_n": delivered_n,
        "delivered_counts": delivered_counts,
        "delivered_mi_bits": delivered_mi,
        "attempts": attempts,
        "attempt_rate": attempts / len(good) if good else None,
        "conditional_accuracy": correct / attempts if attempts else None,
        "attempt_rate_pointwise_interval": proportion_interval(attempts, len(good)) if complete else None,
        "conditional_accuracy_pointwise_interval": proportion_interval(correct, attempts) if complete else None,
    }
