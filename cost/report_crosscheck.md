# Cross-check: pilot-based estimate vs the actual 100,000-review run

The calculator (`python cost/calculator.py`) scales the **100-review pilot**. After the 500, 10,000 and 100,000-review runs we can compare.
All "actual" figures are logged token usage x `cost/rates.csv` (see `results/run_summary.json`, `grading/calls.jsonl`); they are not provider invoices.

| Stage | Pilot-based estimate for ~100k (base) | Actual (final run dir) | Notes |
|---|---|---|---|
| Enrich (Haiku 5.5) | about $5.4 | **$4.06** (2,043 calls, 99,970 records) | Exact-duplicate reuse covered 21,913 records (no calls); estimate assumed none |
| Group (Haiku 5.5) | about $2.8 | **$0.71** (797 calls, 43,550 complaints) | Pilot scaled the one-time menu-building cost with volume; menu was built once from the 10,000 run |
| Verify (Sonnet 5.5) | $1.1 for 1,000 sampled | **$0.31** for 300 sampled (12 calls) | Verify sample was 100 (10k run) + 200 (final) |
| Memo (Sonnet 5.5) | $0.03 fixed | **$0.04** (2 calls) | The first draft used a number outside the allowed list and was rewritten once |
| **Total** | about $9.4 | **$5.12** | Plus about $0.35 of pilots, tests and evaluations in other run folders |

Measured throughput: one worker about 237 reviews/min on the pilot; 6 workers about 700-1,000 reviews/min on the 100k run (about 4 to 5 times faster, not 6 times).
Not applied anywhere: provider Batch API (about half price, asynchronous). A full 660,609-review run was out of budget; at the observed $0.052 per newly enriched text (the $4.06 enrich cost / 78,057 non-reused records) enriching all 484,189 distinct texts is an **estimate** of roughly $25 for enrich alone, before grouping, verification and retries.
