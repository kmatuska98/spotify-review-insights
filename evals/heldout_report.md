## Held-out 20 (fresh reviews labeled after the rules were frozen; never used in prompts or rule changes)

Cases: 20 | model completed: 20 (missing counts as wrong)

- **topic** agreement 0.90 (18/20), macro-F1 0.69
- **intent** agreement 0.85 (17/20), macro-F1 0.87
- **severity** exact 0.80, within 1 1.00, MAE 0.20; model higher/lower than human: 0/4
- **sentiment** MAE 0.29; within predeclared tolerance 0.5: 18/20
- **evidence_quote** exact substring of source: 20/20 (checked in code; whether the quote *supports* the label needs the human read below)
- **needs_review** (human flagged 2 ambiguous cases): model flagged 3; caught 1, missed 1, extra 2
- **entities**: model listed entities on 6/20 reviews (inspect for unsupported additions; not scored against human lists)

Topic counts (human): other 15, playback 3, downloads 1, usability 1

Topic confusion:

| human \ model | access | usability | playback | downloads | catalog | billing | support | other |
|---|---|---|---|---|---|---|---|---|
| usability |  | 1 |  |  |  |  |  |  |
| playback |  |  | 2 |  |  | 1 |  |  |
| downloads |  |  |  | 1 |  |  |  |  |
| other |  | 1 |  |  |  |  |  | 14 |

Intent confusion:

| human \ model | cancellation | complaint | request | praise | unclear |
|---|---|---|---|---|---|
| complaint |  | 5 |  | 1 | 1 |
| request |  |  | 1 |  |  |
| praise |  |  |  | 8 | 1 |
| unclear |  |  |  |  | 3 |

Concrete disagreements (human topic/intent/sev -> model topic/intent/sev):

- `86a5ff4e` downloads/complaint/2 -> downloads/praise/1 | 'I rate this app for three star because the nicest thing of this ap is that we can download all music'
- `6ce7255a` playback/complaint/4 -> playback/complaint/3 | "So glitchy, even on a premium subscription. Albums won't load or play, the app runs extremely slowly and the controls are really buggy. Bare"
- `4e677b01` playback/complaint/4 -> billing/complaint/4 | 'im trying to pay via mobile load but it says that it has encountered an error even though it worked the first time'
- `6ff1d255` other/praise/1 -> other/unclear/1 | '😊'
- `ce97902b` usability/request/3 -> usability/request/2 | 'I have prem and like sptfy.Give a toggle to turn podcasts off from my main home feed. The music card thing is very inconvenient and I like h'
- `f794fcef` other/praise/1 -> usability/praise/1 | 'if i rate five stars can i have 1 week of Spotify premium? just kidding, i love spotify even with ads'
- `3a870cfb` other/complaint/2 -> other/unclear/1 | 'Boycott'
