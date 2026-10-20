"""Dashboard BACKEND (FastAPI). Reads the processed-results SQLite database and serves it as JSON, plus the static dashboard.
It makes NO model calls and needs NO API key: the AI-generated recommendation was produced by the pipeline and is stored in the DB.

  local:   uvicorn dashboard.app:app --port 8000        (env DASHBOARD_DB=path/to/spotify.sqlite[.gz])
  deploy:  see render.yaml and README
"""
import gzip, json, os, shutil, sqlite3, tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

HERE = Path(__file__).resolve().parent
DB_ENV = os.environ.get("DASHBOARD_DB", str(HERE / "data" / "spotify.sqlite.gz"))


def resolve_db():
    """Use a plain .sqlite file, or unpack the committed .sqlite.gz once into a temp dir."""
    p = Path(DB_ENV)
    if p.suffix == ".gz":
        target = Path(tempfile.gettempdir()) / "spotify_dashboard.sqlite"
        if not target.exists() or target.stat().st_mtime < p.stat().st_mtime:
            with gzip.open(p, "rb") as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        return target
    return p


DB_PATH = resolve_db()
app = FastAPI(title="Spotify review insight dashboard API")


def q(sql, args=()):
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()


def meta(key, default=None):
    rows = q("SELECT value FROM meta WHERE key=?", (key,))
    return json.loads(rows[0]["value"]) if rows else default


@app.get("/api/health")
def health():
    return {"ok": True, "classified_reviews": q("SELECT COUNT(*) n FROM reviews")[0]["n"]}


@app.get("/api/overview")
def overview():
    total = q("SELECT COUNT(*) n, AVG(severity) s, SUM(needs_review) nr FROM reviews")[0]
    classified, source = meta("classified", 0), meta("source_rows", 0)
    complaints = q("SELECT COUNT(*) n, AVG(severity) s FROM reviews WHERE intent IN ('complaint','cancellation')")[0]
    return {
        "source_rows": source, "classified": classified, "classified_share_of_source": round(classified / source, 4) if source else None,
        "not_classified": source - classified,
        "complaint_or_cancellation": complaints["n"], "mean_severity_of_complaints": round(complaints["s"] or 0, 3),
        "needs_review": total["nr"], "ranked_issues": q("SELECT COUNT(*) n FROM ranking")[0]["n"],
        "by_topic": q("SELECT topic, COUNT(*) n FROM reviews GROUP BY topic ORDER BY n DESC"),
        "by_intent": q("SELECT intent, COUNT(*) n FROM reviews GROUP BY intent ORDER BY n DESC"),
        "by_severity": q("SELECT severity, COUNT(*) n FROM reviews GROUP BY severity ORDER BY severity"),
        "complaints_by_topic": q("SELECT topic, COUNT(*) n, ROUND(AVG(severity),3) mean_severity FROM reviews WHERE intent IN ('complaint','cancellation') GROUP BY topic ORDER BY n DESC"),
        "pipeline": {"model_calls": meta("model_calls"), "api_cost_usd": meta("api_cost_usd"), "calls_by_role": meta("calls_by_role"),
                     "verify": {k: meta("verify", {}).get(k) for k in ("verify_model", "verified", "agreement")},
                     "evaluation": meta("evaluation"), "notes": meta("notes")},
    }


@app.get("/api/ranking")
def ranking(limit: int = Query(50, ge=1, le=500)):
    return q("""SELECT r.rank, r.issue_id, i.name, i.topic, r.complaint_count, r.severity_sum, r.mean_severity, r.priority_score
                FROM ranking r JOIN issues i USING(issue_id) ORDER BY r.rank LIMIT ?""", (limit,))


@app.get("/api/issues/{issue_id}")
def issue(issue_id: str, limit: int = Query(15, ge=1, le=100)):
    row = q("""SELECT r.rank, r.issue_id, i.name, i.topic, i.description, r.complaint_count, r.severity_sum, r.mean_severity, r.priority_score
               FROM ranking r JOIN issues i USING(issue_id) WHERE r.issue_id=?""", (issue_id,))
    if not row:
        raise HTTPException(404, "unknown issue")
    ev = q("""SELECT review_id, text, rating, review_timestamp, intent, severity, evidence_quote, cache_source_id FROM reviews
              WHERE issue_id=? ORDER BY severity DESC, review_id LIMIT ?""", (issue_id, limit))
    dist = q("SELECT severity, COUNT(*) n FROM reviews WHERE issue_id=? GROUP BY severity ORDER BY severity", (issue_id,))
    return {**row[0], "severity_distribution": dist, "evidence": ev, "claims": q("SELECT * FROM claims WHERE issue_id=? ORDER BY claim_id", (issue_id,))}


@app.get("/api/reviews/{review_id}")
def review(review_id: str):
    rows = q("SELECT * FROM reviews WHERE review_id=?", (review_id,))
    if not rows:
        raise HTTPException(404, "review not in the classified set")
    r = rows[0]
    r["entities"] = json.loads(r["entities"])
    trace = {"issue": None, "rank": None}
    if r["issue_id"]:
        trace["issue"] = q("SELECT * FROM issues WHERE issue_id=?", (r["issue_id"],))[0]
        trace["rank"] = (q("SELECT * FROM ranking WHERE issue_id=?", (r["issue_id"],)) or [None])[0]
        trace["claims"] = q("SELECT * FROM claims WHERE issue_id=?", (r["issue_id"],))
    return {"review": r, "trace": trace}


@app.get("/api/recommendation")
def recommendation():
    """The stored AI-written memo plus each cited claim re-checked against the ranking table."""
    claims = q("SELECT c.claim_id, c.issue_id, c.metric, c.value, r.complaint_count, r.severity_sum, r.mean_severity, r.priority_score FROM claims c JOIN ranking r USING(issue_id)")
    for c in claims:
        c["matches_ranking"] = str(c[c["metric"]]) == c["value"]
        for k in ("complaint_count", "severity_sum", "mean_severity", "priority_score"):
            c.pop(k)
    return {"memo_markdown": meta("memo_markdown", ""), "claims": claims,
            "all_claims_match": all(c["matches_ranking"] for c in claims) if claims else None}


@app.get("/api/search")
def search(topic: str = "", intent: str = "", min_severity: int = 1, limit: int = Query(20, ge=1, le=100)):
    sql, args = "SELECT review_id, text, topic, intent, severity, issue_id FROM reviews WHERE severity>=?", [min_severity]
    if topic:
        sql += " AND topic=?"; args.append(topic)
    if intent:
        sql += " AND intent=?"; args.append(intent)
    return q(sql + " ORDER BY severity DESC, review_id LIMIT ?", args + [limit])


@app.exception_handler(sqlite3.Error)
def db_error(_, exc):
    return JSONResponse({"error": "database error", "detail": str(exc)[:200]}, status_code=500)


app.mount("/", StaticFiles(directory=HERE / "static", html=True), name="static")
