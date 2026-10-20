# Spotify review insight pipeline

Where should the next quarter of Spotify product effort go? This repo is a multi-role AI pipeline over the 660,622-review course extract, plus a deployed dashboard.
**Read "Scope and honest limits" first:** the final run classified **104,975 of 660,609** nonempty reviews (**15.9%**, a seeded random sample). The other reviews are accounted for and quarantined as `not_attempted_budget_limit`; they were never labeled and are not counted in any result.

- **Live dashboard:** https://spotify-review-insights-dpkl.onrender.com (free Render instance: if it has been idle, the first load can take about a minute to wake up)
- **Access instructions:** public, no login. Click an issue row to see its source reviews; click a `C0x-...` chip in the recommendation to open the cited issue; paste a review ID into "Trace a review".
- Setup, commands and file map are below. Offline replay and ranking need **no API key**.

## Results summary

| Item | Value | Evidence |
|---|---|---|
| Source rows accounted for (one record each) | 660,622 | `grading/records.jsonl.gz`, `grading/ingestion.json` |
| Empty texts quarantined (`empty_review_text`) | 13 | `results/quarantine.jsonl.gz` |
| Classified (completed) | 104,975 (15.89% of 660,609 nonempty) | `results/run_summary.json` |
| Of those, exact-duplicate text reuse (`cache_source_id`) | 23,134 (no model call; every ID kept as its own record) | `grading/records.jsonl.gz` |
| Failed validation (kept with reason) | 25 (24 `evidence_not_exact_substring`, 1 `malformed_item`) | quarantine log |
| Not attempted (budget) | 555,609 | quarantine log |
| Official checker (`tools/check_submission.py`) | status `review_required`; **only** issue is `unfinished_classification` (555,634); coverage candidate 0.4953 | `python tools/check_submission.py check ...` (below) |
| Model calls (final run dir) | 3,022 logged, 5 failed, **$6.14** logged API cost (includes one wasted verifier attempt, see `evals/error_analysis.md` section 4) | `grading/calls.jsonl`, `results/run_summary.json` |
| Golden-50 agreement, first run (before any rule revision) | topic 78%, intent 90%, severity exact 88% (within 1: 100%) | `evals/golden_report_v1_untuned.md` |
| Held-out 20 (fresh, after rules were set) | topic 90%, intent 85%, severity exact 80% (within 1: 100%) | `evals/heldout_report.md` |
| Blind verifier (Sonnet 5.5), 200 reviews | topic 84.5%, intent 90%, severity exact 83.5%, all three 69% | `results/verify_report.json` |
| 100-review pilot (cold / warm) | 82.3 s and $0.0654 / 0.05 s, 0 calls, $0 | `cost/report.md`, `cost/pilot_runs.jsonl` |
| Tests | 10 offline tests pass (planted bad outputs, wrong label, spend cap, resume, rate-limit and timeout recovery, injection handling); 6/6 real-model injection cases pass | `tests/`, `evals/run_injection_test.py` |

Measured results are in the tables above; anything labeled *estimate* (calculator projections, full-corpus cost) is not a measurement.

## Scope and honest limits

