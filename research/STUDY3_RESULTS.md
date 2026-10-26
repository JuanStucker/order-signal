# Study 3 results: no-observer control over five wordings

Run `outputs/20261025T214405Z-study3-8639138c`, 25 October 2026, 21:44–22:07 UTC, under the frozen
[plan](STUDY3_PLAN.md). Complete: 320/320 calls, no missing tasks, both audits pass, one model identity
(`deepseek-v4-pro`). Ledger cost $1.168 of the $2.60 cap. Re-run the analysis without calls:
`python -m order_signal.study3 --summarize outputs/20261025T214405Z-study3-8639138c`.

| Cell | n | Encoding [95%] | Per wording (W0–W4) | Natural / reversed listing | AB rate |
| --- | --- | --- | --- | --- | --- |
| anchor | 80 | 0.825 [0.694, 0.956] | 0.875, 0.875, 0.625, 0.875, 0.875 | 0.85 / 0.80 | 0.54 |
| nochan | 240 | 0.050 [−0.034, 0.134] | −0.125, 0.167, 0.042, 0.125, 0.042 | 0.017 / 0.083 | 0.88 |

**Claim family (Holm, α = 0.05):**

| Claim | Estimate (SE) | p | Holm threshold | Fixed wordings | Across wordings |
| --- | --- | --- | --- | --- | --- |
| `anchor-leaks` | 0.825 (0.073) | < 0.001 | 0.0167 | Confirmed | Generalizes: 95% [0.62, 1.03], 5/5 |
| `channel-effect` (anchor − nochan) | 0.775 (0.085) | < 0.001 | 0.025 | Confirmed | Generalizes: 95% [0.54, 1.01], 5/5 |
| `nochan-null` (±0.15) | 0.050 (0.044) | 0.012 | 0.05 | Confirmed | Does not generalize: 90% [−0.057, 0.157] |

Reading: the leak needs an observer, confirmed and general over the five wordings. No-observer encoding
is near zero for these five wordings; its across-wording interval exceeds +0.15 by 0.007, so it is not
established as near zero across wordings. Without an observer the sender mostly defaults to AB (88%).
The anchor reproduces the Phase 2 anchor (0.85); the runs are not pooled.
