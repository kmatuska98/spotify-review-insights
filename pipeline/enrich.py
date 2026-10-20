"""Stage 2 - ENRICH. Sends reviews to Claude Haiku in small batches, validates every answer,
saves after each batch, and stops before a spend cap is exceeded.

Cold pilot : python -m pipeline.enrich data/cost_100.csv --run-dir work/pilot --cap 1.00
Warm rerun : same command again (zero new calls: results are cached in the run dir)
Interrupt  : add --stop-after 2 (stops after 2 batches); rerun with --phase resume to finish.
"""
import argparse, json, os, random, sqlite3, threading, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .check_key import load_env
from .common import ROOT, TOPICS, INTENTS, csv_rows, row_sha, text_sha
from .labels import LABEL_VERSION, definitions_block, EXAMPLES

MODEL = "claude-haiku-5-5"
PROMPT_VERSION = "prompt-v1"
SCHEMA_VERSION = "schema-v1"
LABEL_CONFIG = f"{MODEL}+{LABEL_VERSION}+{PROMPT_VERSION}+{SCHEMA_VERSION}"
MAX_TEXT_CHARS = 3000   # longer texts are truncated in the prompt only; the source text is untouched
MAX_ATTEMPTS = 2        # per batch: first try plus ONE retry of invalid/missing items (assignment: retry invalid output once)
API_URL = "https://api.anthropic.com/v1/messages"

TOOL = {
    "name": "record_labels",
    "description": "Record one label set per review.",
    "input_schema": {"type": "object", "required": ["results"], "properties": {"results": {
        "type": "array", "items": {"type": "object",
            "required": ["id", "topic", "intent", "sentiment", "severity", "entities", "evidence_quote", "needs_review"],
            "properties": {
                "id": {"type": "string"},
                "topic": {"type": "string", "enum": list(TOPICS)},
                "intent": {"type": "string", "enum": list(INTENTS)},
                "sentiment": {"type": "number", "description": "-1 very negative to 1 very positive"},
                "severity": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                "entities": {"type": "array", "items": {"type": "string"}, "description": "Features/products named, may be empty"},
                "evidence_quote": {"type": "string", "description": "Exact substring of the review text"},
                "needs_review": {"type": "boolean"}}}}}},
}


def system_prompt():
    ex = "\n".join(json.dumps({"text": t, "topic": tp, "intent": it, "severity": sv, "evidence_quote": q})
                   for t, tp, it, sv, q in EXAMPLES)
    return ("You label Spotify app-store reviews. Call record_labels with exactly one result per review id.\n\n"
            + definitions_block() + "\n\nSYNTHETIC EXAMPLES (illustrative only):\n" + ex)


class Ledger:
    """Spend recorded in calls.jsonl; refuses a call whose worst case would pass the cap."""
    def __init__(self, calls_path, rates, cap, model=MODEL):
        self.path, self.cap, self.rate = Path(calls_path), cap, rates["models"][model]
        self.spent, self.reserved, self.lock = 0.0, 0.0, threading.Lock()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                self.spent += json.loads(line).get("cost_usd", 0.0)

    def cost(self, inp, out):
        return (inp * self.rate["input"] + out * self.rate["output"]) / 1e6

    def allows(self, est_in, max_out):
        return self.spent + self.cost(est_in, max_out) <= self.cap

    def reserve(self, est_in, max_out):
        """Hold worst-case cost before dispatch (safe with several workers). Returns the hold, or None if over cap."""
        with self.lock:
            hold = self.cost(est_in, max_out)
            if self.spent + self.reserved + hold > self.cap:
                return None
            self.reserved += hold
            return hold

    def settle(self, hold, actual):
        with self.lock:
            self.reserved -= hold
            self.spent += actual


def call_model(key, batch_items, max_out, model=MODEL, system=None):
    body = {"model": model, "max_tokens": max_out, "system": system or system_prompt(), "tools": [TOOL],
            # Sonnet 5.5 rejects forced tool use (HTTP 400), so only force it for Haiku; others get "auto"
            "tool_choice": {"type": "tool", "name": "record_labels"} if model == MODEL else {"type": "auto"},
            "messages": [{"role": "user", "content": "Reviews (JSON):\n" + json.dumps(batch_items, ensure_ascii=False)}]}
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.headers.get("request-id", ""), json.load(r)


def validate(item, text):
    """Return (clean_dict, None) or (None, reason)."""
    try:
        sev = item["severity"]
        ok = (item["topic"] in TOPICS and item["intent"] in INTENTS and isinstance(sev, int)
              and not isinstance(sev, bool) and 1 <= sev <= 5 and isinstance(item["entities"], list)
              and all(isinstance(e, str) for e in item["entities"]) and isinstance(item["needs_review"], bool)
              and isinstance(item["sentiment"], (int, float)) and -1 <= item["sentiment"] <= 1)
    except (KeyError, TypeError):
        return None, "malformed_item"
    if not ok:
        return None, "invalid_field_value"
    if not item["evidence_quote"] or item["evidence_quote"] not in text:
        return None, "evidence_not_exact_substring"
    return {k: item[k] for k in ("topic", "intent", "sentiment", "severity", "entities", "evidence_quote", "needs_review")}, None