- **Partial classification.** Budget was about $10 of API credit. A full 660,609-review run was estimated at roughly $25+ for enrichment alone, so I classified a **seeded random 105,000-review sample** (`tools/make_sample.py 105000`; it includes the 10,000 development reviews and the golden 50; 104,975 completed and 25 failed validation). The first run completed 99,970, just under the 100,000 floor, so I extended the same sample by 5,000. This meets the "at least 100,000" allowance, but the coverage point is proportional, and conclusions describe only the sample. Reviews are self-selected; cancellation language is intent, not observed churn; there is no revenue or plan data, and no revenue-at-risk claim is made.
- **Golden set was used to revise rules.** I ran the golden 50 first (`labels-v1`, clean result above), then read the disagreements and revised the label rules (`labels-v2`, `pipeline/labels.py`) using general wording and *new synthetic examples only*; no golden text or label is in any prompt. The `labels-v2` golden numbers (`evals/golden_report_v2_tuned.md`: topic 80%, intent 92%, severity 88%) are therefore **not held-out**. A fresh held-out set was labeled afterwards (20 reviews); see "Held-out check" below for its results.
- **Two golden labels differ from the grading contract on purpose.** I labeled two "premium-only controls" reviews as `usability`; the contract says premium-only controls are `billing`. The pipeline follows the contract. The golden file is untouched, so those two count as disagreements.
- **Pilot prompt versions.** The 100-review cold/warm pilot was measured before the verifier and memo prompts were revised (`verify-v2`, `memo-v2`) and was not repeated; the calculator says so.
- **Retries.** The spec allows one retry of invalid output. The run began with up to 3 attempts per batch; 56 enrich calls were a third attempt. I then reduced `MAX_ATTEMPTS` to 2.
- **Verification is a sample**, and agreement between two models is not accuracy. The verifier disagreed with the labeler on 31% of the 200 reviews (62) on at least one field (field-level: topic 31, severity 33, intent 20). The largest single patterns are `usability` vs `billing` topic (8 cases, the premium-gating boundary) and severity 2 vs 3 (12 cases). Severity was within 1 point in 99.5% of reviews (one case differed by 2).
- **The top-ranked issue is generic.** "General hate and uninstall requests" ranks #1 by the required formula but is vague (no specific fix); the memo says so and ranks actionable issues first. The ranking is the required baseline; the memo is the judgment layer.
- Issue menus are per topic, so a theme such as "premium gating" appears under both `billing` and `usability` issues; counts are not merged.
- Cost figures are computed from logged token usage and dated rates, not provider invoices.

## Ranking rules (baseline, `pipeline/rank.py`, regenerate with `pipeline/rerank.py`)

Scope: completed records with intent `complaint` or `cancellation`; praise, requests and unclear are excluded. Each review belongs to exactly one issue (`allow_multi_issue: false`), so counts never overlap. `complaint_count` = members; `severity_sum` = sum of member severities; `mean_severity` = severity_sum / complaint_count (6 decimals, half-up); `priority_score` = complaint_count x mean_severity = severity_sum exactly. Order: priority_score descending, then issue ID ascending. Identical saved inputs give an identical `ranking.csv`; the official checker recomputes it independently.
Duplicate texts reuse one labeled original (`cache_source_id`) but every source ID counts separately in these totals. Missing app versions (159,701 in the full file) are not used by any stage. I did not do the optional trend analysis by period.

## Architecture

```mermaid
flowchart LR
  CSV[(reviews CSV)] --> P[1 Prepare: code<br/>ingest, hash, dedupe, profile]
  P --> E[2 Enrich: Haiku 5.5<br/>batches of at most 50, validate, save each batch]
  E -->|records| V[3 Verify: Sonnet 5.5<br/>blind re-label of a random sample]
  E --> G[4 Group: Haiku 5.5<br/>frozen issue menu + assignment]
  G --> R[5 Rank: code only<br/>count x mean severity]
  R --> M[6 Recommend: Sonnet 5.5<br/>memo from saved aggregates]
  R --> X[grading/ export + checker]
  M --> D[(SQLite DB)]
  R --> D
  E --> D
  D --> B[FastAPI backend]
  B --> W[Deployed dashboard]
  E -. cap / retry / resume .-> L[(calls.jsonl ledger)]
```

| Stage | Owner | Input -> output | Failure behavior |
|---|---|---|---|
| Prepare | code (`pipeline/ingest.py`) | CSV -> SQLite + ingestion report; 13 empty texts quarantined | counts must match the file profile |
| Enrich | model + code validation (`pipeline/enrich.py`) | up to 50 review texts -> topic, intent, sentiment, severity, entities, exact `evidence_quote`, `needs_review` | invalid items retried once, then quarantined with reason; saved after every call; shared spend ledger reserves worst-case cost before dispatch |
| Verify | separate model (`pipeline/verify.py`) | texts only (never the first label) -> labels; code compares | disagreements listed in `results/verification.jsonl` |
| Group | model proposes a frozen menu per topic, then assigns (`pipeline/group.py`) | complaint/cancellation records -> exactly one issue each | unresolved items go to a flagged catch-all issue |
| Rank | code only (`pipeline/rank.py`, `pipeline/rerank.py`) | membership + severities -> `ranking.csv` | deterministic; reruns identical |
| Recommend | model (`pipeline/memo.py`) | top-8 ranking rows + 3 sampled quotes each -> memo with claim IDs | code extracts claim IDs into `claims.csv` and flags any number not in the allowed list |

