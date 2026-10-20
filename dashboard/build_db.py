"""Load PROCESSED pipeline outputs into the dashboard's SQLite database (no model calls).

  python dashboard/build_db.py --run-dir work/c10000 --input data/sample_100k.csv --out dashboard/data/spotify.sqlite

Tables: reviews (classified records + source metadata + issue), issues, ranking, claims, meta (memo, coverage,
verifier, golden, cost). The backend (dashboard/app.py) only ever READS this database.
"""
import argparse, csv, json, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.common import csv_rows  # noqa: E402
from pipeline.enrich import LABEL_CONFIG  # noqa: E402

SCHEMA = """
CREATE TABLE reviews(review_id TEXT PRIMARY KEY, text TEXT, rating TEXT, review_timestamp TEXT, topic TEXT, intent TEXT,
  sentiment REAL, severity INTEGER, evidence_quote TEXT, needs_review INTEGER, entities TEXT, cache_source_id TEXT,
  label_config TEXT, issue_id TEXT);
CREATE INDEX ix_issue ON reviews(issue_id); CREATE INDEX ix_topic ON reviews(topic); CREATE INDEX ix_intent ON reviews(intent);
CREATE TABLE issues(issue_id TEXT PRIMARY KEY, topic TEXT, name TEXT, description TEXT, catch_all INTEGER);
CREATE TABLE ranking(rank INTEGER, issue_id TEXT PRIMARY KEY, complaint_count INTEGER, severity_sum INTEGER, mean_severity TEXT, priority_score INTEGER);
CREATE TABLE claims(claim_id TEXT PRIMARY KEY, issue_id TEXT, metric TEXT, value TEXT);
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
"""
TEXT_LIMIT = 700   # review text kept for traceability (truncated for size; full text stays in the source CSV)


def read_text(path, default=""):
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else default


def build(run_dir, input_csv, out, source_rows, extra_meta):
    run_dir, out = Path(run_dir), Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    db = sqlite3.connect(out)
    db.executescript(SCHEMA)

    src = {r["review_id"]: r for r in csv_rows(input_csv)}
    edb = sqlite3.connect(run_dir / "enrich.db")
    member = dict(sqlite3.connect(run_dir / "group.db").execute("SELECT review_id, issue_id FROM membership"))
    batch, n_done, n_failed = [], 0, 0
    for rid, status, rec, alias in edb.execute("SELECT review_id, status, record, cache_source_id FROM results WHERE label_config=?", (LABEL_CONFIG,)):
        if status != "completed":
            n_failed += status == "failed"
            continue
        r, s = json.loads(rec), src.get(rid, {})
        n_done += 1
        batch.append((rid, s.get("review_text", "")[:TEXT_LIMIT], s.get("review_rating", ""), s.get("review_timestamp", ""), r["topic"], r["intent"],
                      r["sentiment"], r["severity"], r["evidence_quote"][:TEXT_LIMIT], int(r["needs_review"]), json.dumps(r["entities"], ensure_ascii=False),
                      alias, r["label_config"], member.get(rid) if r["intent"] in ("complaint", "cancellation") else None))
        if len(batch) >= 5000:
            db.executemany("INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch); batch = []
    db.executemany("INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)

    tax = json.loads((run_dir / "issues.json").read_text(encoding="utf-8"))["issues"]
    db.executemany("INSERT INTO issues VALUES(?,?,?,?,?)", [(i["issue_id"], i["topic"], i["name"], i["description"], int(bool(i.get("catch_all")))) for i in tax])
    for r in csv.DictReader((run_dir / "ranking.csv").open(encoding="utf-8")):
        db.execute("INSERT INTO ranking VALUES(?,?,?,?,?,?)", (r["rank"], r["issue_id"], r["complaint_count"], r["severity_sum"], r["mean_severity"], r["priority_score"]))
    for r in csv.DictReader((run_dir / "claims.csv").open(encoding="utf-8")):
        db.execute("INSERT INTO claims VALUES(?,?,?,?)", (r["claim_id"], r["issue_id"], r["metric"], r["value"]))

    calls = [json.loads(x) for x in (run_dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    by_role = {}
    for c in calls:
        a = by_role.setdefault(c["role"], {"calls": 0, "failed": 0, "input_tokens": 0, "output_tokens": 0, "usd": 0.0})
        a["calls"] += 1; a["failed"] += c["outcome"] == "failed"
        a["input_tokens"] += c["input_tokens"]; a["output_tokens"] += c["output_tokens"]; a["usd"] += c["cost_usd"]
    meta = {"source_rows": source_rows, "classified": n_done, "failed_validation": n_failed,
            "memo_markdown": read_text(run_dir / "memo.md"), "calls_by_role": by_role, "model_calls": len(calls),
            "api_cost_usd": round(sum(c["cost_usd"] for c in calls), 4),
            "verify": json.loads(read_text(run_dir / "verify_report.json", "{}")), **extra_meta}
    for k, v in meta.items():
        db.execute("INSERT INTO meta VALUES(?,?)", (k, json.dumps(v, ensure_ascii=False)))
    db.commit()
    db.execute("VACUUM")
    db.close()
    print(json.dumps({"db": str(out), "classified_reviews": n_done, "issues": len(tax), "size_mb": round(out.stat().st_size / 1e6, 1)}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--input", required=True, help="the CSV that was classified (for source text and metadata)")
    ap.add_argument("--out", default=str(ROOT / "dashboard" / "data" / "spotify.sqlite"))
    ap.add_argument("--source-rows", type=int, default=660_622)
    ap.add_argument("--extra-meta", default="", help="path to a JSON file merged into meta (golden results, notes)")
    a = ap.parse_args()
    extra = json.loads(Path(a.extra_meta).read_text(encoding="utf-8")) if a.extra_meta else {}
    build(a.run_dir, a.input, a.out, a.source_rows, extra)
