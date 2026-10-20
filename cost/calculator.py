"""OFFLINE cost and runtime calculator. No API key, no network, no model calls.

Reads the MEASURED 100-review pilot (cost/usage.csv, cost/pilot_summary.json, cost/pilot_runs.jsonl) and the
EDITABLE rates (cost/rates.csv), then scales each stage by its own work count:

    item_cost = billed_tokens x price_per_million / 1,000,000        total = sum of items

Replay:   python cost/calculator.py
Edit:     python cost/calculator.py --rate-multiplier 2 --budget 10 --verify-sample 1000 --workers 6 --worker-speedup 4
Write:    python cost/calculator.py --report        (rewrites cost/report.md)

Everything under "ESTIMATE" is a projection from 100 reviews, not a measurement or a guarantee.
"""
import argparse, csv, json
from pathlib import Path

COST = Path(__file__).resolve().parent
FULL_NONEMPTY, FULL_DISTINCT, FULL_ROWS, FULL_EMPTY = 660_609, 484_189, 660_622, 13


def load():
    rates = {r["model"]: r for r in csv.DictReader((COST / "rates.csv").open(encoding="utf-8"))}
    usage = list(csv.DictReader((COST / "usage.csv").open(encoding="utf-8")))
    summ = json.loads((COST / "pilot_summary.json").read_text(encoding="utf-8"))
    runs = [json.loads(x) for x in (COST / "pilot_runs.jsonl").read_text(encoding="utf-8").splitlines()]
    return rates, usage, summ, runs


def price(rates, model, tin, tout, mult):
    r = rates[model]
    return mult * (tin * float(r["input_usd_per_mtok"]) + tout * float(r["output_usd_per_mtok"])) / 1e6


def measured(rates, usage, mult):
    out = {}
    for u in usage:
        tin, tout = int(u["input_tokens"]), int(u["output_tokens"])
        out[u["stage"]] = {"model": u["model"], "requests": int(u["requests"]), "failed": int(u["failed_requests"]),
                           "input_tokens": tin, "output_tokens": tout, "cost_usd": price(rates, u["model"], tin, tout, mult)}
    return out


def project(m, summ, n_reviews, verify_sample, retry_factor, fallback_fraction, fallback_cost_ratio):
    """Scale each stage by its own work count (never memo cost x review count)."""
    per_review = m["enrich"]["cost_usd"] / summ["pilot_ids"]
    complaints = n_reviews * summ["complaint_share"]
    per_complaint = m["group"]["cost_usd"] / max(1, summ["complaint_or_cancellation_records"])
    per_verified = m["verify"]["cost_usd"] / summ["verify_sample"]
    items = {"enrich": per_review * n_reviews * retry_factor,
             "group": per_complaint * complaints * retry_factor,
             "verify": per_verified * verify_sample,
             "memo": m["memo"]["cost_usd"],   # one-time, fixed
             "fallback": per_review * n_reviews * fallback_fraction * fallback_cost_ratio}
    items["total"] = sum(items.values())
    return items


def hours(n_reviews, summ, runs, workers, speedup, retry_factor):
    cold = next(r for r in runs if r["label"] == "cold")
    per_review_s = cold["stages"]["enrich"]["seconds"] / summ["pilot_ids"]      # measured, 1 worker
    return per_review_s * n_reviews * retry_factor / max(1.0, speedup if workers > 1 else 1.0) / 3600


