# Memo: Which customer issues to fix first

**To:** Spotify Product Team
**Re:** Priority ranking from classified app reviews

## How we ranked
Priority score is the complaint count multiplied by the mean severity, so it favors issues that are both common and painful.

## Recommendation

**1. Excessive ads on free plan (ISS-064): fix first.** It has 5575 complaints [C02-count] with a mean severity of 2.229776 [C02-mean], for a priority score of 12431 [C02-score]. It is the highest-scoring issue we can act on directly. Customers describe it bluntly:
- "Ad ad ad" (review 772e4e34-1c55-4fb6-8894-e5b546deeefd)
- "as a premium subscriber, I still get commercials, but only on conservative content" (review bf99f2d0-f489-4c9e-91da-daeb6a951724)

The second quote suggests a possible ad-targeting or entitlement bug for paying users. Check that first.

**2. Other billing problems (ISS-018): fix second.** It has 2825 complaints [C03-count] but the highest mean severity of the top three, 2.617699 [C03-mean], for a score of 7395 [C03-score]. The quotes are mostly about premium prompts rather than charges:
- "stop putting premium on literally everything" (review c4d1559e-bbb2-43c8-9487-31f649634e9b)
- "Provoking to get premium" (review 8bc55766-506d-4899-ad44-0fadd2b12227)

Review the frequency and placement of upgrade prompts, and consider relabeling this category.

**3. General hate and uninstall requests (ISS-044): investigate, don't fix directly.** It has the top score, 17727 [C01-score], from 8897 complaints [C01-count] at a mean severity of 1.992469 [C01-mean]. But the reviews are vague:
- "Worst app ever" (review 4cb79e53-dd8c-429e-a3ae-9938d7d135a6)
- "Bad app" (review 6ed8ef34-784d-46c5-aa97-aa85bace76d8)

There is nothing here to build against. Treat it
