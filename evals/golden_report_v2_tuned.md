## Golden-50, labels-v2 (rules revised after reading golden disagreements: NOT held-out)

Cases: 50 | model completed: 50 (missing counts as wrong)

- **topic** agreement 0.80 (40/50), macro-F1 0.63
- **intent** agreement 0.92 (46/50), macro-F1 0.68
- **severity** exact 0.88, within 1 1.00, MAE 0.12; model higher/lower than human: 4/2
- **sentiment** MAE 0.23; within predeclared tolerance 0.5: 48/50
- **evidence_quote** exact substring of source: 50/50 (checked in code; whether the quote *supports* the label needs the human read below)
- **needs_review** (human flagged 8 ambiguous cases): model flagged 7; caught 7, missed 1, extra 0
- **entities**: model listed entities on 17/50 reviews (inspect for unsupported additions; not scored against human lists)

Topic counts (human): other 29, usability 9, catalog 5, playback 5, downloads 1, billing 1

Topic confusion:

| human \ model | access | usability | playback | downloads | catalog | billing | support | other |
|---|---|---|---|---|---|---|---|---|
| usability |  | 5 | 1 |  |  | 2 |  | 1 |
| playback | 1 | 1 | 3 |  |  |  |  |  |
| downloads |  |  |  | 1 |  |  |  |  |
| catalog |  | 1 |  |  | 3 |  |  | 1 |
| billing |  |  |  |  |  | 1 |  |  |
| other |  | 2 |  |  |  |  |  | 27 |

Intent confusion:

| human \ model | cancellation | complaint | request | praise | unclear |
|---|---|---|---|---|---|
| complaint | 1 | 20 |  |  | 1 |
| request |  |  | 1 |  |  |
| praise |  |  |  | 19 | 1 |
| unclear |  |  | 1 |  | 6 |

Concrete disagreements (human topic/intent/sev -> model topic/intent/sev):

- `292ce26a` catalog/complaint/2 -> other/complaint/2 | 'Staff must be full of mentally ill kool-aid heads. Banning conservative music that speaks truth. Spotify is doing all they can to protect pe'
- `723f07de` usability/complaint/4 -> playback/complaint/4 | 'Update: I reached out to Spotify Support and with some help from Sarah I was able to get the app working again. Old Post:Normally, the app w'
- `fc344263` other/praise/1 -> other/unclear/1 | 'Great...'
- `657f1b77` other/complaint/1 -> other/complaint/2 | 'Hate This application 👎'
- `5de7f95b` other/complaint/1 -> other/unclear/1 | "We are boycotting Swedish app in our protest against Sweden for their desrecpect & desceration of our holy book Qur'an"
- `372d4e67` other/unclear/1 -> usability/request/2 | 'Please ye ads ko thoda kumm Karo harr ek song ke baad ad 🙏🙄'
- `3ddb3f4e` usability/complaint/3 -> billing/cancellation/3 | "Deleting this App. The new update suck, we can't choose our fvrt songs after some clicks, we can't CHOOSE song after a song played, and we c"
- `16d640e9` usability/complaint/2 -> billing/complaint/3 | "It's my best music app but now it's not...everything basic features is premium...."
- `215463ae` playback/complaint/4 -> access/complaint/4 | "What is happening with Spotify?? Recently I'm trying to play a song but it doesn't working. So I unstalled and thn again install it now I ca"
- `2aa566c6` other/praise/1 -> usability/praise/1 | 'Nice app, very less advertising'
- `b58dd6f0` catalog/request/2 -> usability/request/1 | 'The only thing Spotify lacks is the ability to organize saved \nalbums/artists into collections. Would definitely deserve 5 stars if it \nincl'
- `dceb14e7` playback/complaint/4 -> usability/complaint/3 | "I gave one star because I can't give any less than that. the new update is sooooooo annoying like I can't even play the songs that I like an"
- `d2f3874f` billing/complaint/2 -> billing/complaint/3 | 'Too expensive and the free version is pretty much unusable with constant ads... Every two or three songs.. Forget it'
- `99b93e31` usability/complaint/2 -> other/complaint/2 | 'This update very bad for everyone.old Spotify. we all want.'
