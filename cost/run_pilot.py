"""EXPLICIT PILOT EXECUTION (makes paid API calls). Runs the whole chain on data/cost_100.csv with ONE worker
and records wall-clock time, calls and spend per stage. Run it twice with the same --run-dir:
first run = cold (empty cache), second run = warm (cached; should make zero new calls).

usage: python cost/run_pilot.py --label cold --run-dir work/pilot_final
       python cost/run_pilot.py --label warm --run-dir work/pilot_final
Importing this file does nothing; offline replay is cost/calculator.py (no API key needed).
"""
import argparse, json, sys, time, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import enrich, verify, group, rank, memo  # noqa: E402

CSV = ROOT / "data" / "cost_100.csv"
RATES = ROOT / "cost" / "rates.json"
VERIFY_SAMPLE = 20


def snapshot(run_dir):
    p = Path(run_dir) / "calls.jsonl"
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []
    return rows


def main(label, run_dir, cap):
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"{label}-{uuid.uuid4().hex[:8]}"
    stages = [("enrich", lambda: enrich.run(CSV, run_dir, cap, 25, "initial", None, RATES, workers=1)),
              ("verify", lambda: verify.run(run_dir, VERIFY_SAMPLE, cap, verify.VERIFY_MODEL, RATES)),
              ("group", lambda: group.run(run_dir, cap, RATES, workers=1)),
              ("rank", lambda: rank.compute(run_dir)),
              ("memo", lambda: memo.run(run_dir, 5, cap, RATES, "The pilot classified 100 sample reviews; the memo is illustrative."))]
    t_all, out = time.time(), {"run_id": run_id, "label": label, "stages": {}}
    for name, fn in stages:
        before, t = len(snapshot(run_dir)), time.time()
        fn()
        new = snapshot(run_dir)[before:]
        out["stages"][name] = {"seconds": round(time.time() - t, 2), "new_calls": len(new),
                               "failed_calls": sum(c["outcome"] == "failed" for c in new),
                               "input_tokens": sum(c["input_tokens"] for c in new), "output_tokens": sum(c["output_tokens"] for c in new),
                               "cost_usd": round(sum(c["cost_usd"] for c in new), 6)}
    out["wall_seconds"] = round(time.time() - t_all, 2)
    out["total_cost_usd"] = round(sum(s["cost_usd"] for s in out["stages"].values()), 6)
    with (ROOT / "cost" / "pilot_runs.jsonl").open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(out) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", choices=("cold", "warm"), required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--cap", type=float, default=1.00)
    a = ap.parse_args()
    main(a.label, a.run_dir, a.cap)
