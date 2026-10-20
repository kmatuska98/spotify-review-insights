"""Stage 3 - VERIFY. A different, stronger model re-labels a random sample BLIND: it sees only the
review text and the label definitions, never the first model's answer. Then code compares.

usage: python -m pipeline.verify --run-dir work/pilot --sample-size 50 --cap 0.50
"""
import argparse, hashlib, json, os, sqlite3, time, urllib.error
from pathlib import Path

from .check_key import load_env
from .common import ROOT
from .enrich import (Ledger, call_model, validate, system_prompt, LABEL_VERSION, SCHEMA_VERSION,
                     MAX_TEXT_CHARS)

VERIFY_MODEL = "claude-sonnet-5-5"
VERIFY_VERSION = "verify-v2"
SEED = "a5-verify-seed-1"

VERIFIER_PREFACE = (
    "ROLE: independent VERIFIER. You are auditing a labeling pipeline. You have NOT been shown any earlier label for these "
    "reviews and must not try to guess one. Read each review fresh and apply the definitions below strictly and literally; "
    "when the evidence is thin, prefer topic `other`, intent `unclear`, severity 1 and set needs_review=true rather than "
    "inferring facts. Respond ONLY by calling record_labels, with exactly one result per review id, and write no other text "
    "(no explanations, no preamble). Keep entities to a few short words.\n\n")


def verifier_prompt():
    """Separate instructions for the verify role: same label definitions, different role framing."""
    return VERIFIER_PREFACE + system_prompt().split("\n\n", 1)[1]


def pick_sample(enrich_db, label_config, n):
    """Deterministic random sample of completed ORIGINAL records (not cache aliases)."""
    rows = enrich_db.execute("SELECT review_id, text, record FROM results WHERE label_config=? AND status='completed' AND cache_source_id IS NULL", (label_config,)).fetchall()
    rows.sort(key=lambda r: hashlib.sha256((SEED + r[0]).encode()).hexdigest())
    return rows[:n]


def run(run_dir, n, cap, model, rates_path, batch_size=25):
    from .enrich import LABEL_CONFIG
    load_env()
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    run_dir = Path(run_dir)
    rates = json.loads(Path(rates_path).read_text(encoding="utf-8"))
    cfg = f"{model}+{LABEL_VERSION}+{VERIFY_VERSION}+{SCHEMA_VERSION}"
    ledger = Ledger(run_dir / "calls.jsonl", rates, cap, model)
    src = sqlite3.connect(run_dir / "enrich.db")
    vdb = sqlite3.connect(run_dir / "verify.db")
    vdb.execute("CREATE TABLE IF NOT EXISTS verify(review_id TEXT, config TEXT, record TEXT, PRIMARY KEY(review_id, config))")
    sample = pick_sample(src, LABEL_CONFIG, n)
    done = {r[0] for r in vdb.execute("SELECT review_id FROM verify WHERE config=?", (cfg,))}
    todo = [s for s in sample if s[0] not in done]
    new_calls, stopped = 0, None
    for i in range(0, len(todo), batch_size):
        chunk = {s[0]: s for s in todo[i:i + batch_size]}
        for attempt in range(2):
            if not chunk:
                break
            ids = list(chunk)
            items = [{"id": str(k + 1), "text": chunk[r][1][:MAX_TEXT_CHARS]} for k, r in enumerate(ids)]
            est_in = len(verifier_prompt()) // 3 + sum(len(x["text"]) for x in items) // 3 + 100
            max_out = 140 * len(ids) + 300
            if not ledger.allows(est_in, max_out):
                stopped = "spend_cap"; break
            started = time.time()
            entry = {"request_id": "", "role": "verify", "review_ids": ids, "model": model, "phase": "initial",
                     "outcome": "failed", "label_config": cfg, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
            got = []
            try:
                rid, resp = call_model(key, items, max_out, model, system=verifier_prompt())
                u = resp.get("usage", {})
                entry.update(request_id=rid or resp.get("id", ""), input_tokens=u.get("input_tokens", 0),
                             output_tokens=u.get("output_tokens", 0), outcome="succeeded")
                entry["cost_usd"] = ledger.cost(entry["input_tokens"], entry["output_tokens"])
                ledger.spent += entry["cost_usd"]
                blocks = [b for b in resp.get("content", []) if b.get("type") == "tool_use"]
                got = blocks[0]["input"].get("results", []) if blocks else []
            except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
                entry["note"] = f"HTTP {e.code}" if isinstance(e, urllib.error.HTTPError) else type(e).__name__
            entry["seconds"] = round(time.time() - started, 2)
            new_calls += 1
            with (run_dir / "calls.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            for it in got:
                real = ids[int(it["id"]) - 1] if str(it.get("id", "")).isdigit() and 1 <= int(it["id"]) <= len(ids) else None
                if real is None or real not in chunk:
                    continue
                clean, _ = validate(it, chunk[real][1])
                if clean:
                    vdb.execute("INSERT OR REPLACE INTO verify VALUES(?,?,?)", (real, cfg, json.dumps(clean, ensure_ascii=False)))
                    del chunk[real]
            vdb.commit()
        if stopped:
            break
    rep = report(run_dir, src, vdb, sample, cfg, model, new_calls, ledger, stopped)
    src.close(); vdb.close()
    return rep


def report(run_dir, src, vdb, sample, cfg, model, new_calls, ledger, stopped):
    rows, agree = [], {"topic": 0, "intent": 0, "severity": 0, "within1": 0, "all_three": 0}
    for rid, _, rec in sample:
        v = vdb.execute("SELECT record FROM verify WHERE review_id=? AND config=?", (rid, cfg)).fetchone()
        if not v:
            continue
        a, b = json.loads(rec), json.loads(v[0])
        same = {f: a[f] == b[f] for f in ("topic", "intent", "severity")}
        for f in same:
            agree[f] += same[f]
        agree["within1"] += abs(a["severity"] - b["severity"]) <= 1
        agree["all_three"] += all(same.values())
        rows.append({"review_id": rid, "enrich": {f: a[f] for f in same}, "verify": {f: b[f] for f in same}, "all_agree": all(same.values())})
    k = len(rows)
    rep = {"verify_model": model, "label_config": cfg, "sample_requested": len(sample), "verified": k,
           "agreement": {f: round(v / k, 3) for f, v in agree.items()} if k else {},
           "disagreements": [r for r in rows if not r["all_agree"]],
           "new_calls_this_invocation": new_calls, "total_spent_usd_in_run_dir": round(ledger.spent, 6), "stopped_early": stopped}
    (run_dir / "verification.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8", newline="\n")
    (run_dir / "verify_report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k2: v for k2, v in rep.items() if k2 != "disagreements"}), "| disagreements:", len(rep["disagreements"]))
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--sample-size", type=int, default=50)
    ap.add_argument("--cap", type=float, default=1.00, help="cumulative USD cap for the run dir (enrich + verify)")
    ap.add_argument("--model", default=VERIFY_MODEL)
    ap.add_argument("--rates", default=str(ROOT / "cost" / "rates.json"))
    a = ap.parse_args()
    run(a.run_dir, a.sample_size, a.cap, a.model, a.rates)