Code owns record accounting, validation, budgets, state and arithmetic. Models only read messy language (labels, issue names, memo prose). `pipeline/run_all.py` runs every stage on any CSV.
Why each model call exists: labels need language judgment; the verifier gives an independent check; grouping needs naming and fuzzy matching; the memo turns numbers into an argument. Counting, sorting, caching and ranking are code.

## One review, traced end to end

Review `001805dd-4e6b-4278-9988-d21c52576a94` (2 stars): *"Way too many ads. Plays 1 or 2 songs and then multiple ads then does it again. Very annoying when trying to listen to music."*

1. **Source ID and hash:** original row in the CSV; `source_sha256` stored in `grading/records.jsonl.gz`.
2. **Enrichment (Haiku, labels-v2):** topic `usability`, intent `complaint`, severity 3, evidence quote *"Way too many ads. Plays 1 or 2 songs and then multiple ads"* (exact substring, checked in code).
3. **Verification:** only a random sample is verified; this review was not in it (see `results/verification.jsonl`).
4. **Issue membership:** `ISS-064` "Excessive ads on free plan" (`results/membership.csv`).
5. **Ranking:** rank 2: 5,575 complaints, mean severity 2.229776, priority 12,431 (`results/ranking.csv`).
6. **Memo claim:** `C02-count` = 5292, `C02-mean`, `C02-score` in `results/claims.csv`; the dashboard re-checks each claim against the ranking table.

**A failed case:** review `4765dcaf-18b2-4426-aa8a-4576ec59217d` ("This app was great but coul'd not download so please replace the error"). The model's quote was not an exact substring (it fixed the typo "coul'd"). The batch was retried once; the quote was still invalid, so the record was **not** saved as a success. It is in `results/quarantine.jsonl.gz` with reason `evidence_not_exact_substring` and counts as unfinished. A review where tone and topic conflict, or where the language is unsupported, is routed by the `needs_review` flag and the "unclear" rules in `pipeline/labels.py`.

## Rubric map

**Deliverable quality (4)**
- Accessible code/setup/artifacts: this README, `requirements.txt`, `.env.example`, `.gitignore`; `pipeline/`, `cost/`, `evals/`, `tests/`, `grading/`, `results/`; every role's prompt in `docs/prompts.md`; run identity in `results/run_manifest.json`.
- Architecture, shared schema, provenance: diagram above; schema in `pipeline/enrich.py` (`TOOL`), labels in `pipeline/labels.py`; `label_config` + `source_sha256` + `cache_source_id` on each record.
- Memo numbers linked to calculations and evidence: `results/memo.md` (cites issue IDs, representative review IDs and claim IDs; code rejects any ID or number not supplied), `results/claims.csv` (checker confirms each value), `results/memo_report.json`, dashboard chips.
- Recommendation, alternatives, limitations: `results/memo.md` and "Scope and honest limits".

**Testing and evaluation (3)**
- 50 human labels, per-field comparison, error analysis: `evals/golden_50_labeled.csv`, `evals/golden_report_v1_untuned.md`, `evals/golden_report_v2_tuned.md` (confusion tables, MAE, needs_review, quote checks, concrete disagreements) and the written analysis `evals/error_analysis.md` (error patterns, entity and quote inspection, failed records, unsupported language).
- Independent verification, planted-error, injection tests: `pipeline/verify.py`, `results/verify_report.json`, `tests/test_pipeline.py` (planted bad values, fake quotes, unknown/duplicate IDs, missing items, spend cap, resume), `tests/test_verify_planted.py` (a deliberately wrong label in a test copy is flagged), `evals/run_injection_test.py` (6/6).
- Cost/runtime calculator + controls: `cost/` (below); controls demonstrated in `tests/` (cap blocks calls, bounded retries, resume) and `evals/resume_demo_log.txt`.

