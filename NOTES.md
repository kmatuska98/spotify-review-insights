# Project handoff notes

## Ground rules (from the user)
- Work ONLY inside this project folder. Do not list, read, search or write anything outside it. If a file from elsewhere is needed, ask the user to move it into the project.
- Never print API keys. `.env` holds the key; never echo, log or commit it. Use masked checks only.
- The user is a student and wants to be taught as work proceeds: short plain-language mini-lessons, optional quizzes, explain why each stage exists. Keep explanations concise.
- Never invent executions, usage, costs, revenue or churn. Mark estimates as estimates.
- Settings: `.claude/settings.local.json` restricts reads outside the project and enables a shell sandbox (untested; see below).

## Assignment (summary)
Multi-agent pipeline over Spotify reviews (`data/spotify_reviews_18months.csv`, 660,622 rows, 660,609 nonempty, 13 empty to quarantine, 484,189 distinct nonempty texts; at least 100,000 classified is acceptable). Stages: Prepare, Classify (batches of at most 50), Verify (blind re-label of a random sample), Group (stable issue membership), Rank (priority = complaint_count x mean_severity = severity_sum; tie-break ascending issue ID), Recommend (memo from saved aggregates). Also required: 100-review cost/runtime calculator with real cold/warm pilot and offline replay (spec in `data/COST_CALCULATOR.md`), `grading/` export (spec in `data/GRADING_CONTRACT.md`, checker in `tools/check_submission.py`), golden-50 evaluation, planted-error and injection tests, interruption/resume evidence, deployed dashboard + backend + database, README mapping rubric to evidence. Deadline: Oct 20, 2026, 11:59 pm Pacific.

## Labels (exact)
- topic: access, usability, playback, downloads, catalog, billing, support, other.
- intent precedence: cancellation, complaint, request, praise, unclear.
- severity 1-5: 1 no problem/praise/request, 2 annoyance/generic criticism, 3 degraded function, 4 core task blocked, 5 explicit serious financial/privacy/data harm.
- Ads are usability unless they break playback. Paid-plan mention alone is not billing. General praise is `other`; specific praised feature gets that topic.

## Done so far
1. `pipeline/ingest.py` (Stage 1) run on the full CSV; results in `work/pipeline.db` and `work/ingestion_report.json`. Counts matched the assignment exactly.
2. `tools/make_label_page.py` builds `evals/label_golden.html`; the user hand-labeled the golden 50, saved as `evals/golden_50_labeled.csv` (complete; 2 evidence quotes were corrected to exact substrings; labels untouched). These labels must never appear in prompts or examples.
3. `.gitignore`, `.env.example` created. `.env` holds ANTHROPIC_API_KEY only (rotated by the user).
4. Smoke test earlier: `claude-haiku-5-5` responded via the Anthropic API.

## Decisions and results (added later)
- Premium-only controls: pipeline follows the GRADING CONTRACT (`billing`). Two golden labels (user chose `usability`) differ on purpose; golden file untouched. Mention in README.
- Labels now `labels-v2` (general rules + synthetic examples only; no golden texts). Golden-50 (Haiku 5.5): v1 topic .78 / intent .90 / severity exact .88; v2 topic .80 / intent .92 / sev .88. Pilot blind verify (Sonnet 5.5, 50 reviews) all-three agreement v1 .68, v2 .76. Small sample, so differences may be noise.
- Pilot v1 cost $0.0054 for 100 reviews (Haiku); Sonnet verify of 50 cost about $0.08. Rates in `cost/rates.json` (checked 2026-10-18). Sonnet 5.5 rejects forced tool_choice, so non-Haiku calls use auto.
- Run dirs: `work/pilot`, `work/golden` (labels-v1); `work/pilot_v2`, `work/golden_v2` (labels-v2). Stages built: `pipeline/enrich.py`, `pipeline/verify.py`, `evals/score_golden.py`.

