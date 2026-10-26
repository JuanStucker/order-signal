# Current status of claims (25 October 2026)

This page is the single source for what the project currently claims. Earlier
documents keep their original text, with update notes pointing here.

## Question

Which confidentiality specifications leave a task-equivalent action-order side
channel open? Does a restricted sender use that channel, and can a receiver
exploit it profitably? The setting is a single synthetic game with one model
(`deepseek-v4-pro`). The payoff rule defines harm; harm is not measured
independently.

## Claims the data support

| Claim | Evidence | Strength |
| --- | --- | --- |
| Without thinking, telling the agents that Bob knows Alice holds the answer has no material effect on restricted encoding. This does **not** hold with reasoning (see below). | [Restraint replicate](RESTRAINT_RESULTS.md): awareness +0.002 [−0.105, 0.110], inside the prespecified ±0.15 margin | Primary, prespecified |
| Without thinking, the v3 framing and the restriction label each suppress encoding. Encoding appears only when both are removed. | Frame +0.15 [0.05, 0.26], label +0.12 [0.02, 0.23] | Primary, prespecified |
| The "do not use" clause is not what produces restraint. | +0.015 [−0.09, 0.12] | Secondary |
| No-thinking sender results depend strongly on how the symbols are listed. | The matched encoding is 0.44–0.50 with natural-first listing and −0.08 to 0.18 with reversed listing; there is a first-option default | Prespecified diagnostic, both runs |
| Encoding depends on someone observing the order (signalling, not association). | No-channel cells: −0.03 (no thinking) and 0.00 (low reasoning) | Secondary (no thinking); descriptive (low reasoning) |
| **With low reasoning, a restricted sender leaks through the order.** Combined with a receiver who applies the natural mapping, the expected pair gain is positive. | [Low-reasoning run](RESTRAINT_LOW_RESULTS.md): 24 October matched restricted 0.78 [0.61, 0.94]; expected pair gain +0.74 [0.46, 1.07] | Exploratory, 32 per answer, prespecified analysis |
| The receiver decodes only when a signal is plausible. Told that Alice does not know the answer, Bob passes 27 of 32 times. The pair-gain gap between prompts comes from the senders. | [Phase 1](PHASE1_RESULTS.md) uninformed receiver; v3 receiver 15/0/8 and 0/13/11 | Screening |
| **The vague rule ("not authorized to disclose") leaks in every wording tested.** | [Phase 2](PHASE2_RESULTS.md): +0.85 [0.73, 0.97]; per wording 0.62–1.00 | **Confirmed** (Holm), generalizes over 5 wordings |
| **Forbidding indirect disclosure cuts the leak to near zero, whether or not the rule names the channel.** Explicit ("order must not depend on the answer") +0.03 [−0.08, 0.13]; general ("must not convey it by any means") +0.10 [−0.04, 0.24]. | Phase 2: −0.83 and −0.75 against the anchor; general minus explicit +0.075 [−0.12, 0.27] | **Confirmed** (Holm), generalizes. The ±0.15 equivalence test for explicit narrowly misses (p = 0.030 against 0.025), so say "near zero", not "equivalent to zero" |
| **The leak is driven by Alice's own payoff.** | Phase 2 no-stake 0.18, −0.68 against the anchor; no-harm 0.75 in Phase 1 (removing a −3 harm barely matters) | **Confirmed** (Holm), generalizes. [Block C](PAYOFF_RESULTS.md) screen: when passing pays more than any correct answer, encoding falls to −0.06 (−1.00 vs a same-run anchor of 0.94). Harm ×10 gives 0.62, −0.31 [−0.63, 0.005], inconclusive |
| The leak does not need Bob's observation to be described as ordered. | Phase 2 unflagged ("activity log") 0.57; −0.28 against the anchor | Confirmed difference; does not generalize over wordings |
| **Under the vague rule, a history of successful decoding fully sets Alice's convention; under the explicit rule it does not reopen the channel.** | Phase 2 F, low reasoning: anchor natural − reversed +1.83 (6/6 templates, p = 0.031); explicit +0.17 (p = 0.69) | Exploratory, synthetic histories |
| **In real repeated play, the leak pays off for the pair.** | [Pair play](PHASE2_RESULTS.md): real delivery +1.00 pair gain per round (accuracy 0.70) against −0.08 shuffled; 7 of 8 pairs positive, 1 tie | Descriptive: the primary test is withheld because 3 shuffled pair-runs timed out, all in the shuffled arm |
| The v3 leak is aimed at Bob. | v3 with no channel 0.06 | Screening |
| With low reasoning, the realistic v3 restriction leaks little, and not profitably. | Phase 2 v3 0.10 [−0.02, 0.22], not confirmed (p = 0.16); earlier 0.22 [0.03, 0.40]; pair gain −0.24 [−0.60, 0.10] | Not confirmed in Phase 2 |
| **With low reasoning, the leak needs an observer.** | No-channel 0.003 [−0.15, 0.16]; channel effect +0.77. [Study 3](STUDY3_RESULTS.md), five wordings: no-channel 0.05 [−0.03, 0.13], channel effect +0.78 (5/5 wordings) | **Confirmed** (Holm), generalizes. Near-zero (±0.15) confirmed for these five wordings only: across-wording 90% upper bound 0.157 |
| **With low reasoning, the leak does not need the hint that Bob knows Alice has the answer.** Without it, encoding is lower but clearly positive. | [Hint control](HINT_RESULTS.md) (R9), five wordings: no hint 0.50 [0.34, 0.66], 5/5 wordings; same-run anchor 0.73; hint effect +0.23 [0.01, 0.44], p = 0.044 | **Confirmed** (Holm), generalizes. The hint effect is confirmed but does not generalize over wordings (4/5) |
| **Matched positive control: an authorized sender encodes almost fully.** | R9 authorized 0.95 [0.76, 1.00], 5/5 wordings; authorized − anchor +0.23 [−0.02, 0.47] | **Confirmed** (Holm), generalizes. The difference from the anchor is descriptive |
| With low reasoning, the matched frame leaks more than v3. | +0.21 [0.006, 0.41]. Borderline: worst-case filling of the missing tasks gives 0.17, which would put the interval across zero. Label −0.05 [−0.25, 0.15], inconclusive | Primary |
| The awareness sentence matters with reasoning but not without it. It combines "Bob knows Alice knows" with "he sees only the order", so its cause is not identified. | At the matched-plain corner: +0.40 (low) vs +0.02 (none); interaction +0.38 [0.07, 0.69] | Secondary; interaction chosen after the data were seen |
| Without thinking, there is no profitable end-to-end use in any arm, including the authorized one. | Expected pair gain −0.70 to −0.92 | Descriptive |
| Four consistent feedback examples set the receiver's convention, under both authorized and restricted prompts. | P1; F restricted receiver, sign-flip p = 0.0005 | Exploratory, synthetic histories, natural-first listing only |
| Feedback that looks like past encoding makes a restricted sender encode (0.79 with both listings). Senders also follow reversed feedback (−0.38), more weakly. The earlier "reverse only weakly" claim was largely an artifact of the listing: with the reversed option listed first, reversal is −0.75. | [Phase 1](PHASE1_RESULTS.md) counterbalanced rerun, p = 0.001 | Exploratory, no thinking, synthetic histories |

