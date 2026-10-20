## Golden-50, labels-v1 (run BEFORE any golden-informed revision: clean result)

Cases: 50 | model completed: 50 (missing counts as wrong)

- **topic** agreement 0.78 (39/50), macro-F1 0.73
- **intent** agreement 0.90 (45/50), macro-F1 0.62
- **severity** exact 0.88, within 1 1.00, MAE 0.12; model higher/lower than human: 2/4
- **sentiment** MAE 0.21; within predeclared tolerance 0.5: 50/50
- **evidence_quote** exact substring of source: 50/50 (checked in code; whether the quote *supports* the label needs the human read below)
- **needs_review** (human flagged 8 ambiguous cases): model flagged 9; caught 5, missed 3, extra 4
- **entities**: model listed entities on 21/50 reviews (inspect for unsupported additions; not scored against human lists)

Topic counts (human): other 29, usability 9, catalog 5, playback 5, downloads 1, billing 1

Topic confusion:

| human \ model | access | usability | playback | downloads | catalog | billing | support | other |
|---|---|---|---|---|---|---|---|---|
| usability |  | 4 | 1 |  |  | 2 |  | 2 |
| playback |  |  | 5 |  |  |  |  |  |
| downloads |  |  |  | 1 |  |  |  |  |
| catalog |  | 1 |  |  | 3 |  |  | 1 |
| billing |  |  |  |  |  | 1 |  |  |
| other |  | 2 |  |  | 2 |  |  | 25 |

Intent confusion:

| human \ model | cancellation | complaint | request | praise | unclear |
|---|---|---|---|---|---|
| complaint | 1 | 20 |  |  | 1 |
| request |  |  | 1 |  |  |
| praise |  |  |  | 20 |  |
| unclear |  |  | 2 | 1 | 4 |

Concrete disagreements (human topic/intent/sev -> model topic/intent/sev):

- `b5ee7834` catalog/praise/1 -> other/praise/1 | 'Spotify is awesome and and very diverse :)'
- `1fc8b08f` usability/praise/1 -> other/praise/1 | 'Duo Premium .... No ads at all!'
- `947821dc` playback/complaint/4 -> playback/complaint/3 | 'Very good but wen I play my song it o ly plays a little bit then it stops I updated my phone and it worked but it happend again they need to'
- `723f07de` usability/complaint/4 -> playback/complaint/4 | 'Update: I reached out to Spotify Support and with some help from Sarah I was able to get the app working again. Old Post:Normally, the app w'
- `ac6cd66d` other/unclear/1 -> catalog/unclear/1 | 'Lhat ng song nasa spotify'
- `46842184` other/unclear/1 -> catalog/request/1 | 'asem, lirik nya kdang gaada kek mana??'
- `657f1b77` other/complaint/1 -> other/complaint/2 | 'Hate This application 👎'
- `5de7f95b` other/complaint/1 -> other/unclear/1 | "We are boycotting Swedish app in our protest against Sweden for their desrecpect & desceration of our holy book Qur'an"
- `372d4e67` other/unclear/1 -> usability/request/1 | 'Please ye ads ko thoda kumm Karo harr ek song ke baad ad 🙏🙄'
- `47f1406d` playback/complaint/4 -> playback/complaint/3 | 'Very poor updates as we cannot playback the songs and most bad updates are happening it is affecting the spotify quality'
- `f4c8146a` other/unclear/1 -> other/praise/1 | 'Unconditional love, Stoli Canales'
- `3ddb3f4e` usability/complaint/3 -> billing/cancellation/3 | "Deleting this App. The new update suck, we can't choose our fvrt songs after some clicks, we can't CHOOSE song after a song played, and we c"
- `16d640e9` usability/complaint/2 -> billing/complaint/3 | "It's my best music app but now it's not...everything basic features is premium...."
- `2aa566c6` other/praise/1 -> usability/praise/1 | 'Nice app, very less advertising'
- `b58dd6f0` catalog/request/2 -> usability/request/1 | 'The only thing Spotify lacks is the ability to organize saved \nalbums/artists into collections. Would definitely deserve 5 stars if it \nincl'
- `dceb14e7` playback/complaint/4 -> playback/complaint/3 | "I gave one star because I can't give any less than that. the new update is sooooooo annoying like I can't even play the songs that I like an"
- `99b93e31` usability/complaint/2 -> other/complaint/2 | 'This update very bad for everyone.old Spotify. we all want.'
