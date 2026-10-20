"""Build the grading/ folder from a run directory (see data/GRADING_CONTRACT.md).

Every source ID of the FULL CSV gets exactly one record:
  completed    - labeled by the model (or an exact-duplicate text reusing a direct original via cache_source_id)
  quarantined  - empty text, a validation failure, or "not_attempted_budget_limit" (never labeled)
ingestion.json is made separately with the provided helper (tools/check_submission.py profile).

usage: python -m pipeline.export_grading --run-dir work/c10000 --full data/spotify_reviews_18months.csv --out grading
"""
import argparse, csv, hashlib, json, shutil, sqlite3
from pathlib import Path

from .common import csv_rows, row_sha
from .enrich import LABEL_CONFIG


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def export(run_dir, full_csv, out):
    run_dir, out = Path(run_dir), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(run_dir / "enrich.db")
    res = {r[0]: r[1:] for r in db.execute("SELECT review_id, status, reason, record, cache_source_id FROM results WHERE label_config=?", (LABEL_CONFIG,))}
    # an unlabeled duplicate whose representative text failed validation inherits that failure reason
    rep_fail = dict(db.execute("SELECT text_sha, reason FROM results WHERE label_config=? AND status='failed' GROUP BY text_sha", (LABEL_CONFIG,)).fetchall())
    sha_of = dict(db.execute("SELECT review_id, text_sha FROM results WHERE label_config=? AND status='pending'", (LABEL_CONFIG,)).fetchall())
    for rid, th in sha_of.items():
        if th in rep_fail:
            res[rid] = ("pending", "duplicate_of_failed_text:" + str(rep_fail[th]), None, None)

    n_rows = n_done = n_alias = 0
    reasons = {}
    completed_ids, original_ids = [], []
    with (out / "records.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for r in csv_rows(full_csv):
            n_rows += 1
            rid, sha = r["review_id"], row_sha(r)
            st, why, rec, src = res.get(rid, (None, None, None, None))
            if st == "completed":
                d = json.loads(rec)
                d["entities"] = [e for e in d["entities"] if e.strip()]
                d["source_sha256"] = sha
                out_row = d
                n_done += 1
                completed_ids.append(rid)
                if src:
                    n_alias += 1
                else:
                    original_ids.append(rid)
            else:
                reason = why or ("empty_review_text" if not r["review_text"].strip() else "not_attempted_budget_limit")
                reasons[reason] = reasons.get(reason, 0) + 1
                out_row = {"review_id": rid, "source_sha256": sha, "status": "quarantined", "reason": reason}
            f.write(json.dumps(out_row, ensure_ascii=False) + "\n")

    # calls.jsonl: every attempt, with a local id where the provider gave none (failed attempts)
    resume_ids, calls = set(), []
    for i, line in enumerate((run_dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()):
        d = json.loads(line)
        if not d.get("request_id"):
            d["request_id"] = f"local-{i:06d}"
        if d["role"] == "enrich" and d["phase"] == "resume" and d["outcome"] == "succeeded" and d["label_config"] == LABEL_CONFIG:
            resume_ids.update(d["review_ids"])
        calls.append(d)
    with (out / "calls.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        f.writelines(json.dumps(c, ensure_ascii=False) + "\n" for c in calls)

    # resume evidence: "before" = originals finished before the interruption (never re-sent in resume calls)
    before = [i for i in original_ids if i not in resume_ids]
    (out / "checkpoint_before.json").write_text(json.dumps({"completed_ids": before}), encoding="utf-8", newline="\n")
    (out / "checkpoint_after.json").write_text(json.dumps({"completed_ids": completed_ids}), encoding="utf-8", newline="\n")

    for name in ("membership.csv", "ranking.csv", "claims.csv", "memo.md"):
        shutil.copyfile(run_dir / name, out / name)
    (out / "run.json").write_text(json.dumps({"version": "a5-audit-v1", "analysis_count": n_rows, "analysis_sha256": file_sha(full_csv),
        "classification_input_fields": ["review_text"], "allow_multi_issue": False}) + "\n", encoding="utf-8", newline="\n")
    summary = {"source_rows": n_rows, "completed": n_done, "of_which_cache_reuse": n_alias, "quarantined_by_reason": reasons,
               "checkpoint_before": len(before), "checkpoint_after": len(completed_ids), "calls": len(calls)}
    print(json.dumps(summary))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--full", required=True)
    ap.add_argument("--out", default="grading")
    a = ap.parse_args()
    export(a.run_dir, a.full, a.out)
