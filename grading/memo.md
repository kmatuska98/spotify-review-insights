# Memo: Which customer issues to fix first

**To:** Spotify Product Team
**Re:** Priority order from review analysis

## Method
Priority score is the complaint count multiplied by the mean severity, which is rated on a five-point scale, so frequent and painful issues rank highest.

## Recommendation

**1. Excessive ads on free plan: fix first.**
This issue has 5575 [C02-count] complaints, a mean severity of 2.229776 [C02-mean], and a priority score of 12431 [C02-score]. It is the highest-scoring issue we can act on. One user says, "as a premium subscriber, I still get commercials," which suggests a possible ad-targeting or entitlement bug worth checking.

**2. Premium gating and billing friction: fix as one package.**
Several issues share one theme, features locked behind Premium:
- Other billing problems: 2825 [C03-count] complaints, mean severity 2.617699 [C03-mean], score 7395 [C03-score].
- Playlist and repeat features gated to premium: 1711 [C05-count] complaints, mean severity 2.903565 [C05-mean], score 4968 [C05-score].
- Cannot choose specific songs without premium: 1253 [C08-count] complaints, mean severity 3.032721 [C08-mean], score 3800 [C08-score].

A user writes, "I can't even repeat the song I've selected. It says I need Premium for that." Clearer upgrade messaging, or loosening basic controls like repeat, could address all of them at once.

**3. Playback reliability: fix in parallel with engineering capacity.**
Playback stopping or pausing mid-song has 1179 [C06-count] complaints but the highest mean severity of the group at 3.480916 [C06-mean], for a score of 4104 [C06-score]. Users mention stuttering "after the update," so a regression check is a sensible first step. Other playback problems
