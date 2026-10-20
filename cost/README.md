# cost/: 100-review cost and runtime calculator

## Offline replay (default; no API key, no network, no model calls)

```bash
python cost/calculator.py                                 # recomputes everything from saved usage + editable rates
python cost/calculator.py --rate-multiplier 2             # doubles API cost; measured time and local costs are unchanged
python cost/calculator.py --reviews 250000 --budget 10    # add a custom projected volume; measured pilot results do not change
python cost/calculator.py --verify-sample 500 --fallback-fraction 0.05 --workers 6 --worker-speedup 4 --output-token-cap 90
python cost/calculator.py --report                        # rewrites cost/report.md
```

Editable controls: rates (`rates.csv`, dated and linked), budget, verify sample size, retry factor for the conservative case, fallback fraction and cost ratio, workers and an *assumed* speedup, output-token cap. Scenarios that exceed the budget are labeled `OVER BUDGET`.
Opening or importing the calculator never makes a paid call.

## Explicit paid pilot (makes real API calls, about $0.07)

```bash
python cost/run_pilot.py --label cold --run-dir work/pilot_final    # empty cache, one worker, whole chain on data/cost_100.csv
python cost/run_pilot.py --label warm --run-dir work/pilot_final    # same settings and saved results: expects 0 new calls
python cost/package_pilot.py --run-dir work/pilot_final             # copies the measured evidence into this folder (no calls)
```

## Files

| File | Contents |
|---|---|
| `report.md` | measured-100 tables, settings, throughput, full-run base/conservative estimates, budget warnings (offline replay output) |
| `report_crosscheck.md` | pilot-based estimate vs the real runs at 500, 10,000 and 105,000 reviews |
| `rates.csv`, `rates.json` | dated Anthropic prices (checked 2026-10-18) and source link; editable |
| `usage.csv` | raw provider usage by stage (requests, failures, input and output tokens, summed request seconds) |
| `pilot_calls.jsonl` | every attempted call of the cold run with run id, stage, request id, usage, timing |
| `pilot_records.jsonl` | one record per pilot ID with original row hash and common labels |
| `pilot_runs.jsonl` | cold and warm runs: wall clock, per-stage seconds, calls and cost |
| `pilot_summary.json` | counts and settings used by the calculator |

## Notes

- Billing formula: `item_cost = billed_tokens x price_per_million / 1,000,000`; total = sum of mutually exclusive items. Thinking tokens: none requested; none appear in usage. Provider prompt caching: not used. Batch API: not used.
- The pilot was measured with prompts `verify-v1` and `memo-v1`; the verifier and memo prompts were revised afterwards (`verify-v2`, `memo-v2`) and the pilot was not repeated.
- Local compute/electricity cost: unknown (not measured and not treated as zero).
- API cost here is computed from logged usage x rates, not from a provider invoice; reconcile with the provider's usage dashboard.
