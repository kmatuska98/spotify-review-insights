"""Show the two checkpoint snapshots from the real 100k-review run (no model calls).  python tools/show_checkpoints.py"""
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent / "grading"
before = set(json.loads((root / "checkpoint_before.json").read_text(encoding="utf-8"))["completed_ids"])
after = set(json.loads((root / "checkpoint_after.json").read_text(encoding="utf-8"))["completed_ids"])
print(f"checkpoint_before.json: {len(before):,} completed IDs saved before the interruption")
print(f"checkpoint_after.json : {len(after):,} completed IDs after resuming and finishing")
print(f"new work completed after resume: {len(after - before):,}")
print(f"before is a strict subset of after: {before < after}")