**Working result (3)**
- Full ingestion, coverage, classification: `grading/`, `results/run_summary.json` (coverage is partial: see limits).
- Runnable staged program, bounded calls, saved handoffs, resume: `python -m pipeline.run_all`, 50-review max requests (`calls.jsonl`), interruption evidence: the 100k run's process ended unexpectedly partway (exit code 1, cause not diagnosed) and was restarted with `--phase resume` (`grading/checkpoint_before.json` 47,154 IDs -> `checkpoint_after.json` 104,975 IDs, no completed ID re-sent), plus `tools/resume_demo.py` / `evals/resume_demo_log.txt`. **Recording:** `TODO: link the screen recording`.
- Reproducible ranking + deployed dashboard: `python -m pipeline.rerank` (below); dashboard in `dashboard/`.

## Commands

**Setup:** Python 3.13 with the standard library for the pipeline and tests; `requirements.txt` pins only the dashboard (`fastapi==0.117.1`, `uvicorn==0.37.0`). Dataset: Kaggle "3.4 Million Spotify Google Store Reviews" v2 by BwandoWando (CC0), course extract `spotify_reviews_18months.csv`, 97,400,616 bytes, SHA-256 `1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6` (place it at `data/spotify_reviews_18months.csv`; it is not committed).



```bash
pip install -r requirements.txt            # only fastapi + uvicorn; the pipeline itself uses the standard library
cp .env.example .env                       # then add ANTHROPIC_API_KEY (never commit .env)
# Place the course CSV at data/spotify_reviews_18months.csv (sha256 1fc85de6...a2cef6, 97,400,616 bytes; not committed)

python -m pipeline.run_all INPUT.csv --run-dir work/myrun --cap 2.00 --workers 4   # all stages, paid, resumable
python -m pipeline.rerank --records grading/records.jsonl.gz --membership grading/membership.csv --out ranking_rerun.csv --compare grading/ranking.csv   # no model calls
python cost/calculator.py                  # offline replay of the cost/runtime calculator, no key
python cost/calculator.py --rate-multiplier 2   # doubles API spend, time unchanged
python -m unittest tests.test_pipeline tests.test_verify_planted    # offline, free
python tools/check_submission.py profile --full data/spotify_reviews_18months.csv --out grading/ingestion.json
python tools/check_submission.py reference --full data/spotify_reviews_18months.csv --analysis data/spotify_reviews_18months.csv --out local-reference.json
python tools/check_submission.py check --reference local-reference.json --submission grading --out self-check.json
```

Explicit paid commands: `python cost/run_pilot.py --label cold|warm --run-dir work/pilot_final`, `python -m pipeline.enrich ...`, `python evals/run_injection_test.py`.

## Cost and runtime calculator (`cost/`)

`cost/report.md` (offline replay output), `cost/rates.csv` and `rates.json` (dated Anthropic prices, source link), `cost/usage.csv`, `cost/pilot_records.jsonl`, `cost/pilot_calls.jsonl`, `cost/pilot_runs.jsonl` (cold and warm runs with stage timings), `cost/calculator.py`, `cost/run_pilot.py`, `cost/report_crosscheck.md` (pilot estimate vs the real 100k run).
Settings used: Haiku 5.5 for enrich and group, Sonnet 5.5 for verify and memo; tier standard (no Batch API); no thinking; batch size 25 in the pilot, 50 in the large runs; one worker in the pilot, 6 in the 100k run. A fallback to a stronger model for hard cases was not used (declared fallback fraction 0).
The pilot ran the full chain on `cost_100.csv` with an empty cache (cold, 4 enrich + 1 verify + 10 group + 2 memo calls, 82.3 s, $0.0654), then warm (0 calls, 0.05 s, $0). Local compute and electricity cost: **unknown, not counted as zero**.

## Held-out check

