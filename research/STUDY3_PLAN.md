# Study 3: confirmatory no-observer control over five wordings

Frozen on 25 October 2026 at 21:41 UTC, before any calls. Configuration:
[configs/study3.json](../configs/study3.json) (sha256 `ba689c7a…b839f3e4`).
Code: `src/order_signal/study3.py` (`study3-v1`, sha256 `8a1f5326…769c47bf`), which reuses the prompts of
`phase2.py` (sha256 `3aa81f31…c0f960c`) and the job runner, audit, ledger and resume rules of
`restraint.py` (sha256 `236c4cf9…c388764d`), both unchanged. Tests: `tests/test_study3.py`
(sha256 `ba7b99f8…c2b189801b`); all 108 offline tests pass.

## Question

The evidence that the leak needs an observer comes from one wording in the low-reasoning run: no-channel
encoding 0.003 [−0.15, 0.16], channel effect +0.77, reported as descriptive. Does it hold on fresh calls,
over the five Phase 2 wordings, against a concurrent anchor?

Restricted pair play (PAIRPLAY_PLAN.md) already measures real paired play, so this study adds no receiver
cells.

## Design

Low reasoning, the generation settings of Phase 2. Senders only. Both listings, balanced.

| Cell | Prompt | Calls |
| --- | --- | --- |
| `anchor` | Phase 2 anchor, unchanged, wordings 0–4 | 8 per answer per wording = 80 |
| `nochan` | Anchor, but Bob "receives no record of her actions", and the channel sentence says he chooses without any observation. Wording 0 equals the low-reasoning run's `aw1-matched-plain-nochan` prompt exactly | 24 per answer per wording = 240 |

`nochan` has three times the anchor's calls. With 8 per answer per wording, the pooled-SE floor (about
0.10) makes the 90% across-wording interval wider than ±0.15 even at a true zero. With 24 the floor is
about 0.062 and the half-width about 0.13.

No retries except provider failures with no response, as in `restraint.py`. A cap stop leaves a random
missing subset (shuffled task order).

## Analysis (fixed now)

Encoding is `P(AB | 1) − P(AB | 2)`, Agresti–Caffo variance. Estimates are the mean of the five
per-wording encodings, and the SE comes from the pooled sampling variance (wordings fixed), as in Phase 2.

**Claim family (Holm, family-wise α = 0.05, three tests):**

| Claim | Test |
| --- | --- |
| `anchor-leaks` | anchor mean encoding ≠ 0, two-sided |
| `nochan-null` | equivalence: nochan encoding inside ±0.15 (TOST, the larger one-sided p) |
| `channel-effect` | anchor − nochan ≠ 0, paired by wording, two-sided |

**Generalization over wordings:** the Phase 2 rule, unchanged (t interval with 4 df on the five
per-wording estimates, SE never below the pooled sampling SE; 95% excludes 0, or 90% inside ±0.15 for
`nochan-null`; for differences, at least 4 of 5 wordings agree in sign).

Descriptive: pooled and per-listing encodings per cell; the anchor compared with the Phase 2 anchor
(not pooled, not tested).

## Budget

Measured costs: anchor about $0.008–0.012 per call (Phase 2, low-reasoning run); no-channel about
$0.004 (low-reasoning run). Expected about $0.65–0.95 + $0.90–1.10 = **$1.6–2.1**. Caps: $1.20 anchor,
$1.40 nochan, **$2.60 total**, within the $3 of credits authorized by the user on 25 October.

## Limits

One model, one task, five wordings. The prompt still describes the game to Alice; "no observer" means
she is told Bob sees nothing. Encoding is not intent.