## Withdrawn or narrowed

- "A restricted sender who knows Bob knows she has the answer encodes at roughly
  the authorized rate." Withdrawn for no thinking, where awareness is not the
  cause and the size depends on presentation. With low reasoning, awareness does
  raise encoding (0.37 to 0.78). This is still below the authorized 1.00 from an
  earlier small sample.
- "Feedback content fully determines the convention." Narrowed to consistent
  histories, and mainly to receivers.
- L1 encoding differences of 0.75–0.8 as a leakage signal. Withdrawn earlier, in
  the [convention re-analysis](CONVENTION_REANALYSIS.md).

## Method lessons

- **Counterbalance the symbol listing in every probe.** Without thinking, a
  first-option default dominates, and single-presentation results are not robust.
- **Treat no thinking as a weak instrument for this question.** It barely
  signals, even when authorized (0.29). Its conclusions about awareness and the
  label reverse with reasoning. Base safety claims on reasoning regimens.
- **Resume runs only by explicit rules.** The low-reasoning run was resumed twice.
  Only provider failures that returned no model response were re-sent. Timeouts
  are recorded as missing, and cap changes are recorded in the run directory.
- **Size each cap from that condition's measured cost, plus slack for changes in
  caching.** Low-reasoning receivers and restricted senders cost 2–5 times the
  pooled estimates.

## Budget

| Authorization | Spent | Covers |
| --- | --- | --- |
| Earlier $4.00 | $2.3261 | Scouting plus the 24 October probes |
| New $3.00, then more credits | $2.0599 + $4.4489 = $6.5088 | Restraint runs (no thinking) plus the low-reasoning run |
| Three-phase $10 (25 October) | $1.6918 + $5.1109 + $1.2190 + $1.0272 = $9.0489 | Phase 1 screening, Phase 2 A + F, Phase 2 B pair play, Block C screen; **$0.95 remains** |

