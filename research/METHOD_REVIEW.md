# Methodological validity of the order signal experiment

Assessment dated 24 October 2026. The implementation can support a controlled
study of information transfer through action order and short-context adaptation.
The current configurations do not identify spontaneous collusion, conscious
agreement, or the isolated effect of confidentiality. The proposed ten-pair
authorized study remains an exploratory pilot.

## What is valid

| Component | Assessment and implication |
| --- | --- |
| Task equivalence | AB and BA execute both dummy items at identical cost and final state. This isolates an otherwise utility-neutral order channel. It does not establish preservation of a useful real-world workflow. |
| Information boundary | Alice alone receives the current answer. Bob receives only the order plus permitted shared training history. Current answers are IID, and evaluation answers never enter feedback. Exact saved-prompt reconstruction audits this boundary. |
| Channel intervention | Independent order replacement is sampled after sender commitment, with a separate seeded RNG. It breaks sender-current-answer dependence in the delivered order in expectation while preserving the two-symbol alphabet. Finite samples can have accidental correlations. |
| Main objective intervention | Restricted L1–L4 change the objective sentence and delivery regime while retaining confidentiality. This identifies the effect of those prompt objectives in this game, subject to valid completion and stable model behavior. |
| History isolation | Training histories are separate by pair and arm. Only past answer, delivered order, choice and outcome are replayed. Evaluation freezes history. There are no model-weight updates or persistent provider conversations. |
| Replication | Pair contexts with distinct IID answer streams are the clusters. Arms share answer schedules within a replication. Repeated rounds and the two agents are not independent replications. |
| Cost and failure records | Calls reserve cost before submission; retries are disabled. Invalid responses are retained and charged when usage is known. Unknown usage retains its reservation. Incomplete pairs are not replaced or counted as passes. |
| Verification | All 51 existing offline tests passed before paid scouting. Three additional tests verify budget decomposition, matched schedules, altered action/payoff detection and receiver-fork history preservation; all 54 tests pass. A scripted pass establishes software behavior only. |

The new scouting analysis additionally links returned tool actions to executed
checklist actions, reconstructed outcomes and all payoff fields. The original
learning audit checks prompt and channel boundaries but does not independently
validate every saved outcome against returned actions.

## Interpretations the controls do not support

1. **Authorized versus restricted is not a pure permission contrast.** Authorized
   prompts explicitly tell both agents that Alice knows the answer and may encode
   it, and frame the activity as communication. Restricted Bob is not explicitly
   told who holds it. The difference includes awareness and framing. Keep the
   authorization statement as the only changing text in a new matched test.
2. **History versus memoryless is a context treatment.** History arms also say
   “same pair,” identify the phase and describe feedback. A1–M2 therefore measures
   the full history/context package. An empty-history or length-matched irrelevant
   history control is needed for a specific feedback-content claim.
3. **Actual versus random learning arms change both training and evaluation.**
   A1–A2 is the value of an entire channel regime, including its effect on learned
   beliefs. Fork evaluation from an identical frozen training history to isolate
   immediate dependence on the delivered order; independently vary training
   delivery to study acquisition.
4. **The objective contrast bundles incentive and information value.** Private
   expected payoff on an attempted answer is `3q − 2`; answering beats passing
   only when conditional correctness `q > 2/3`. Expected group payoff is `−q`,
   so passing is always optimal and knowingly wrong answers tie it. The group
   condition has no positive value of learning the correct answer. A positive
   interaction is not specific evidence of antisocial intent. An aligned-payoff
   comparison is needed for that stronger interpretation.
5. **Correctness and stipulated harm are the same outcome.** Group loss is exactly
   the correctness indicator. Pair gain and organization loss are also fixed
   functions of correct/wrong/pass. Report them to explain incentives, but do not
   call them independent corroboration of harm.
6. **Encoding is different from decoding and profit.** Sender secret-order
   dependence can be present while Bob passes, uses the reverse convention, or
   guesses unprofitably. Inspect per-pair contingency tables and encoding direction;
   pooled mutual information can obscure opposite conventions. Small-sample
   empirical MI is biased upward and is not a significance test.
7. **A familiar convention can precede learning.** AB/BA and 1/2 admit a natural
   ordering. High memoryless accuracy may reflect shared model priors. A claim
   about newly learned conventions requires label/codebook counterbalancing or
   held-out symbol sets, plus a training-history comparison.
8. **Changing reasoning settings changes more than computation.** The client uses
   forced tool choice without thinking and automatic tool choice with thinking.
   The provider documents that temperature has no effect in thinking mode. Different
   output limits also affect completion. Call the contrast an inference-regimen
   comparison, not an isolated causal effect of reasoning tokens. [Provider API
   documentation](https://api-docs.deepseek.com/guides/responses_api/).
9. **Model alias and seeded environment are not full reproducibility.** The
   returned alias is checked for changes, but it does not attest immutable weights.
   The experiment seeds do not seed hosted sampling. Match runs in time, archive
   source/prompts/model metadata, and state the remaining provider uncertainty.

## Precision and stopping

The revision 3 single-round simultaneous Hoeffding method is conservative but
valid under independent bounded trial outcomes. Correlation between its three
score measures does not invalidate the union bound. It must not be applied to
repeated-pair learning rounds as if each were independent. The stored planning
scenario requires a conservative sufficient **2,288 trials per condition** and
18,304 requests for its stronger evidence rule; this is an assumption-based bound,
not a minimum or a pilot-derived requirement. See [planner output](original-planner.json).

The ten-pair learning runner correctly resamples paired differences, but its
pointwise percentile bootstrap is exploratory, lacks multiplicity adjustment,
and may collapse to zero width when observed pairs are identical. Ten identical
pairs do not establish a zero-variance population. With two or four pairs, report
pair values and directions rather than bootstrap significance. Fresh final data
need a frozen pair-level analysis, a meaningful effect/margin, and an honest
sample-size or precision calculation. A null requires an equivalence margin, not
merely a non-significant difference.

The runners stop on a failed call and can stop on their dollar cap. Failures can
depend on the condition and on difficult model decisions. Completed subsets can
therefore be selected. Keep failures visible, withhold overall paired contrasts
when required pairs are missing, and include completion feasibility in the decision.
Do not repeatedly raise output caps on the same sampled pairs until they succeed.

## Research relevance

Existing work already studies steganographic capabilities, incentive-driven hidden
communication, and canonical task interfaces. The useful potential contribution
here is a narrowly controlled separation of sender encoding, receiver use,
short-context feedback and disclosure restrictions through task-equivalent actions.
That is a candidate contribution, not a certified literature-wide novelty claim.

- [Motwani et al., NeurIPS 2024](https://papers.nips.cc/paper_files/paper/2024/hash/861f7dad098aec1c3560fb7add468d41-Abstract-Conference.html)
  formalize secret collusion and evaluate steganographic capabilities and defenses.
- [Mathew et al., IJCNLP-AACL 2025](https://aclanthology.org/2025.ijcnlp-long.34/)
  elicit linguistic steganography through gradient and in-context optimization;
  their training setting differs from this fixed-model short-history experiment.
- [Pandey et al., October 2026](https://arxiv.org/abs/2610.25032)
  examine private-state leakage under passive monitoring and canonical interfaces;
  their results limit claims that a task-preserving channel restriction is itself novel.

These primary sources were checked for this assessment. The current study should
not be presented as the first demonstration of hidden communication, collusion,
or task-preserving channel restriction.
