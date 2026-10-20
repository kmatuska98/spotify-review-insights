"""Stage 1 - PREPARE. No model calls. Reads every row, hashes it, profiles quality,
finds exact-duplicate texts, and loads everything into a SQLite work database.

usage: python -m pipeline.ingest INPUT.csv [--db work/pipeline.db]
"""
import argparse, sqlite3, time
from collections import Counter
from .common import ROOT, WORK, csv_rows, row_sha, text_sha, atomic_write_json

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews(
  review_id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL, review_text TEXT NOT NULL,
  review_rating TEXT, review_likes TEXT, app_version TEXT, review_timestamp TEXT,
  text_sha TEXT NOT NULL, status TEXT NOT NULL, reason TEXT);
CREATE INDEX IF NOT EXISTS ix_text ON reviews(text_sha);
"""


def ingest(src, db_path):
    t0 = time.time()
    WORK.mkdir(exist_ok=True)
    db = sqlite3.connect(db_path)
    db.executescript(SCHEMA)
    ids, months, ratings = set(), Counter(), Counter()
    c = Counter()
    batch = []
    for row in csv_rows(src):
        c["records"] += 1
        if row["review_id"] in ids:
            c["duplicate_review_ids"] += 1
            continue
        ids.add(row["review_id"])
        empty = not row["review_text"].strip()
        c["empty_review_text"] += empty
        c["missing_app_version"] += not row["app_version"].strip()
        months[row["review_timestamp"][:7]] += 1
        ratings[row["review_rating"]] += 1
        batch.append((row["review_id"], row_sha(row), row["review_text"], row["review_rating"],
                      row["review_likes"], row["app_version"], row["review_timestamp"],
                      text_sha(row["review_text"]), "quarantined" if empty else "pending",
                      "empty_review_text" if empty else None))
        if len(batch) >= 20000:
            db.executemany("INSERT OR IGNORE INTO reviews VALUES(?,?,?,?,?,?,?,?,?,?)", batch); batch = []
    db.executemany("INSERT OR IGNORE INTO reviews VALUES(?,?,?,?,?,?,?,?,?,?)", batch)
    db.commit()
    nonempty = db.execute("SELECT COUNT(*) FROM reviews WHERE status='pending'").fetchone()[0]
    distinct = db.execute("SELECT COUNT(DISTINCT text_sha) FROM reviews WHERE status='pending'").fetchone()[0]
    dup_groups = db.execute("SELECT COUNT(*) FROM (SELECT text_sha FROM reviews WHERE status='pending' GROUP BY text_sha HAVING COUNT(*)>1)").fetchone()[0]
    report = {"source_file": str(src), "rows_read": c["records"], "rows_in_db": len(ids),
              "counts": dict(c), "nonempty_pending": nonempty, "distinct_nonempty_texts": distinct,
              "texts_that_repeat": dup_groups, "reviews_by_month": dict(sorted(months.items())),
              "reviews_by_rating": dict(sorted(ratings.items())), "seconds": round(time.time() - t0, 1)}
    atomic_write_json(WORK / "ingestion_report.json", report)
    print(report["counts"], "pending", nonempty, "distinct", distinct, "repeating texts", dup_groups, report["seconds"], "s")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--db", default=str(WORK / "pipeline.db"))
    a = ap.parse_args()
    ingest(a.input, a.db)
