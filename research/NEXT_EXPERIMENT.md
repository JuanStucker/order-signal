# Recommended final experiment specification

> **Superseded on 25 October 2026.** Cheap single-decision probes answered this
> specification's main question: synthetic feedback fully determines both agents'
> convention. They also found that a restricted sender with matched awareness
> encodes the answer at roughly the authorized rate. The recommended next study is
> now the restraint decomposition and restricted-use study in
> [PROBE_RESULTS.md](PROBE_RESULTS.md). The text below is kept as the record of
> the earlier recommendation.

Do not launch `learning-10pairs.json` unchanged. Its twenty-round training phase
is not justified by the observed early authorized performance, and A1 versus A2
changes both training and evaluation channels. The most informative next study
separates feedback use from immediate use of the order channel. This specification
is a proposed next run, not authorization to spend beyond the completed $4 screen.

## Main question

Does authorized feedback make a receiver use an already available action-order
signal more reliably, and does randomizing that order remove the benefit? Measure
encoding, answering, correctness and profit separately. This is a communication
mechanism study; it is not evidence of voluntary covert collusion under a rule.

## Preferred controlled design

Use independent training histories. Train each authorized Alice/Bob pair for four
rounds with actual delivery, without a supplied codebook. Freeze that history.
For each fresh evaluation answer, obtain one Alice order with the frozen history.
Replay Bob under the following four conditions in randomized order:

| Cell | Bob receives training feedback | Bob receives current order |
| --- | --- | --- |
| H actual | True frozen feedback | Alice's actual order |
| H random | The same true feedback | Independent random replacement |
| Empty actual | Empty feedback | The same Alice order |
| Empty random | Empty feedback | The same random replacement as H random |

Keep all other receiver text identical, including knowledge that Alice has the
answer, authorization, role, objective and evaluation framing. Only feedback content
and current order change. Specify this as a new version; the current A1/M2 prompts
also change framing and are not already this factorial. Randomize call ordering,
keep decisions stateless, release no evaluation outcomes, and save all inputs.

This controls sender decisions across receiver forks and therefore localizes the
effect to receiver use. It deliberately does not estimate how withholding sender
history changes encoding. If the target is instead end-to-end learning, give
history/empty-history senders their own arms and retain a separate receiver-fork
diagnostic; the two estimands must not be conflated.

The current pilot's natural AB/BA and 1/2 labels make shared priors plausible. Add
a preregistered second symbol set, or counterbalance presentation order, to test
transfer. Pure relabeling does not guarantee removal of ordinal priors. If arbitrary
codebook learning is the target, a separate control can assign a hidden random
mapping to Alice and reveal it to Bob only through feedback; that is instructed
encoding and must be reported as a capability/learning control.

## Outcomes and analysis to freeze before final sampling

Use evaluation correctness per planned round, including passes, as the primary
outcome. Retain conditional accuracy, attempt rate, pair gain and sender
secret-order tables as mechanism diagnostics. Do not select only attempted answers.

Two prespecified contrasts are H actual minus Empty actual (feedback-content effect
on use of the same sender decisions) and H actual minus H random (immediate channel
dependence). The four-cell interaction is secondary. Analyze differences at the
independent-history level. Never call the many forks independent replications.
Keep a fixed sample size and stopping rule, and budget enough headroom to finish
every required cell. If a required cell fails, show the incomplete result and do
not silently impute it or replace the history.

A practical planning starting point is **24 fresh independent histories, four
training rounds and sixteen fresh evaluation answers**, with five calls per
evaluation answer (one sender and four receiver forks): **2,112 calls** in total.
This is a proposed precision design, not a power guarantee. At 24 histories, an
approximate simultaneous two-contrast t interval with 97.5% coverage per contrast
has a half-width near `2.40 × SD(difference) / sqrt(24)`:
about 0.10, 0.15 or 0.25 for history-level SDs of 0.2, 0.3 or 0.5. Use a t critical
value for the actual analysis. The tiny selected pilots cannot establish which SD
applies; plan conservatively and report achieved uncertainty. An additional label
family requires more budget or an explicitly narrower claim for each family.

For an approximate final analysis, preregister pair-level mean differences and
Bonferroni-adjusted paired t intervals for the two contrasts, show every history,
and include a cluster-bootstrap sensitivity analysis. State distributional/small-
sample limits. If finite-sample distribution-free guarantees are required, retain
bounded-difference intervals and accept the larger sample requirement. For a
single difference in [-1,1], two-sided Hoeffding half-width is
`sqrt(2 log(2/alpha) / N)`; with alpha=0.025 and N=24 it is about 0.604. The current
v3 repeated-round evidence gates must not be reused for this study.

Before buying the run, use measured **per-condition** token and latency costs;
ambiguous or randomized-history decisions consume much more reasoning than learned
actual-channel decisions. A single pooled cost per call and equal cash allocation
can censor expensive controls. Quote a scenario-based total and a conservative
cash ceiling, including full pending reservations; obtain a new budget if it exceeds
the remaining authorization. No final live configuration is activated here.

## Follow-up if confidentiality is the scientific priority

Use a separate matched permission-by-channel design. Tell Bob that Alice knows the
answer in both permission arms, preserve the same role and communication framing,
and change only the disclosure authorization rule. Keep objectives fixed initially.
Add the objective factor only if restricted encoding and profitable use occur
reliably enough to study. Include authorized communication as a capability control.

Treat a pass as a legitimate choice. Require sender dependence on the current
answer, receiver use, and positive pair gain before claiming profitable restricted
transfer. A permission effect still does not establish conscious agreement. An
aligned-payoff control is required to separate conflict of interests from ordinary
information value. The present restricted pilot does not justify funding the large
objective interaction study as the leading final experiment.

The authorized fork study is the stronger near-term methodological choice. The
matched confidentiality study has greater direct relevance to collusion risk but
needs another small, independently specified feasibility check. More repetitions
of the present mismatched prompts would not repair that identification problem.
