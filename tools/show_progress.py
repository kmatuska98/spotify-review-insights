"""Show saved progress of an enrich run: completed IDs on disk, calls by phase, and whether any ID was re-sent after resume.
No model calls.   python tools/show_progress.py work/live_demo
"""
import json, sqlite3, sys
from pathlib import Path

run = Path(sys.argv[1])
db = sqlite3.connect(run / "enrich.db")
completed = {r[0] for r in db.execute("SELECT review_id FROM results WHERE status='completed'")}
pending = db.execute("SELECT COUNT(*) FROM results WHERE status='pending'").fetchone()[0]
calls = [json.loads(x) for x in (run / "calls.jsonl").read_text(encoding="utf-8").splitlines()] if (run / "calls.jsonl").exists() else []
initial = [c for c in calls if c["phase"] == "initial"]
resume = [c for c in calls if c["phase"] == "resume"]
done_in_initial = {i for c in initial if c["outcome"] == "succeeded" for i in c["review_ids"]} & completed
resent = {i for c in resume for i in c["review_ids"]} & done_in_initial
print(f"completed and saved on disk : {len(completed)}")
print(f"still pending               : {pending}")
print(f"calls before interruption   : {len(initial)} (phase initial)")
print(f"calls after resume          : {len(resume)} (phase resume)")
print(f"IDs saved before the interruption and sent AGAIN after resume: {len(resent)}   (must be 0)")