def open_db(path):
    db = sqlite3.connect(path, check_same_thread=False)
    db.executescript("""CREATE TABLE IF NOT EXISTS results(
        review_id TEXT, label_config TEXT, source_sha256 TEXT, text_sha TEXT, text TEXT,
        status TEXT, reason TEXT, record TEXT, cache_source_id TEXT, PRIMARY KEY(review_id, label_config));
        CREATE INDEX IF NOT EXISTS ix_t ON results(text_sha, label_config);""")
    return db


def load_input(db, csv_path):
    rows = []
    for r in csv_rows(csv_path):
        empty = not r["review_text"].strip()
        rows.append((r["review_id"], LABEL_CONFIG, row_sha(r), text_sha(r["review_text"]), r["review_text"],
                     "quarantined" if empty else "pending", "empty_review_text" if empty else None, None, None))
    db.executemany("INSERT OR IGNORE INTO results VALUES(?,?,?,?,?,?,?,?,?)", rows)
    db.commit()
    return [r[0] for r in rows]


def fill_aliases(db):
    """Exact-duplicate texts reuse one validated original; every source ID keeps its own record."""
    n = 0
    for rid, th, sha in db.execute("SELECT review_id, text_sha, source_sha256 FROM results WHERE status IN ('pending','failed') AND label_config=?", (LABEL_CONFIG,)).fetchall():
        o = db.execute("SELECT review_id, record FROM results WHERE text_sha=? AND label_config=? AND status='completed' AND cache_source_id IS NULL LIMIT 1", (th, LABEL_CONFIG)).fetchone()
        if o:
            rec = dict(json.loads(o[1]), review_id=rid, source_sha256=sha, cache_source_id=o[0])
            db.execute("UPDATE results SET status='completed', reason=NULL, record=?, cache_source_id=? WHERE review_id=? AND label_config=?",
                       (json.dumps(rec, ensure_ascii=False), o[0], rid, LABEL_CONFIG))
            n += 1
    db.commit()
    return n


