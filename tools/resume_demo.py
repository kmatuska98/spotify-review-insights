"""Interruption + resume demonstration (REAL model calls, about half a cent). Good to screen-record.

  python tools/resume_demo.py            writes evals/resume_demo_log.txt as well

Steps: (1) classify cost_100.csv in batches of 10 and STOP after 3 batches (simulated interruption, progress is on disk),
(2) show saved work, (3) rerun with --phase resume, (4) prove no completed ID was sent again and counts grew.
"""
import json, shutil, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import enrich  # noqa: E402

RUN = ROOT / "work" / "resume_demo"
CSV = ROOT / "data" / "cost_100.csv"
RATES = ROOT / "cost" / "rates.json"
lines = []


def say(msg=""):
    print(msg); lines.append(str(msg))


def done_ids():
    db = sqlite3.connect(RUN / "enrich.db")
    ids = {r[0] for r in db.execute("SELECT review_id FROM results WHERE status='completed'")}
    db.close()
    return ids


def calls():
    return [json.loads(x) for x in (RUN / "calls.jsonl").read_text(encoding="utf-8").splitlines()]


if RUN.exists():
    shutil.rmtree(RUN)
say("STEP 1: start run on cost_100.csv, batches of 10, interrupt after 3 batches")
s1 = enrich.run(CSV, RUN, 0.25, 10, "initial", 3, RATES)
before = done_ids()
n1 = len(calls())
say(f"INTERRUPTED. Saved on disk: {len(before)} completed IDs, {n1} model calls, spend ${s1['total_spent_usd']:.6f}")
say("\nSTEP 2: resume (same command, --phase resume). Completed IDs must not be sent again.")
s2 = enrich.run(CSV, RUN, 0.25, 10, "resume", None, RATES)
after = done_ids()
resent = {i for c in calls()[n1:] for i in c["review_ids"]} & before
say(f"RESUMED. Completed IDs now: {len(after)} (was {len(before)}); new calls: {len(calls()) - n1}; spend ${s2['total_spent_usd']:.6f}")
say(f"Completed-before IDs re-sent after resume: {len(resent)}   (must be 0)")
say(f"Checkpoint check: before is a strict subset of after: {before < after}")
say("\nSTEP 3: run again with nothing left to do (warm): new calls expected 0")
s3 = enrich.run(CSV, RUN, 0.25, 10, "resume", None, RATES)
say(f"New calls this time: {s3['new_calls_this_invocation']}")
assert not resent and before < after
(ROOT / "evals").mkdir(exist_ok=True)
(ROOT / "evals" / "resume_demo_log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
