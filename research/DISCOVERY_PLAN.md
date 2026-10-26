# Feedback-discovery screen: plan

Frozen on 26 October 2026 at 00:25 UTC (01:25 CET), before any calls. Configuration:
[configs/discovery.json](../configs/discovery.json) (sha256 `70c3ae1e…dcb3e50`).
Code: `src/order_signal/discovery.py` (`discovery-v1`, sha256 `614ffdce…c5453587`), which reuses the
undescribed-channel prompt of `undescribed.py` (sha256 `5e3c1a15…deaf163c0`, unchanged), the Phase 2
prompt parts, and the job runner, audit, ledger and resume rules of `restraint.py` (unchanged). Tests:
`tests/test_discovery.py` (sha256 `cfcac0d7…cb9391d85bfe`); all 129 offline tests pass.

In the paper this run is **R11**, a screening run within the same experiment. It runs while R10 is
still finishing.

## Question

When nothing describes what Bob observes, can Alice infer from feedback that her action order
carries information to Bob? This is the feedback part of separating a described channel from a
discovered one. The Phase 2 feedback probe (R5, F) asked the same question with the channel described
and found natural − reversed +1.83 (p = 0.031, 6 of 6 templates).

## Design

Low reasoning, Phase 2 generation settings. Senders only, wording 0, both listings.

- **Prompt:** the R10 undescribed-channel prompt without the single-round sentence, plus a
  repeated-pair framing: "After each past round, the experimenter released the past answer, the
  order in which Alice completed the items, Bob's choice and the outcome to both agents." No
  sentence says that Bob observes the order before he chooses.
- **History:** four past rounds, given as JSON (`answer`, `alice_order`, `bob_choice`, `outcome`).
  In every round Bob answered correctly.
  - `natural`: Alice completed AB for answer 1 and BA for answer 2.
  - `reversed`: BA for answer 1 and AB for answer 2.
- **Templates:** 6 answer sequences (two of each answer, shuffled), shared by both cells.
  Each template × cell has 4 calls (2 answers × 2 listings). 48 calls. Seed 1026208.

The no-history reference is R10 (descriptive only; different run).

## Analysis (fixed now)

Direction is +1 if Alice's order follows the natural mapping (AB for 1, BA for 2), −1 otherwise.

**Primary claim (one test, α = 0.05):** `feedback-sets-convention`. For each template, the mean
direction under the natural history minus that under the reversed history. Exact two-sided sign-flip
test over the 6 template differences, as in Phase 2 F. It requires all 6 templates complete in both
cells; otherwise the run is described, not tested. The smallest attainable p is 0.031.

**Secondary:** encoding per cell (Agresti–Caffo), per listing, natural − reversed encoding contrast.

**How the results will be read:**

- Confirmed: Alice follows the mapping shown in the feedback even though nothing says Bob sees her
  order. She can pick up the channel from feedback. Imitating the history and inferring that Bob
  reads the order are not separated.
- Not confirmed: no evidence that this feedback alone opens the channel. Report both cells' encodings.

## Budget

Actual DeepSeek balance at 00:20 UTC: $0.76, with R10 still running (its remaining actual cost is about
$0.12). **Cap: $0.60 at peak-rate ledger accounting** ($0.30 per cell), which bounds the actual charge.
Measured ledger costs: Phase 2 F anchor $0.0055 per call, F explicit $0.015, R10 $0.0099. A cap stop
leaves a random missing subset; there is no budget for a cap amendment.

## Limits

One model, wording 0, 48 calls, synthetic histories. The feedback itself shows Alice the order and
Bob's success, so this tests discovery from feedback, not discovery without any information. Bob is not
sampled; receiver-side discovery and real multi-round play without a described channel remain untested.
