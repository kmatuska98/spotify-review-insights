"""Regenerate the baseline ranking from SAVED outputs only. No model calls, no API key, no database.

  python -m pipeline.rerank --records grading/records.jsonl --membership grading/membership.csv --out ranking_rerun.csv --compare grading/ranking.csv

Rule (GRADING_CONTRACT.md): complaint/cancellation records only; priority_score = severity_sum = count x mean;
sort by score descending then issue_id ascending; mean exported to 6 decimals, half-up.
"""
import argparse, csv, gzip, json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


def opened(path):
    p = Path(path)
    return gzip.open(p, "rt", encoding="utf-8") if p.suffix == ".gz" else p.open(encoding="utf-8")


def rerank(records_path, membership_path):
    sev = {}
    with opened(records_path) as f:
        for line in f:
            r = json.loads(line)
            if r.get("status") == "completed" and r["intent"] in ("complaint", "cancellation"):
                sev[r["review_id"]] = r["severity"]
    groups = {}
    for row in csv.DictReader(opened(membership_path)):
        if row["review_id"] in sev:
            groups.setdefault(row["issue_id"], []).append(sev[row["review_id"]])
    rows = []
    for iid, v in groups.items():
        s, n = sum(v), len(v)
        rows.append({"issue_id": iid, "complaint_count": n, "severity_sum": s, "priority_score": s,
                     "mean_severity": str((Decimal(s) / Decimal(n)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))})
    rows.sort(key=lambda x: (-x["priority_score"], x["issue_id"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True)
    ap.add_argument("--membership", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--compare", help="existing ranking.csv; prints whether the rerun is identical")
    a = ap.parse_args()
    rows = rerank(a.records, a.membership)
    cols = ["rank", "issue_id", "complaint_count", "severity_sum", "mean_severity", "priority_score"]
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows({k: r[k] for k in cols} for r in rows)
    print(f"{len(rows)} issues ranked -> {a.out}")
    if a.compare:
        same = Path(a.compare).read_text(encoding="utf-8") == Path(a.out).read_text(encoding="utf-8")
        print("identical to", a.compare, ":", same)
