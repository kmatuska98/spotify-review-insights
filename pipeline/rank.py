"""Stage 5 - RANK. Pure code, no model calls. Baseline from data/GRADING_CONTRACT.md:

  complaint_count = members of the issue      severity_sum = sum of member severities
  mean_severity   = severity_sum / count      priority_score = severity_sum  (= count x mean)
  order: priority_score descending, then issue_id ascending. Means exported to 6 decimals, half-up.

usage: python -m pipeline.rank --run-dir work/c10000
"""
import argparse, csv, json, sqlite3
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .enrich import LABEL_CONFIG


def mean_string(total, n):
    return str((Decimal(total) / Decimal(n)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def compute(run_dir):
    run_dir = Path(run_dir)
    sev = {}
    db = sqlite3.connect(run_dir / "enrich.db")
    for rid, rec in db.execute("SELECT review_id, record FROM results WHERE label_config=? AND status='completed'", (LABEL_CONFIG,)):
        r = json.loads(rec)
        if r["intent"] in ("complaint", "cancellation"):
            sev[rid] = r["severity"]
    members = {}
    for iid, rid in sqlite3.connect(run_dir / "group.db").execute("SELECT issue_id, review_id FROM membership"):
        if rid in sev:
            members.setdefault(iid, []).append(sev[rid])
    rows = [{"issue_id": i, "complaint_count": len(v), "severity_sum": sum(v), "mean_severity": mean_string(sum(v), len(v)),
             "priority_score": sum(v)} for i, v in members.items()]
    rows.sort(key=lambda x: (-x["priority_score"], x["issue_id"]))
    for n, row in enumerate(rows, 1):
        row["rank"] = n
    cols = ["rank", "issue_id", "complaint_count", "severity_sum", "mean_severity", "priority_score"]
    with (run_dir / "ranking.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows({k: r[k] for k in cols} for r in rows)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    rows = compute(ap.parse_args().run_dir)
    print(len(rows), "ranked issues; top 5:")
    for r in rows[:5]:
        print(r)