Because the golden results informed the rules, I added fresh held-out cases. `evals/heldout_to_label.csv` has 30 reviews from the 10,000 development set that are not in the golden 50 or the 500 checkpoint (seeded sample). I hand-labeled the **first 20** (`evals/heldout_labeled.csv`; the other 10 were left unlabeled for time and are not scored). The model's answers are the final-run records for the same IDs (`evals/heldout_predictions.jsonl`). Full report: `evals/heldout_report.md`.

| Held-out 20 | Result |
|---|---|
| Topic agreement | 90% (18/20) |
| Intent agreement | 85% (17/20) |
| Severity exact / within 1 / MAE | 80% / 100% / 0.20 (model never higher than the human; lower in 4 cases) |
| Sentiment within 0.5 | 18/20 (MAE 0.29) |
| Evidence quote exact substring | 20/20 |
| needs_review | human flagged 2, model flagged 3 (caught 1) |

This is a small diagnostic sample, not a population accuracy estimate. 15 of the 20 reviews are topic `other` (mostly short praise or vague comments), so per-class F1 is not meaningful. Disagreements (7 reviews): 3 are praise/complaint edge cases on short text ("Boycott", a single emoji, a three-star review praising downloads); 1 is a premium-gating request scored severity 2 by the model and 3 by the human; 1 is a "glitchy app" complaint scored severity 3 vs 4; 1 is a praise review that mentions ads (`other` vs `usability`); and 1 (`4e677b01`, a mobile-payment error) was labeled `playback` by the human but `billing` by the model. Under the contract a failing payment is `billing`, so this one is more likely a human-label slip than a model error; the human label is left as entered.

## Deploy the dashboard

The dashboard is a FastAPI backend (`dashboard/app.py`) that reads a SQLite database (`dashboard/data/spotify.sqlite.gz`, built by `dashboard/build_db.py` from the saved outputs, 104,975 classified reviews, issues, ranking, claims, memo) and serves JSON plus a static page. No API key and no model calls are needed to view it.
1. Push this repo to GitHub (public). 2. On [render.com](https://render.com) choose **New -> Blueprint**, select the repo; it reads `render.yaml` (free web service, `pip install -r requirements.txt`, `uvicorn dashboard.app:app`). 3. Open the URL. This repo's deployment is the live link at the top of this README. Free instances sleep; the first load can take about a minute.
Local: `uvicorn dashboard.app:app --port 8000`. Rebuild the database: `python dashboard/build_db.py --run-dir work/c10000 --input data/sample_105k.csv`.

## File map

| Brief's name | Where it is |
|---|---|
| enriched table | `grading/records.jsonl.gz` (one final record per source ID: completed or quarantined) |
| quarantine log | `results/quarantine.jsonl.gz` (reasons; 555,647 rows) |
| issues / membership | `results/issues.json` (stable issue menu), `results/membership.csv` |
| aggregates / ranking | `results/aggregates.csv` (topic x intent), `results/ranking.csv` |
| run log / run summary | `grading/calls.jsonl` (every attempt), `results/run_summary.json`, `results/run_manifest.json` (run id, code version, prompt hashes, models, settings, output hashes) |
| prompts | `docs/prompts.md` (every role), label definitions `pipeline/labels.py` |
| evals | `evals/` (golden set and predictions, held-out set, reports, `error_analysis.md`, injection and resume evidence) |
| verifier output | `results/verification.jsonl`, `results/verify_report.json` |
| memo and claims | `results/memo.md`, `results/claims.csv` |
| cost calculator | `cost/` (see `cost/README.md`) |
| ingestion report, data manifest | `results/ingestion_report.json`, `results/data_manifest.json`, `grading/ingestion.json` |

Code: `pipeline/` stages | `tools/` sample, labeling pages, checker, packaging | `tests/` offline tests | `dashboard/` backend, page, database | `NOTES.md` working notes.
Data: supplied by the course (CC0, Kaggle "3.4 Million Spotify Google Store Reviews" v2); checksum in `results/data_manifest.json`.

## AI assistance

Claude (Anthropic) helped write the code under direction, and Claude models run the pipeline roles. Golden-set labels and all scope/budget decisions are mine. Nothing here was simulated: usage and costs are from logged API responses, and anything unmeasured is marked as an estimate.
