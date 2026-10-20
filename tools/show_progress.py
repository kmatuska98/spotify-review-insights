"""Show saved progress of an enrich run and prove nothing already saved is paid for again.
No model calls.   python tools/show_progress.py work/live_demo

Run it right after the interruption (before resuming): it saves a snapshot of the completed IDs. Run it again after the resume:
it compares the IDs sent in resume calls against that snapshot.
"""
import json, sqlite3, sys
from pathlib import Path

run = Path(sys.argv[1])
snap_path = run / "completed_before_resume.json"
db = sqlite3.connect(run / "enrich.db")
completed = {r[0] for r in db.execute("SELECT review_id FROM results WHERE status='completed'")}
pending = db.execute("SELECT COUNT(*) FROM results WHERE status='pending'").fetchone()[0]
failed = db.execute("SELECT COUNT(*) FROM results WHERE status='failed'").fetchone()[0]
calls = [json.loads(x) for x in (run / "calls.jsonl").read_text(encoding="utf-8").splitlines()] if (run / "calls.jsonl").exists() else []
initial = [c for c in calls if c["phase"] == "initial"]
resume = [c for c in calls if c["phase"] == "resume"]

print(f"completed and saved on disk : {len(completed)}")
print(f"still pending               : {pending}" + (f"   (failed validation, will be retried on resume: {failed})" if failed else ""))
print(f"calls before interruption   : {len(initial)} (phase initial)")
print(f"calls after resume          : {len(resume)} (phase resume)")

if not resume:
    snap_path.write_text(json.dumps(sorted(completed)), encoding="utf-8")
    print(f"\nSnapshot saved: {len(completed)} completed IDs are on disk right now. Resume next, then run this again.")
elif snap_path.exists():
    before = set(json.loads(snap_path.read_text(encoding="utf-8")))
    resent = {i for c in resume for i in c["review_ids"]} & before
    print(f"\nCompleted before the interruption (snapshot) : {len(before)}")
    print(f"Completed now                                : {len(completed)}  (+{len(completed - before)} new)")
    print(f"Saved-before IDs sent AGAIN after resume     : {len(resent)}   (must be 0)")
    print(f"Snapshot is a strict subset of completed now : {before < completed}")
else:
    print("\nNo snapshot found (this script was not run before the resume), so the re-send check cannot be done for this folder.")
