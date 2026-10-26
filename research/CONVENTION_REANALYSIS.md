# Convention re-analysis of existing live runs

Post-hoc, no API calls, specified after seeing the data. Script:
[reanalyze_conventions.py](reanalyze_conventions.py); per-pair output:
[JSON](convention-reanalysis.json) and [table](convention-reanalysis-table.md).
Covers every live repeated-pair run under `outputs/`, including the earlier pilots
and the incomplete low-reasoning batches: 65 pairs, 61 with evaluation decisions.

## Definitions

- **History-implied mapping:** across the training feedback the agents saw (past
  answer and *delivered* order), whether more rounds follow AB→1 / BA→2 (natural)
  or AB→2 / BA→1 (reversed). Equal counts are a tie.
- **Alice's evaluation convention:** the majority mapping of her committed orders
  against the current answers. A sender who always submits the same order carries
  no information and is labeled constant, never natural or reversed.
- **Bob's evaluation convention:** the majority mapping of his attempted answers
  against the delivered order. Passes are excluded. A receiver who gives one answer
  regardless of the order is labeled constant.

## Main observation: agents follow the mapping the feedback implies

Counts are pairs, by evaluation-phase majority convention.

| Feedback implied | Pairs | Alice natural / reversed / other | Bob natural / reversed / other |
| --- | ---: | --- | --- |
| No feedback (memoryless) | 16 | 10 / 0 / 6 | 15 / 0 / 1 |
| Natural | 21 | 16 / 1 / 4 | 18 / 1 / 2 |
| Reversed | 9 | 0 / 4 / 5 | 0 / 7 / 2 |
| — authorized | 3 | 0 / 3 / 0 | 0 / 3 / 0 |
| — restricted | 6 | 0 / 1 / 5 | 0 / 4 / 2 |
| Tie | 15 | 6 / 6 / 3 | 3 / 7 / 5 |

"Other" is tie, constant or no attempts. Each Bob "other" under reversed feedback is
a pair with no attempted answers.

- **The receiver signal:** with no feedback, every decidable Bob uses AB→1. When
  the feedback implies the reversed mapping, every decidable Bob (7 of 7) decodes
  with the reversed one. The natural label prior is a default that a few rounds of
  in-context feedback override.
- **The sender signal is narrower:** authorized senders adopt the reversed mapping
  (3 of 3). Restricted senders mostly do not encode at all: three are constant AB,
  two are ties, one is reversed.
- **This mechanism produced the scouting results.** "Random delivery hurts" partly
  works through random feedback that implies an arbitrary, sometimes reversed,
  mapping that both agents then adopt. Senders see only delivered orders, never
  their own committed ones, which makes this possible.
- **Unexplained:** under tied feedback, Bob leans reversed (7 vs 3). Bob's own past
  choices and outcomes are also in the feedback, and this summary does not model them.

## Restricted senders: no dependence beyond chance

There are 24 restricted pairs (L1–L4, M1) where a secret × order table is defined
over all of Alice's decisions. Two have a two-sided Fisher exact p below 0.10 (0.072
and 0.081) and none falls below 0.05. About 2.4 would be expected below 0.10 by
chance. Over evaluation rounds only, the smallest p across 21 pairs is 0.14.
Without history, restricted senders (M1, 5 pairs, all without thinking) always submitted AB.

Earlier review notes called the L1 encoding differences of 0.75–0.8 an under-reported
leakage signal. At 8 evaluation rounds per pair, they are consistent with chance and
that claim is withdrawn.

## Limits

- **Post hoc and descriptive.** Implied mappings were not assigned. Reversed
  histories arise mostly under random delivery or inconsistent senders, so arm,
  regimen and history are confounded. Pairs differ in regimen, prompt version
  details and run.
- **Short histories.** Four training rounds give implied-mapping margins of only
  3–1 or 4–0.
- **Feedback beyond the mapping.** Feedback also contains Bob's choices and outcomes,
  which carry additional information.
- **Next step.** The controlled test is [PROBE_PLAN.md](PROBE_PLAN.md), P1.