def main(a):
    rates, usage, summ, runs = load()
    m = measured(rates, usage, a.rate_multiplier)
    L = []
    P = L.append
    P("# 100-review pilot: cost and runtime calculator (offline replay)\n")
    P(f"Rates file: cost/rates.csv (checked {next(iter(rates.values()))['checked_on']}, {next(iter(rates.values()))['source_url']}). Rate multiplier: {a.rate_multiplier}\n")
    P("## Settings of the measured run\n")
    P("| Provider | Models (exact IDs) | Effort / thinking | Prompt-schema versions | Batch size | Workers | Currency, unit |\n|---|---|---|---|---|---|---|")
    P(f"| {summ.get('provider', 'Anthropic')} | enrich+group: claude-haiku-5-5; verify+memo: claude-sonnet-5-5 | {summ.get('effort_setting', 'n/a')} | {summ.get('enrich_label_config', '')}; {summ.get('verify_version', '')}; {summ.get('memo_version', '')} | enrich {summ.get('batch_size_enrich', 25)} (limit 50) | {summ.get('workers', 1)} | {summ.get('currency', 'USD')}, {summ.get('price_unit', 'per MTok')} |\n")
    P(f"Unique texts in the 100 pilot reviews: {summ.get('unique_texts', 'n/a')}. Result-cache hits: cold {summ.get('cold_cache_hits', 0)}; warm: {summ.get('warm_cache_hits_completed_records_served_from_saved_results', 'n/a')} saved records served with 0 new calls.\n")
    P("## MEASURED on cost_100.csv (cold run, 1 worker)\n")
    P(f"- IDs: {summ['pilot_ids']} | completed: {summ['completed']} | failed or quarantined: {summ['failed_or_quarantined']}")
    P(f"- Complaint/cancellation records grouped: {summ['complaint_or_cancellation_records']} ({summ['complaint_share']:.1%} of completed)")
    P(f"- Cold wall-clock: {summ['cold_wall_seconds']} s | Warm wall-clock: {summ['warm_wall_seconds']} s | Warm new model calls: {summ['warm_new_calls']} | Warm cost: ${summ['warm_cost_usd']:.6f}\n")
    P("| Stage | Model | Requests | Failed | Input tok | Output tok | API cost (USD) |\n|---|---|---|---|---|---|---|")
    for s, v in m.items():
        P(f"| {s} | {v['model']} | {v['requests']} | {v['failed']} | {v['input_tokens']} | {v['output_tokens']} | {v['cost_usd']:.6f} |")
    tot = sum(v["cost_usd"] for v in m.values())
    P(f"| **total** | | | | | | **{tot:.6f}** |\n")
    P(f"Cost per 1,000 input rows: ${tot / summ['pilot_ids'] * 1000:.4f} | per completed record: ${tot / max(1, summ['completed']):.6f}")
    P("(Includes the 20-review Sonnet verify sample and one memo, so per-row figures are higher than enrich alone.)\n")
    cold = next(r for r in runs if r["label"] == "cold")
    es = cold["stages"]["enrich"]["seconds"]
    P(f"Throughput (enrich, 1 worker): {summ['pilot_ids'] / es:.2f} reviews/s ({summ['pilot_ids'] / es * 60:.0f} per minute). Whole-chain wall clock: {summ['cold_wall_seconds']} s cold vs {summ['warm_wall_seconds']} s warm. "
      "Stage seconds (cold): " + ", ".join(f"{k} {v['seconds']}" for k, v in cold["stages"].items()) + ".\n")
    P("Local compute/infrastructure cost: UNKNOWN (not measured; not treated as zero).\n")
    P("## ESTIMATE: scaled from the pilot (not measured)\n")
    P(f"Assumptions (editable): verify sample {a.verify_sample} reviews; base retry factor 1.0, conservative {a.conservative_retry}; "
      f"fallback fraction {a.fallback_fraction:.0%} at {a.fallback_cost_ratio}x enrich cost; budget ${a.budget}; workers {a.workers}, speedup {a.worker_speedup}x (assumed).\n")
    P("| Scenario | Reviews classified | Base cost | Conservative cost | Hours (base) | Budget check |\n|---|---|---|---|---|---|")
    scenarios = [("Full corpus, no exact-text reuse", FULL_NONEMPTY), ("Full corpus, exact-text reuse (484,189 distinct)", FULL_DISTINCT),
                 ("100,000-review sample", 100_000), ("10,000 checkpoint", 10_000)]
    if a.reviews:
        scenarios.append((f"Custom volume (--reviews {a.reviews})", a.reviews))
    for name, n in scenarios:
        base = project(m, summ, n, a.verify_sample, 1.0, 0.0, a.fallback_cost_ratio)
        cons = project(m, summ, n, a.verify_sample, a.conservative_retry, a.fallback_fraction, a.fallback_cost_ratio)
        h = hours(n, summ, runs, a.workers, a.worker_speedup, 1.0)
        warn = "OVER BUDGET" if cons["total"] > a.budget else ("base over budget" if base["total"] > a.budget else "within budget")
        P(f"| {name} | {n:,} | ${base['total']:.2f} | ${cons['total']:.2f} | {h:.1f} | {warn} |")
    r_out = float(rates["claude-haiku-5-5"]["output_usd_per_mtok"]) * a.rate_multiplier
    P(f"\nOutput-token cap control: at a cap of {a.output_token_cap} output tokens per review, the worst-case enrich output bill for all "
      f"{FULL_NONEMPTY:,} reviews is ${FULL_NONEMPTY * a.output_token_cap * r_out / 1e6:,.2f} (measured average in the pilot: {m['enrich']['output_tokens'] / summ['pilot_ids']:.0f} tokens per review).")
    P(f"\nAccounting: all {FULL_ROWS:,} rows are accounted for in any scenario; {FULL_EMPTY} empty texts are quarantined ('empty_review_text'); "
      "unclassified rows are reported as unfinished, never as successes.\n")
    P("Caveats: the first 100 reviews give an initial estimate only. Rare failures, sustained rate limits and duplicate-text reuse are not measured here. "
      "Group cost is scaled by complaint count and includes one-time menu-building overhead, so it is likely overstated at scale. "
      "Batch API discounts are NOT applied (hypothetical, not measured). The 100-review pilot was measured before the verifier and memo prompts were revised (verify-v2, memo-v2); it was not repeated, so the verify and memo stage costs here are from the earlier prompts.")
    text = "\n".join(L)
    print(text)
    if a.report:
        (COST / "report.md").write_text(text + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate-multiplier", type=float, default=1.0)
    ap.add_argument("--budget", type=float, default=9.11, help="USD available for the whole project (editable)")
    ap.add_argument("--verify-sample", type=int, default=1000)
    ap.add_argument("--conservative-retry", type=float, default=1.25)
    ap.add_argument("--fallback-fraction", type=float, default=0.05, help="declared max fraction sent to a stronger model")
    ap.add_argument("--fallback-cost-ratio", type=float, default=20.0, help="stronger-model cost vs Haiku per review (Sonnet/Haiku rate ratio)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--worker-speedup", type=float, default=4.0, help="ASSUMED speedup from parallel workers")
    ap.add_argument("--reviews", type=int, default=0, help="add a custom projected volume (measured pilot results do not change)")
    ap.add_argument("--output-token-cap", type=int, default=90, help="max output tokens per review the pipeline allows (code: 90 per review + 200 per request)")
    ap.add_argument("--report", action="store_true")
    main(ap.parse_args())
