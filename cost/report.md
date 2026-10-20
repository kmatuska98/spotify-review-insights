# 100-review pilot: cost and runtime calculator (offline replay)

Rates file: cost/rates.csv (checked 2026-10-18, https://platform.claude.com/docs/en/about-claude/pricing). Rate multiplier: 1.0

## Settings of the measured run

| Provider | Models (exact IDs) | Effort / thinking | Prompt-schema versions | Batch size | Workers | Currency, unit |
|---|---|---|---|---|---|---|
| Anthropic | enrich+group: claude-haiku-5-5; verify+memo: claude-sonnet-5-5 | no extended thinking requested (model default; usage shows 0 thinking tokens) | claude-haiku-5-5+labels-v2+prompt-v1+schema-v1; verify-v1 (as measured; later runs used verify-v2); memo-v1 (as measured; later runs used memo-v2) | enrich 25 (limit 50) | 1 | USD, USD per million tokens (MTok), standard tier, no Batch API |

Unique texts in the 100 pilot reviews: 100. Result-cache hits: cold 0; warm: 100 saved records served with 0 new calls.

## MEASURED on cost_100.csv (cold run, 1 worker)

- IDs: 100 | completed: 100 | failed or quarantined: 0
- Complaint/cancellation records grouped: 51 (51.0% of completed)
- Cold wall-clock: 82.27 s | Warm wall-clock: 0.05 s | Warm new model calls: 0 | Warm cost: $0.000000

| Stage | Model | Requests | Failed | Input tok | Output tok | API cost (USD) |
|---|---|---|---|---|---|---|
| enrich | claude-haiku-5-5 | 4 | 0 | 16903 | 7510 | 0.005445 |
| verify | claude-sonnet-5-5 | 1 | 0 | 3801 | 1470 | 0.022302 |
| group | claude-haiku-5-5 | 10 | 0 | 12725 | 3075 | 0.002810 |
| memo | claude-sonnet-5-5 | 2 | 0 | 2535 | 2977 | 0.034840 |
| **total** | | | | | | **0.065397** |

Cost per 1,000 input rows: $0.6540 | per completed record: $0.000654
(Includes the 20-review Sonnet verify sample and one memo, so per-row figures are higher than enrich alone.)

Throughput (enrich, 1 worker): 3.95 reviews/s (237 per minute). Whole-chain wall clock: 82.27 s cold vs 0.05 s warm. Stage seconds (cold): enrich 25.34, verify 8.35, group 22.97, rank 0.01, memo 25.6.

Local compute/infrastructure cost: UNKNOWN (not measured; not treated as zero).

## ESTIMATE: scaled from the pilot (not measured)

Assumptions (editable): verify sample 1000 reviews; base retry factor 1.0, conservative 1.25; fallback fraction 5% at 20.0x enrich cost; budget $9.11; workers 6, speedup 4.0x (assumed).

| Scenario | Reviews classified | Base cost | Conservative cost | Hours (base) | Budget check |
|---|---|---|---|---|---|
| Full corpus, no exact-text reuse | 660,609 | $55.69 | $105.29 | 11.6 | OVER BUDGET |
| Full corpus, exact-text reuse (484,189 distinct) | 484,189 | $41.12 | $77.48 | 8.5 | OVER BUDGET |
| 100,000-review sample | 100,000 | $9.41 | $16.91 | 1.8 | OVER BUDGET |
| 10,000 checkpoint | 10,000 | $1.98 | $2.73 | 0.2 | within budget |

Output-token cap control: at a cap of 90 output tokens per review, the worst-case enrich output bill for all 660,609 reviews is $29.73 (measured average in the pilot: 75 tokens per review).

Accounting: all 660,622 rows are accounted for in any scenario; 13 empty texts are quarantined ('empty_review_text'); unclassified rows are reported as unfinished, never as successes.

Caveats: the first 100 reviews give an initial estimate only. Rare failures, sustained rate limits and duplicate-text reuse are not measured here. Group cost is scaled by complaint count and includes one-time menu-building overhead, so it is likely overstated at scale. Batch API discounts are NOT applied (hypothetical, not measured). The 100-review pilot was measured before the verifier and memo prompts were revised (verify-v2, memo-v2); it was not repeated, so the verify and memo stage costs here are from the earlier prompts.
