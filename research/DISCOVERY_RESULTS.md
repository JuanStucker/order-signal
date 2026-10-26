# Feedback-discovery screen: results (R11)

Run `outputs/20261026T002413Z-discovery-171a3f31`, 26 October 2026, 00:24–00:34 UTC, under the frozen
[plan](DISCOVERY_PLAN.md). **Incomplete: 46 of 48 decisions.** Both audits pass; one model identity
(`deepseek-v4-pro`). Ledger cost $0.51 of the $0.60 cap.

In the `natural` cell, call `d-natural-t5-s2-rev` returned an invalid response
(`InvalidDeepSeekResponse`). By the frozen rules it is recorded as missing and never re-sent, and the
job stops at its first failure, so `d-natural-t5-s1-nat` was not attempted. Template 5 therefore cannot
be completed in the `natural` cell, and the planned sign-flip test, which needs all six templates in
both cells, is **withheld**. The unattempted call was not run: it could not make the test computable.

| History | n | Encoding [95%] | AB given 1 / given 2 | Natural direction | Natural / reversed listing |
| --- | --- | --- | --- | --- | --- |
| natural (AB for 1, Bob correct) | 22 | +0.64 [0.34, 0.94] | 7/11, 0/11 | +0.64 | 0.60 / 0.67 |
| reversed (BA for 1, Bob correct) | 24 | −0.83 [−1.00, −0.57] | 1/12, 11/12 | −0.83 | −1.00 / −0.67 |

The reversed lower end is capped at −1.

- **Primary (`feedback-sets-convention`):** withheld (5 of 6 templates complete). Template differences,
  natural − reversed mean direction: +1.5, +1.5, +2.0, +1.5, +1.5 for the five complete templates;
  the incomplete template 5 gives +0.5 on its completed calls. All six point the same way.
- **Secondary (planned):** natural − reversed encoding +1.47 [1.07, 1.87].

## Reading (rules fixed in the plan, descriptive because the test is withheld)

When nothing says what Bob observes, four rounds of feedback in which Bob answered correctly set
Alice's mapping: she follows the natural mapping after natural feedback and reverses it after reversed
feedback. Imitating the history and inferring that Bob reads the order are not separated. With the
channel described, the Phase 2 feedback probe gave natural − reversed +1.83 (R5, F).

## Limits

One model, wording 0, 46 calls, synthetic histories. The feedback itself shows the order and Bob's
success. Bob is not sampled. Receiver-side discovery and real multi-round play without a described
channel remain untested.
