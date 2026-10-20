"""Copy the SAVED outputs of the final run into results/ (small files only), and write quarantine log + run summary.
No model calls.   python tools/package_results.py --run-dir work/c10000
"""
import argparse, gzip, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results"


def main(run_dir):
    run_dir = Path(run_dir)
    OUT.mkdir(exist_ok=True)
    for name in ("issues.json", "group_report.json", "verify_report.json", "verification.jsonl", "memo_report.json", "ranking.csv", "claims.csv", "memo.md", "membership.csv"):
        shutil.copyfile(run_dir / name, OUT / name)
    shutil.copyfile(ROOT / "work" / "ingestion_report.json", OUT / "ingestion_report.json")
    shutil.copyfile(ROOT / "data" / "manifest.json", OUT / "data_manifest.json")

    # quarantine log: every non-completed record with its reason (gzip: ~560k "not attempted" rows)
    counts, n = {}, 0
    with gzip.open(ROOT / "grading" / "records.jsonl.gz", "rt", encoding="utf-8") as src, gzip.open(OUT / "quarantine.jsonl.gz", "wt", encoding="utf-8", newline="\n") as dst:
        for line in src:
            r = json.loads(line)
            if r["status"] != "completed":
                dst.write(line); n += 1
                counts[r["reason"]] = counts.get(r["reason"], 0) + 1

    calls = [json.loads(x) for x in (ROOT / "grading" / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    by = {}
    for c in calls:
        a = by.setdefault((c["role"], c["model"], c["phase"]), {"calls": 0, "failed": 0, "input_tokens": 0, "output_tokens": 0, "usd": 0.0, "seconds": 0.0})
        a["calls"] += 1; a["failed"] += c["outcome"] == "failed"
        a["input_tokens"] += c["input_tokens"]; a["output_tokens"] += c["output_tokens"]
        a["usd"] += c.get("cost_usd", 0.0); a["seconds"] += c.get("seconds", 0.0)
    attempts = {}
    for c in calls:
        if c["role"] == "enrich":
            attempts[c.get("attempt", 1)] = attempts.get(c.get("attempt", 1), 0) + 1
    summary = {
        "final_run_dir": "work/c10000 (not committed: contains large SQLite working files)",
        "source_rows": 660622, "quarantined_not_completed": n, "quarantine_reasons": counts,
        "classified": 660622 - n, "classified_fraction_of_labelable": round((660622 - n) / 660609, 6),
        "model_calls_logged": len(calls), "failed_calls": sum(c["outcome"] == "failed" for c in calls),
        "api_cost_usd_logged": round(sum(c.get("cost_usd", 0.0) for c in calls), 4),
        "enrich_calls_by_attempt_number": attempts,
        "stages": [{"role": k[0], "model": k[1], "phase": k[2], **{kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in a.items()}} for k, a in sorted(by.items())],
        "notes": ["Costs are computed from logged token usage and cost/rates.json; reconcile with the provider's usage dashboard.",
                  "Run used up to 3 attempts per batch before the retry limit was reduced to 2; " + str(attempts.get(3, 0)) + " enrich calls were a third attempt.",
                  "Wall time is the sum of per-call seconds across overlapping workers, not elapsed time."]}
    (OUT / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: summary[k] for k in ("quarantined_not_completed", "classified", "model_calls_logged", "failed_calls", "api_cost_usd_logged", "enrich_calls_by_attempt_number")}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default=str(ROOT / "work" / "c10000"))
    main(ap.parse_args().run_dir)