| $3.00 of credits (25 October) | $1.168 | No-observer control (R7) |
| $2.40 (26 October) | $1.932 | Hint control and matched positive control (R9) |

All figures are peak-rate ledger estimates. Actual provider charges appear to be
lower.

## Open conceptual gaps (25 October review)

- ~~No tested specification explicitly forbids the order from depending on the answer.~~
  Confirmed in Phase 2 over five wordings. A general "by any means" rule works about as well.
  It also holds against a history of successful encoding in single calls (the repeated-play
  arm was dropped by its gate).
- The rules describe the sender–receiver game to both agents. The study measures rule
  following when the channel is pointed out, not discovery of a channel. Phase 2's unflagged
  cell only partly addresses this: it removes the word "ordered", not the AB/BA choice.
- ~~Alice's incentive and the organization's harm are never varied.~~ Incentive confirmed in
  Phase 2; harm screened only (Phase 1).
- ~~Every interval reflects sampling from one exact prompt string.~~ Phase 2 measures five
  wordings per condition. That is still a narrow sample of wordings.
- **Binary payoff dilemma.** The only way for Alice and Bob to earn points harms the organization,
  and there is no lower-gain, lower-harm option. The rule contrasts stay valid (the payoffs are
  identical across specifications), but the absolute leak rates are measured under maximum
  temptation, and "harm does not restrain her" is tested at only one ratio. Partly addressed by the
  [Block C screen](PAYOFF_RESULTS.md): a dominant paid pass (Bob's action) removes the leak; a tenfold
  harm gives an inconclusive reduction. Harmless smaller gains (`legit-half`) remain untested.
- One model family. Only a DeepSeek key and endpoint are configured.
- Pair play is short (5 rounds), and its timeouts depend on the condition.

## Plan (from 25 October)

Three phases under a single $10 budget: [Phase 1](PHASE1_PLAN.md) fixes and screening,
Phase 2 expansion (a confirmatory specification study with paraphrases, and repeated
restricted pair play with actual against shuffled delivery), and Phase 3 final analysis.
A second model family is out of scope for now.

## Earlier recommended next steps (superseded by the plan above)

1. **A second model family** on four cells: v3, the 24 October matched prompt,
   its no-channel control, and the matched restricted receiver, all with
   reasoning. This is the single biggest gap before any general claim.
2. **Repeated restricted pairs with low reasoning.** Test whether the leak
   persists and sharpens in real play: actual delivery against random delivery,
   v3 against matched framing, with an aligned-payoff control to separate
   incentive from ordinary information value. F suggests encoding that appears in
   the feedback licenses more encoding.
3. **A monitor or defence check.** Does the leak survive a fixed canonical order
   (the order chosen by the system, not Alice), or a monitor that reads the
   sender's reasoning? This makes the result actionable rather than only
   descriptive.
4. **Defer** the authorized fork study and the 20-round training configuration.

## Documents

- Phase 2: [PHASE2_PLAN.md](PHASE2_PLAN.md), [PAIRPLAY_PLAN.md](PAIRPLAY_PLAN.md),
  [PHASE2_RESULTS.md](PHASE2_RESULTS.md). Code: `src/order_signal/phase2.py`,
  `src/order_signal/pairplay.py`.
- Plans: [RESTRAINT_LOW_PLAN.md](RESTRAINT_LOW_PLAN.md),
  [RESTRAINT_PLAN.md](RESTRAINT_PLAN.md), [PROBE_PLAN.md](PROBE_PLAN.md).
- Results: [RESTRAINT_LOW_RESULTS.md](RESTRAINT_LOW_RESULTS.md),
  [RESTRAINT_RESULTS.md](RESTRAINT_RESULTS.md),
  [PROBE_RESULTS.md](PROBE_RESULTS.md) (corrected),
  [CONVENTION_REANALYSIS.md](CONVENTION_REANALYSIS.md).
- History: [SCOUT_DECISION.md](SCOUT_DECISION.md),
  [NEXT_EXPERIMENT.md](NEXT_EXPERIMENT.md) (superseded),
  [METHOD_REVIEW.md](METHOD_REVIEW.md).
- Code: `src/order_signal/restraint.py`; tests in `tests/test_restraint.py`.
  Re-run the analysis without API calls:
  `python -m order_signal.restraint --summarize outputs/<run>`.
