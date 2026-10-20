# Error analysis (inspected failures)

Numbers come from `golden_report_v1_untuned.md`, `golden_report_v2_tuned.md`, `heldout_report.md`, `results/verify_report.json`, `results/verification.jsonl` and `results/quarantine.jsonl.gz`. All samples are small (50, 20 and 200 reviews), so these are diagnostics, not population accuracy.

## 1. Golden 50, first run (labels-v1, before any rule change)
Topic 78%, intent 90%, severity exact 88% (within 1: 100%).

| Pattern | What happened | Likely cause |
|---|---|---|
| Praise about a feature | Human `usability` / `catalog`, model `other` for praise like "no ads at all" and "very diverse" | v1 rules did not say that praise takes the topic of the praised feature |
| Premium-gated controls | Human `usability`, model `billing` (2 reviews) | The grading contract says premium-only controls are `billing`; **the pipeline follows the contract**, the golden labels were left as entered |
| Short or non-English text | Model guessed `catalog` / `request` for a few words; human said `other` / `unclear` | v1 had no rule to refuse a specific topic when the text cannot be read confidently |
| "Can't play songs" severity | Human 4, model 3 (3 cases) | v1 treated playback trouble after an update as degraded, not blocked |
| Bare negative opinion / boycott | Human `complaint`/1 or 2 vs model `unclear` for "Boycott..." text | The contract makes boycott slogans `unclear` unless a product complaint exists; the human labels were more generous |

## 2. What I changed, and what that means for the evidence
After reading those disagreements I revised the rules (`labels-v2`: praise takes the praised feature's topic, playback severity guidance, ads, neutral text, unreadable text, bare negative opinions) and added synthetic examples. **No golden text or label was placed in any prompt.** The v2 golden numbers (topic 80%, intent 92%, severity 88%) are therefore **not held-out**. Gains were small (+2 points on two fields), which is within noise for 50 cases.

## 3. Held-out 20 (fresh, labeled after the rules were set)
Topic 90%, intent 85%, severity exact 80% (within 1: 100%; model never higher than the human). 7 disagreements: three praise/complaint/unclear edge cases on very short text ("Boycott", an emoji, a three-star review praising downloads); two severity differences (premium-gating request 2 vs 3, "glitchy app" 3 vs 4); one praise review mentioning ads (`other` vs `usability`); one payment-error review labeled `playback` by the human but `billing` by the model. Under the contract a failing payment is `billing`, so that one is more likely a human-label slip; it was left as entered to keep the held-out set independent.

## 4. Independent verification (Sonnet 5.5, blind, 200 random reviews)
Agreement: topic 84.5%, intent 90%, severity exact 83.5% (within 1: 99.5%), all three fields 69%.
62 of 200 reviews differ on at least one field (field-level: topic 31, severity 33, intent 20). Largest patterns: `usability` vs `billing` topic (8 cases, the premium-gating boundary) and severity 2 vs 3 (12 of 33 severity differences), then 3 vs 4 (9). Two models reading the same rubric differ on boundary cases, which says the boundaries are fuzzy, not which model is right. A deliberately wrong label planted in a test copy is flagged by the same comparison (`tests/test_verify_planted.py`).
An operational failure to record: the first run of the revised verifier (`verify-v2`) was cut off by its output-token cap (every call returned exactly the cap), so only 25 of 200 reviews parsed and about $0.49 was wasted; I added "call the tool and write no other text" and more output headroom and reran. The wasted calls remain in `grading/calls.jsonl`.

## 5. Failed records (25 of 105,000)
24 `evidence_not_exact_substring`: the model "fixed" a typo or changed spacing in its quote (for example "coul'd" to "could"), so the quote is not a substring of the source. 1 `malformed_item`. Each failed twice (one retry) and is quarantined with its reason; none is counted as a classification. Failed records are re-queued on each resume (the failed count went from 30 to 25 after adding 5,000 new reviews, so some earlier failures were later labeled, but I did not track which).

## 6. Evidence quotes and entities (inspected on the golden 50)
- Quotes are checked in code for exact substring membership (50/50 on golden, 20/20 on held-out). On inspection they usually support the label; the model prefers a focused phrase where the human quoted a whole sentence (e.g. dropping an insult in front of the product complaint). 19 of 50 quotes in v2 are the whole review; 32 of 50 reviews are 60 characters or shorter.
- Entities: of 23 entities listed in v2, 5 are not literal substrings of the text (`ads` twice, `saved albums`, `song selection`, `recommendations`). They are normalized feature names, not invented products, but they are paraphrases and are not scored against human lists.

## 7. Ambiguity and unsupported language
`needs_review` is a prediction, not a guarantee: on the golden 50 the human flagged 8 ambiguous cases and the v2 model flagged 7 (caught 7, missed 1); on the held-out 20 the human flagged 2 and the model flagged 3 (caught 1, missed 1). Non-English or unreadable text is routed to `other` / `unclear` with `needs_review`; it is kept in the data, not dropped.

## 8. Known remaining weaknesses
- The top-ranked issue ("General hate and uninstall requests") is generic; the memo says so and the ranking is unmodified by that judgment.
- Issue menus are per topic, so one theme (premium gating) appears under both `billing` and `usability`.
- 15% of the file was classified; any statement about the other 85% is outside this evidence.
