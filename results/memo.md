# Memo: Which customer issues to fix first

**To:** Spotify product team
**Re:** Priority order from the review analysis

## How we ranked
Priority score is complaint count multiplied by mean severity (rated 1-5), so it rewards issues that are both common and painful.

## Recommendation

**1. Excessive ads on free plan.** This is the most actionable high-volume issue. It has 5292 [C02-count] complaints, mean severity 2.230537 [C02-mean], and a priority score of 11804 [C02-score]. Users call the ads "extremely loud" and "so annoying." One premium subscriber reports still seeing commercials, which suggests a possible targeting or entitlement bug worth checking.

**2. Playback stops or pauses mid-song.** It has fewer complaints, 1141 [C06-count], but the highest mean severity on the list, 3.476775 [C06-mean], and a score of 3967 [C06-score]. Users report stuttering after an update, freezing, and crashes. Because the problem is severe and likely technical, engineering should treat it as a reliability priority. Related "other playback problems" score 4939 [C04-score] from 1643 [C04-count] complaints at severity 3.006086 [C04-mean], so investigate both together.

**3. Premium gating and billing friction.** Several issues share one theme: users feel features are locked behind Premium.
- Other billing problems: score 7108 [C03-score], from 2717 [C03-count] complaints at severity 2.616121 [C03-mean].
- Playlist and repeat features gated to premium: score 4644 [C05-score], from 1600 [C05-count] complaints at severity 2.902500 [C05-mean].
- Cannot choose specific songs without premium: score 3622 [C08-score], from 1196 [C08-count] complaints at severity 3.028428 [C08-mean].

A review of what free users can and cannot do, and how the upsell is messaged, could address all of these at once.

**4. Skip, repeat, and seek limits.** This issue has 1319 [C07-count] complaints and a score of 3790 [C07-score]. It overlaps with the gating theme above.

## Not a fix-first item
"General hate and uninstall requests" has the highest raw score, 16877 [C01-score], from 8469 [C01-count] complaints at a low mean severity of 1.992797 [C01-mean]. The reviews are vague ("Bad," "Bad app"), so there is nothing specific to fix. Tre
