# Phase 2 Block B: repeated restricted pair play plan

Frozen on 25 October 2026, before any calls. Configuration:
[configs/pairplay.json](../configs/pairplay.json) (sha256 `ff461df2…affa00ddfc`).
Code: `src/order_signal/pairplay.py` (`pairplay-v1`, sha256 `250577cc…5d272513`), with prompts from
`phase2.py` (sha256 `3aa81f31…c0f960c`, unchanged since the Phase 2 run). Tests:
`tests/test_pairplay.py`; all 94 offline tests pass.

## Arm 3 gate (decided before this plan)

The [Phase 2 plan](PHASE2_PLAN.md) ran the explicit-rule arm only if, in the low-reasoning feedback
probe, the explicit prompt's `natural − reversed` mean direction was ≥ 0.40. The result was **+0.17**
(sign-flip p = 0.69, 6 templates). For comparison, the anchor reached +1.83 (p = 0.031). **Arm 3 is
dropped.** In single calls, the explicit rule holds against a history in which breaking it paid off.

## Question

The leak has only been measured in single calls, and Bob's profit has only been computed by combining
separate sender and receiver calls. Does a restricted pair that actually plays together, with shared
feedback after every round, turn the leak into profit for Bob? Does Alice keep encoding when the feedback
does not reward it?

## Design

Low reasoning, the generation settings of Phase 2. Prompts: Phase 2 anchor (wording 0) with the
repeated-pair memory framing. Bob gets the same rule text with his role line. After each round both
agents see the past answer, Bob's delivered order, his choice and the outcome (`learning.feedback`,
unchanged).

| Arm | Delivery |
| --- | --- |
| `matched-actual` | Bob sees the order Alice chose |
| `matched-shuffled` | Bob sees an independent random order (seeded per pair) |

- 8 pairs × 5 rounds × 2 arms = 80 rounds, 160 calls.
- Each pair shares its answer schedule across arms.
- Odd pairs list symbols natural-first and even pairs reversed-first, for both agents and their tools.
- No retries or replacement pairs. A pair stops at its first failure, including a cap stop, and is
  reported as incomplete.

## Analysis (fixed now)

Pairs are the unit; the rounds within a pair are dependent.

- **Primary:** mean pair gain per round, `matched-actual − matched-shuffled`, paired by pair, with an
  exact two-sided sign-flip p over the 8 pairs (smallest possible p = 0.008). It is reported only if
  all 8 pairs are complete in both arms. Otherwise each pair's difference is reported, without a p.
- **Secondary (descriptive):** Bob's accuracy and pass rate. Alice's natural-direction rate overall
  and in the late rounds (4–5), actual minus shuffled. Encoding pooled per arm.
- A positive primary contrast means Bob profits from the order Alice actually chose. It does not
  separate Alice's encoding from Bob's decoding; the secondary metrics describe each side.

## Budget

| | |
| --- | --- |
| Expected | about $0.022 per round (anchor sender with history $0.0055, as measured in Phase 2; receiver $0.0165): about **$1.8** |
| Caps | $0.20 per pair, $3.20 in total, which is all of the remaining $10 authorization |

Each call reserves about $0.068 (the full output cap) before it is sent. A pair can therefore complete
5 rounds at up to about $0.015 per call. The worst case uses the whole remaining budget; the expected
reserve afterwards is about $1.4.

## Limits

- One model and one prompt family; 5 rounds is a short horizon.
- 8 pairs detect only effects that are consistent across pairs.
- Encoding is not intent, agreement or harm; harm is defined by the payoff rule.
