"""Build data/sample_<N>k.csv: the 10,000 development reviews + the golden 50 + a seeded random fill
of other NONEMPTY reviews from the full CSV, up to N rows. Deterministic (SHA-256 order, fixed seed).

usage: python tools/make_sample.py [N]
"""
import csv, hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.common import FIELDS, csv_rows  # noqa: E402

SEED = "a5-sample-seed-1"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000

must = {}
for name in ("analysis_10000.csv", "golden_50_to_label.csv"):
    for r in csv_rows(ROOT / "data" / name):
        must[r["review_id"]] = {k: r[k] for k in FIELDS}

pool = []
for r in csv_rows(ROOT / "data" / "spotify_reviews_18months.csv"):
    if r["review_id"] not in must and r["review_text"].strip():
        pool.append((hashlib.sha256((SEED + r["review_id"]).encode()).hexdigest(), {k: r[k] for k in FIELDS}))
pool.sort(key=lambda x: x[0])
rows = list(must.values()) + [p[1] for p in pool[: N - len(must)]]
rows.sort(key=lambda r: hashlib.sha256((SEED + r["review_id"]).encode()).hexdigest())

out = ROOT / "data" / f"sample_{N // 1000}k.csv"
with out.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
print(json.dumps({"rows": len(rows), "forced_in": len(must), "seed": SEED, "file": str(out.relative_to(ROOT))}))