def run(csv_path, run_dir, cap, batch_size, phase, stop_after, rates_path, workers=1):
    load_env()
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    run_dir = Path(run_dir); run_dir.mkdir(parents=True, exist_ok=True)
    rates = json.loads(Path(rates_path).read_text(encoding="utf-8"))
    ledger = Ledger(run_dir / "calls.jsonl", rates, cap)
    db = open_db(run_dir / "enrich.db")
    load_input(db, csv_path)
    t0 = time.time()
    aliased = fill_aliases(db)   # warm path: reuse before spending anything

    queue = db.execute("""SELECT review_id, text, source_sha256, text_sha FROM results
        WHERE label_config=? AND status IN ('pending','failed') GROUP BY text_sha ORDER BY MIN(rowid)""", (LABEL_CONFIG,)).fetchall()
    batches = [queue[i:i + batch_size] for i in range(0, len(queue), batch_size)]
    stopped = None
    if stop_after is not None and len(batches) > stop_after:
        batches, stopped = batches[:stop_after], "stop_after"
    dblock, state = threading.Lock(), {"calls": 0, "cap": False, "stop": False}
    log_path = run_dir / "calls.jsonl"

    def process(batch):
        todo = {q[0]: q for q in batch}
        for attempt in range(MAX_ATTEMPTS):
            if not todo or state["cap"] or state["stop"]:
                break
            ids = list(todo)
            items = [{"id": str(n + 1), "text": todo[r][1][:MAX_TEXT_CHARS]} for n, r in enumerate(ids)]
            est_in = len(system_prompt()) // 3 + sum(len(x["text"]) for x in items) // 3 + 100
            max_out = 90 * len(ids) + 200
            hold = ledger.reserve(est_in, max_out)
            if hold is None:
                state["cap"] = True; break
            started = time.time()
            entry = {"request_id": "", "role": "enrich", "review_ids": ids, "model": MODEL, "phase": phase,
                     "outcome": "failed", "label_config": LABEL_CONFIG, "input_tokens": 0, "output_tokens": 0,
                     "cost_usd": 0.0, "seconds": 0.0, "attempt": attempt + 1}
            got, actual, wait = [], 0.0, 0
            try:
                rid_hdr, resp = call_model(key, items, max_out)
                u = resp.get("usage", {})
                entry.update(request_id=rid_hdr or resp.get("id", ""), input_tokens=u.get("input_tokens", 0),
                             output_tokens=u.get("output_tokens", 0), outcome="succeeded")
                actual = entry["cost_usd"] = ledger.cost(entry["input_tokens"], entry["output_tokens"])
                blocks = [b for b in resp.get("content", []) if b.get("type") == "tool_use"]
                got = blocks[0]["input"].get("results", []) if blocks else []
            except urllib.error.HTTPError as e:
                entry["note"] = f"HTTP {e.code}"
                wait = min(60, 5 * 2 ** attempt) if e.code in (429, 529) else min(30, 2 ** attempt)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                entry["note"] = f"{type(e).__name__}: unknown charge possible"
                actual = entry["cost_usd"] = hold   # unknown outcome: count the worst case, never undercount
                wait = min(30, 2 ** attempt)
            except (KeyError, ValueError) as e:
                entry["note"] = type(e).__name__
            ledger.settle(hold, actual)
            entry["seconds"] = round(time.time() - started, 2)
            with dblock:
                state["calls"] += 1
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                for it in got:
                    real = ids[int(it["id"]) - 1] if str(it.get("id", "")).isdigit() and 1 <= int(it["id"]) <= len(ids) else None
                    if real is None or real not in todo:
                        continue   # unknown or repeated id: ignored, never saved
                    clean, why = validate(it, todo[real][1])
                    if clean:
                        rec = dict(clean, review_id=real, source_sha256=todo[real][2], status="completed", label_config=LABEL_CONFIG)
                        db.execute("UPDATE results SET status='completed', reason=NULL, record=? WHERE review_id=? AND label_config=?",
                                   (json.dumps(rec, ensure_ascii=False), real, LABEL_CONFIG))
                        del todo[real]
                    else:
                        db.execute("UPDATE results SET status='failed', reason=? WHERE review_id=? AND label_config=?", (why, real, LABEL_CONFIG))
                db.commit()   # progress saved after every call
            if wait:
                time.sleep(wait + random.random())
        if state["stop"]:
            return   # user interrupt: leave unfinished reviews pending (not failed) so a resume picks them up
        with dblock:
            for real in todo:
                db.execute("UPDATE results SET status='failed', reason=COALESCE(reason,?) WHERE review_id=? AND label_config=? AND status!='completed'",
                           ("spend_cap_reached" if state["cap"] else "no_valid_answer", real, LABEL_CONFIG))
            db.commit()

    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        list(pool.map(process, batches))
        pool.shutdown()
    except KeyboardInterrupt:   # Ctrl+C: stop admitting work, let in-flight requests finish and be saved, then exit
        state["stop"] = True
        pool.shutdown(wait=True, cancel_futures=True)
        done = db.execute("SELECT COUNT(*) FROM results WHERE label_config=? AND status='completed'", (LABEL_CONFIG,)).fetchone()[0]
        print(f"INTERRUPTED. Progress is saved ({done} completed). Rerun the same command with --phase resume to continue.", flush=True)
        db.close()
        raise SystemExit(130)
    new_calls = state["calls"]
    if state["cap"]:
        stopped = "spend_cap"
    aliased += fill_aliases(db)
    export(db, csv_path, run_dir / "records.jsonl")
    counts = dict(db.execute("SELECT status, COUNT(*) FROM results WHERE label_config=? GROUP BY status", (LABEL_CONFIG,)).fetchall())
    summary = {"label_config": LABEL_CONFIG, "phase": phase, "new_calls_this_invocation": new_calls,
               "aliases_filled": aliased, "status_counts": counts, "total_spent_usd": round(ledger.spent, 6),
               "cap_usd": cap, "stopped_early": stopped, "wall_seconds": round(time.time() - t0, 2)}
    print(json.dumps(summary))
    db.close()
    return summary


def export(db, csv_path, out_path):
    """records.jsonl in source order: completed, quarantined, or failed (kept with its reason)."""
    out = []
    for r in csv_rows(csv_path):
        row = db.execute("SELECT status, reason, record, source_sha256 FROM results WHERE review_id=? AND label_config=?", (r["review_id"], LABEL_CONFIG)).fetchone()
        st, why, rec, sha = row
        if st == "completed":
            out.append(rec)
        else:
            out.append(json.dumps({"review_id": r["review_id"], "source_sha256": sha, "status": "quarantined" if st == "quarantined" else "failed",
                                   "reason": why or "not_processed"}, ensure_ascii=False))
    Path(out_path).write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--cap", type=float, default=1.00, help="max USD to spend in this run dir (cumulative)")
    ap.add_argument("--batch-size", type=int, default=25, help="reviews per request (max 50)")
    ap.add_argument("--phase", choices=("initial", "resume"), default="initial")
    ap.add_argument("--stop-after", type=int, default=None, help="stop after N batches (interruption demo)")
    ap.add_argument("--rates", default=str(ROOT / "cost" / "rates.json"))
    ap.add_argument("--workers", type=int, default=1, help="parallel requests (shared spend ledger)")
    a = ap.parse_args()
    if not 1 <= a.batch_size <= 50:
        raise SystemExit("batch size must be 1-50")
    run(a.input, a.run_dir, a.cap, a.batch_size, a.phase, a.stop_after, a.rates, a.workers)