## Assignment facts (from the user's pasted brief, 2026-10-20)
- Deliverable: ONE public GitHub repo URL via the course portal; README is the grader's entry point and must map rubric categories to evidence links. Due Oct 20 2026 11:59 pm PT.
- Rubric (10 pts): Deliverable quality 4; Testing & evaluation 3 (golden 50 + error analysis; verification + planted-error + injection tests; 100-review cold/warm pilot + offline calculator + retry/spend/recovery controls); Working result 3 (coverage; runnable staged program + resume; ranking + DEPLOYED dashboard -> backend -> database with grounded AI recommendation).
- Coverage point = .2 x file-profile match + .2 x (valid completed or quarantined)/660,622 + .6 x valid classified/660,609. 100k classified is acceptable but earns about 0.6 x 0.15 of the last term.
- Invalid-output retries limited to ONE (enrich MAX_ATTEMPTS now 2; the 100k run before that change used a third attempt on 50 batches: disclose).
- Golden set was used to revise rules (labels-v2): must DISCLOSE and add held-out fresh cases (evals/heldout_to_label.csv -> user labels via evals/label_heldout.html). The labels-v1 golden run is the clean pre-revision result.
- Verify stage must include a deliberately wrong label in a separate test copy (tests/test_verify_planted.py).
- Dashboard: shows overall metrics, issue ranking, AI recommendation with supporting numbers + traceable issue/review evidence; backend serves from a database. Built in dashboard/ (FastAPI + SQLite, render.yaml). USER must deploy (accounts) and push the public GitHub repo.
- Commands: python -m pipeline.run_all INPUT.csv --run-dir DIR; python -m pipeline.rerank (no model calls); python cost/calculator.py (offline replay); python cost/run_pilot.py (paid, explicit).
- Remote Control was turned on for the session at the user's request.

## STATUS as of 2026-10-20 (supersedes the older "Not done yet" list below)
DONE: 100k-sample run (104,975 classified (after a 5,000-review extension to clear the 100,000 floor), 25 failed, 555,609 not attempted), group/rank/memo/verify, grading/ export (checker: only issue is unfinished_classification, coverage candidate 0.4953; after the brief cross-check also added: verifier-specific prompt, memo cites issue+review IDs, docs/prompts.md, run_manifest, aggregates, error_analysis, cost/README, API-failure tests), cost/ pilot + offline calculator, tests (8 pass) + injection 6/6, resume demo, dashboard (FastAPI + SQLite, tested locally), README, results/ folder, .gitignore ignores work/.
USER TODO: (1) approve/ask Claude to `git init`, commit, create PUBLIC GitHub repo and push (gh is logged in as kmatuska98; not done yet); (2) deploy dashboard on Render via render.yaml, paste URL in README top; (3) hand-label the 30 held-out reviews (evals/label_heldout.html -> save evals/heldout_labeled.csv), then run score_golden.py --held-out; (4) record the interruption/resume screen recording (python tools/resume_demo.py) and link it in README; (5) delete .env.docx and stray Downloads link; (6) check API credit balance in Anthropic Console.
Total logged API spend across all run dirs about $5.47 (estimate; Console is authoritative).

## Older list (historical)
## Not done yet
- Test that the new `.env` key works (do it inside the pipeline code, not by printing).
- Label definitions/examples file, prompts, enrichment stage, verifier, grouping, ranking, memo, calculator, grading export, dashboard/backend/database, README.
- Look up current Haiku 5.5 and Sonnet 5.5 prices (dated source links) before any cost estimate. Do not guess.
- Plan: Anthropic only. Haiku 5.5 for enrich/verify, capped Sonnet 5.5 fallback and memo. Start with the 100-review pilot (`data/cost_100.csv`), then 500, then 10,000, then decide 100k vs full run. User has about $10 of API credit; keep a spend cap in code.

## Open items for the user
- Delete the stray Word copy of the old key in the project folder (`.env.docx`) and the stray `Downloads` link/folder inside the project.
- Check that the shell sandbox works in a new session (ask Claude to try listing a folder outside the project; it should be refused). If Python or git break, remove the `sandbox` block from `.claude/settings.local.json`.
