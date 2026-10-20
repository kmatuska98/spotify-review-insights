"""One command runs every stage on ANY input CSV (same columns as the course file), no chat pasting.

  prepare (ingest + profile) -> enrich -> verify -> group -> rank -> recommend (memo) -> grading/ export

Code owns dispatch, state, validation, budgets and arithmetic; models only read messy language
(enrich, verify, group naming/assignment, memo prose). Every stage saves its handoff in --run-dir and
is resumable: rerunning the same command skips finished work.

usage: python -m pipeline.run_all INPUT.csv --run-dir work/myrun --cap 5.00 --workers 4
"""
import argparse, json, shutil, time
from pathlib import Path

from . import enrich, verify, group, rank, memo, export_grading, ingest
from .common import ROOT, WORK


def main(a):
    run_dir = Path(a.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    rates = str(ROOT / "cost" / "rates.json")
    log, t_all = {}, time.time()

    def stage(name, fn):
        t = time.time()
        out = fn()
        log[name] = {"seconds": round(time.time() - t, 2)}
        return out

    if not a.skip_ingest:
        stage("prepare", lambda: ingest.ingest(a.input, str(run_dir / "ingest.db")))
        shutil.copyfile(WORK / "ingestion_report.json", run_dir / "ingestion_report.json")
    stage("enrich", lambda: enrich.run(a.input, run_dir, a.cap, a.batch_size, a.phase, None, rates, workers=a.workers))
    stage("verify", lambda: verify.run(run_dir, a.verify_sample, a.cap, verify.VERIFY_MODEL, rates))
    stage("group", lambda: group.run(run_dir, a.cap, rates, workers=a.workers))
    stage("rank", lambda: rank.compute(run_dir))
    facts = a.memo_facts or "Results cover the reviews the model classified from the supplied file; unclassified rows are not counted."
    stage("recommend", lambda: memo.run(run_dir, a.top, a.cap, rates, facts))
    stage("export", lambda: export_grading.export(run_dir, a.input, run_dir / "grading"))
    calls = [json.loads(x) for x in (run_dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    summary = {"input": str(a.input), "stages": log, "wall_seconds": round(time.time() - t_all, 2), "model_calls": len(calls),
               "failed_calls": sum(c["outcome"] == "failed" for c in calls), "api_cost_usd_logged": round(sum(c["cost_usd"] for c in calls), 6)}
    (run_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--cap", type=float, default=2.00, help="cumulative USD spend cap for this run dir")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--phase", choices=("initial", "resume"), default="initial")
    ap.add_argument("--verify-sample", type=int, default=50)
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--memo-facts", default="")
    ap.add_argument("--skip-ingest", action="store_true")
    main(ap.parse_args())
