# Cross-check: pilot-based estimate vs the actual 105,000-review run

The calculator (`python cost/calculator.py`) scales the **100-review pilot**. After the 500, 10,000 and 105,000-review runs we can compare.
All "actual" figures are logged token usage x `cost/rates.csv` (see `results/run_summary.json`, `grading/calls.jsonl`); they are not provider invoices.

| Stage | Pilot-based estimate for ~100k (base) | Actual (final run dir) | Notes |
|---|---|---|---|
| Enrich (Haiku 5.5) | about $5.4 | **$4.25** (2,138 calls, 104,975 records) | Exact-duplicate reuse covered 23,134 records (no calls); estimate assumed none |
| Group (Haiku 5.5) | about $2.8 | **$0.74** (842 calls, 45,797 complaints) | Pilot scaled the one-time menu-building cost with volume; menu was built once from the 10,000 run |
| Verify (Sonnet 5.5) | $1.1 for 1,000 sampled | **$0.33** for about 310 sampled (13 calls) | Verify sample was 100 (10k run) + 200 (final) + a few new IDs after the extension |
| Memo (Sonnet 5.5) | $0.03 fixed | **$0.08** (4 calls) | Two memo runs (before and after the 5,000-review extension); the first draft of one used a number outside the allowed list and was rewritten once |
| **Total** | about $9.4 | **$5.40** | Plus about $0.35 of pilots, tests and evaluations in other run folders |

Measured throughput: one worker about 237 reviews/min on the pilot; 6 workers about 700-1,000 reviews/min on the 100k run (about 4 to 5 times faster, not 6 times).
Not applied anywhere: provider Batch API (about half price, asynchronous). A full 660,609-review run was out of budget; at the observed $0.052 per newly enriched text (the $4.25 enrich cost / 81,841 non-reused records) enriching all 484,189 distinct texts is an **estimate** of roughly $25 for enrich alone, before grouping, verification and retries.

## Refresh after 500, 10,000 and 105,000 reviews (enrich stage, measured)

| Run | Reviews completed | Enrich cost (USD) | Cost per 1,000 completed | Workers, batch | Notes |
|---|---|---|---|---|---|
| Pilot (cost_100.csv) | 100 | 0.0054 | 0.054 | 1, 25 | 4 calls, 25 s |
| Checkpoint 500 | 499 | 0.0279 | 0.056 | 1, 25 | 24 calls, 132 s of call time, 21 exact-duplicate reuses |
| Development 10,000 | 9,997 | 0.4293 | 0.043 | 1, 50 | 216 calls, 2,049 s of call time, 1,552 reuses |
| Final sample | 104,975 | 4.254 | 0.041 | 1 then 6, 50 | 2,138 calls; 23,134 reuses; the run was interrupted once and resumed |

Reading: cost per completed review fell from $0.054 to $0.041 per 1,000 as exact-duplicate reuse grew with sample size; time per review did not rise. The estimate used for budgeting (100,000 reviews about $9.4) was therefore conservative; the first 100 reviews are an initial estimate only.
