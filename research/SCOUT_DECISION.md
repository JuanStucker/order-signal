# Order signal experiment selection

> **Update, 25 October 2026.** A post-hoc [convention re-analysis](CONVENTION_REANALYSIS.md)
> and frozen-plan [single-decision probes](PROBE_RESULTS.md) changed this selection.
> The probes cost $0.4193; total spend is $2.3261 of $4.00. Four consistent
> feedback examples override the natural convention. A restricted sender given a
> disclose-only rule and mutual awareness encodes at a rate similar to the matched
> authorized sender, while the original v3 restricted prompt shows no encoding.
> Priority 2 below (matched permission) is now first, and the priority table
> further down is superseded. Current claims and next steps are in
> [CURRENT_STATUS.md](CURRENT_STATUS.md).

**Run a fresh, controlled feedback by delivery experiment; do not launch the
existing ten-pair, twenty-training-round configuration unchanged.** The strongest
signal is that feedback changes whether an authorized receiver uses an available
signal. The current restricted conditions do not support selecting a large
objective-driven collusion study.

The scouting campaign used **$1.9068 of the $4 ceiling** at conservative peak-rate
accounting: 1,075 API requests, 521 completed sender–receiver trials and 32 completed
receiver replays. Two pair jobs stopped at their predeclared cash caps, leaving
two failed and five unattempted trials. No charges remain unresolved. **$2.0932
remains unspent.** These are usage-based ledger estimates, not invoice totals.
See the [budget ledger](scout-budget.json) and [verified provider rates](https://api-docs.deepseek.com/quick_start/pricing/).

## Methodological verdict

The information boundary, task equivalence, independently randomized delivery,
frozen evaluation history and pair isolation are suitable for this narrow synthetic
study. All 54 offline tests pass. All 42 completed pair jobs passed prompt/channel
reconstruction and independent action/payoff audits; both replay histories passed
their input audits. Failed jobs remain visible and are not replaced.

Three changes are needed before stronger causal claims:

- **Permission is confounded with awareness and framing.** The authorized prompt
  tells Bob that Alice knows the answer; the restricted prompt does not. Match that
  information before interpreting their difference as rule compliance.
- **Learning and immediate channel use are mixed in A1–A2.** Random delivery affects
  both training and evaluation. Fork evaluation from the same saved history to
  isolate immediate dependence on order.
- **The group objective makes correct answers costly.** It changes the value of
  information, and group harm equals correctness by construction. An objective
  interaction does not by itself establish collusion or independently measured harm.

The [method review](METHOD_REVIEW.md) covers these issues, inference settings,
label priors, sampling units, source overlap and uncertainty. This is a selective
pilot, not a confirmatory result or a novelty certification.

## Most useful signals

All entries below include passes in the correctness denominator. Pair gain is
Alice's and Bob's combined score, averaged over evaluation rounds.

| Inference regimen and condition | Independent pairs | Correct | Wrong | Pass | Mean pair gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| Low reasoning, authorized history, actual order | 4 | 32/32 | 0 | 0 | 2.000 |
| Low reasoning, authorized memoryless, actual order | 4 | 16/32 | 0 | 16 | 1.000 |
| No thinking, authorized history, actual order | 4 | 23/32 | 2 | 7 | 1.188 |
| No thinking, authorized memoryless, actual order | 4 | 26/32 | 6 | 0 | 0.875 |
| No thinking, authorized history, random order | 4 | 11/32 | 12 | 9 | −0.813 |
| No thinking, restricted individual history, actual order | 4 | 11/32 | 10 | 11 | −0.563 |
| No thinking, restricted individual history, random order | 4 | 11/32 | 12 | 9 | −0.813 |

**Feedback and receiver use is the leading candidate.** Under low reasoning, the
history-minus-memoryless correctness differences were **+62.5, +37.5, +62.5 and
+37.5 percentage points**. The mean is +50 points and remains +45.8 to +54.2 points
when any one pair is omitted. Both conditions' senders encoded every evaluation
answer using AB→1 / BA→2. The entire correctness difference came from Bob passing,
not encoding failures or wrong answers. All four history pairs passed on their
first training round and answered the next three correctly. This is consistent
with feedback resolving receiver uncertainty; the current history comparison also
changes framing, so the mechanism needs the matched follow-up.

The last two low-reasoning pairs were added adaptively after seeing the initial
signal, using fresh seeds and unchanged settings. They are additional exploratory
replications, not an independent confirmatory holdout. Four pairs do not support a
precise population estimate, even with a large, consistent observed difference.

**Immediate order use survives the cleaner intervention.** In the receiver replay,
the same two histories, sender decisions and answers gave **16/16 correct with
actual orders versus 7/16 with randomized orders**. Randomized successes exactly
matched the seven orders that happened to equal Alice's original order. Pair-level
accuracy differences were +75 and +37.5 points; mean pair gain fell from +2.000 to
−1.375. This supports decoder reliance conditional on these histories. The 32
replays are not 32 new independent pairs and must not be pooled into the main table.

**The history result is inference-regimen dependent.** Without thinking, history
correctness was 9.4 points below memoryless correctness, with pair differences
0, +12.5, −50 and 0 points. Its mean changes sign if the weakest pair is omitted.
History did improve mean private gain descriptively by reducing wrong answers, but
that gain was not consistent across pairs. Do not call feedback universally helpful
or harmful. Tool choice, output caps and provider sampling behavior differ between
regimens, so this is not an isolated effect of reasoning computation.

**Restricted profitable transfer is not the leading signal.** In the no-thinking
screen, L3 had negative average gain and no correctness advantage over L4. The
pair-gain objective interaction was −0.188 and changed direction across pairs.
The low-reasoning restricted contrast is incomplete and is withheld. These facts
do not establish absence of leakage or collusion; they fail to justify choosing
that large final experiment now.

## Missing data and compute implications

Low-reasoning A2 pair 2 stopped after ten completed trials, and L3 pair 2 after
seven, because another worst-case request reservation would exceed its $0.35 cap.
Their final accounted costs were $0.2934 and $0.2906. These are intentional budget
stops, not provider credit failures or evidence that the models cannot finish a
decision. Their completed evaluation subsets are descriptive only: A2 has 2 correct,
0 wrong and 4 passes; L3 has 1 correct, 0 wrong and 2 passes. Overall A1–A2 and
A1–L3 low-reasoning contrasts are withheld.

Equal cash allocation was conservative but inefficient because difficult controls
required far more output. The completed first-stage A1 calls averaged about 213
output tokens versus 1,492 for M2; A2 and L3 often required thousands and reached
more than 10,000 tokens on individual completed calls. Size future condition budgets
separately or use a predeclared shared global ledger with adequate reserves. Do not
interpret cap-induced missingness as a behavioral null or quietly resume only
successful-looking pairs.

## Selection and concrete next step

| Priority | Experiment | Why it merits the next budget |
| --- | --- | --- |
| 1 | Authorized receiver feedback × immediate delivery, with Alice's decisions held fixed | Largest consistent history signal; clean receiver intervention; separates encoding from use and avoids the training-channel confound. |
| 2 | Matched permission × delivery, with equal receiver awareness | Directly relevant to restricted disclosure; repairs the most consequential identification problem before a larger collusion study. |
| 3 | Label/presentation counterbalancing and alternate conventions | Tests dependence on the natural AB→1 mapping. Memoryless low-reasoning Bob answered 10/15 BA observations but only 6/17 AB observations, an exploratory asymmetry worth checking. |
| Defer | Twenty training rounds, broad objective interaction or market transfer | The pilot gives no reason to buy longer training for the authorized ceiling behavior, and no robust profitable restricted effect on which to base the larger claim. |

The [proposed final specification](NEXT_EXPERIMENT.md) uses four receiver cells:
true versus empty feedback crossed with actual versus independently randomized
orders, all other receiver text held identical. A planning starting point is
24 fresh histories, four training rounds and sixteen evaluation answers: 2,112
calls. Freeze a pair-level analysis and meaningful effect size before sampling;
the specification gives precision scenarios and explicitly does not promise power.
Use a new budget for that run and retain every pilot separately.

The robust decision is narrower than a robust population claim: **prioritize
feedback-dependent receiver use, preserve channel randomization, and repair the
restriction comparison before trying to establish harmful collusion.** More
uncontrolled repetitions would not fix the present identification limits.

## Artifacts and reproduction

- [Pair-level figure](scout-results.png) and [PDF](scout-results.pdf).
- [All pair rows](scout-pairs.csv), [condition summaries](scout-arms.csv), and
  [contrasts with leave-one-pair-out sensitivity](scout-results.json).
- [Initial frozen plan](SCOUT_PLAN.md), [receiver replay plan](REPLAY_PLAN.md),
  [adaptive replication plan](REPLICATION_PLAN.md), and
  [worst-case budget envelope before the added run](replication-budget-authorization.json).
- Raw calls, frozen source, schedules, statuses and child ledgers:
  [broad screen](../outputs/20261024T213446Z-scout-6457b0df),
  [reasoning screen](../outputs/20261024T213450Z-scout-67d57a3a),
  [fresh-pair repeat](../outputs/20261024T213909Z-scout-8212b48a),
  [receiver replay](../outputs/scout-receiver-replay-20261024).

Rebuild tables and figures without API calls from the project directory, using
Python with matplotlib installed:

```sh
python3 research/summarize_scout.py \
  outputs/20261024T213446Z-scout-6457b0df \
  outputs/20261024T213450Z-scout-67d57a3a \
  outputs/20261024T213909Z-scout-8212b48a \
  --replay outputs/scout-receiver-replay-20261024
```
