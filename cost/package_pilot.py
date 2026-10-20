"""Copy the MEASURED pilot evidence from work/pilot_final into cost/ (no API calls).

Writes: pilot_records.jsonl, pilot_calls.jsonl (with run id + stage), usage.csv, rates.csv, pilot_summary.json
usage: python cost/package_pilot.py [--run-dir work/pilot_final]
"""
import argparse, csv, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COST = ROOT / "cost"
STAGE = {"enrich": "enrich", "verify": "verify", "group": "group", "memo": "memo"}


def main(run_dir):
    run_dir = Path(run_dir)
    runs = [json.loads(x) for x in (COST / "pilot_runs.jsonl").read_text(encoding="utf-8").splitlines()]
    cold = next(r for r in runs if r["label"] == "cold")
    warm = [r for r in runs if r["label"] == "warm"][-1]
    shutil.copyfile(run_dir / "records.jsonl", COST / "pilot_records.jsonl")

    calls = [json.loads(x) for x in (run_dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    with (COST / "pilot_calls.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for i, c in enumerate(calls):
            c = dict(c, run_id=cold["run_id"], stage=STAGE[c["role"]])
            c["request_id"] = c["request_id"] or f"local-{i:06d}"
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    rates = json.loads((COST / "rates.json").read_text(encoding="utf-8"))
    with (COST / "rates.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["model", "input_usd_per_mtok", "output_usd_per_mtok", "batch_input_usd_per_mtok", "batch_output_usd_per_mtok", "source_url", "checked_on"])
        for m, r in rates["models"].items():
            w.writerow([m, r["input"], r["output"], r["batch_input"], r["batch_output"], rates["source"], rates["checked_on"]])

    pl = json.loads((run_dir / "group_report.json").read_text(encoding="utf-8"))
    recs = [json.loads(x) for x in (run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()]
    done = [r for r in recs if r["status"] == "completed"]
    texts = {c["review_id"]: 1 for c in done}
    summary = {"pilot_ids": len(recs), "completed": len(done), "failed_or_quarantined": len(recs) - len(done),
               "complaint_or_cancellation_records": pl["eligible_records"],
               "complaint_share": round(pl["eligible_records"] / max(1, len(done)), 4),
               "verify_sample": 20, "cold_run": cold["run_id"], "cold_wall_seconds": cold["wall_seconds"],
               "warm_run": warm["run_id"], "warm_wall_seconds": warm["wall_seconds"],
               "warm_new_calls": sum(s["new_calls"] for s in warm["stages"].values()), "warm_cost_usd": warm["total_cost_usd"]}
    (COST / "pilot_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")

    # usage.csv: one row per (stage, model) with raw provider usage from the cold run
    agg = {}
    for c in calls:
        k = (c["role"], c["model"])
        a = agg.setdefault(k, {"requests": 0, "failed": 0, "in": 0, "out": 0, "sec": 0.0})
        a["requests"] += 1; a["failed"] += c["outcome"] == "failed"
        a["in"] += c["input_tokens"]; a["out"] += c["output_tokens"]; a["sec"] += c.get("seconds", 0)
    with (COST / "usage.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["run_id", "stage", "model", "requests", "failed_requests", "input_tokens", "output_tokens", "summed_request_seconds", "source"])
        for (role, model), a in agg.items():
            w.writerow([cold["run_id"], role, model, a["requests"], a["failed"], a["in"], a["out"], round(a["sec"], 2), "cost/pilot_calls.jsonl"])
    print(json.dumps(summary))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default=str(ROOT / "work" / "pilot_final"))
    main(Path(ap.parse_args().run_dir))
