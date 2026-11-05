# Minutes/role/calibrated v3 — 5 November 2026

User-authorized release for future NBA props; original published selections remain frozen.

1. Project minutes with 70% latest-five median and 30% latest-ten median, using current-season games. Minute variation enters low/base/high scenarios; games below eight minutes remain downside evidence rather than inflating per-minute rates.
2. Decay current-season samples with a ten-game half-life. Previous-season weight is capped at half the current-season total and at fifty source games. Publishing requires five current-season games, projected minutes >=15 and minutes CV <=0.25. This is a role-stability proxy, not a verified starter/rotation report.
3. Bayesian smoothing plus market-specific monotonic calibration, trained on earlier finished dates only. Alternate lines sum to one unit per player/market/game/day. Require effective bin support >=20 on at least three dates, overall five training dates, effective player sample >=10 and a prudential probability floor >=55%. Estimates >=90% need substantially stronger support; sparse bins are capped below 90%. The initial calibration artifact is trained through 2026-11-05 and cannot be applied to that or earlier target dates. It is versioned and requires a new chronological review before replacement; no silent online fitting.
4. New daily rows sort by corrected probability, then minutes stability, effective evidence and value as last tie-breaker. New Singles prioritize corrected probability rather than expected return, retaining odds 1.70–1.90 and p>70%. Top selections retain odds 1.20–2.20, p>=70%, and no negative modeled edge. Availability exclusions remain enforced. Legacy policy is kept for historical replay only.
5. Official lists may contain fewer than ten entries, and the Single may be absent. Modern session reads never fill an already published short list. Old pre-v3 rows cannot be promoted into new sessions.

## Validation

Replay used thirteen archived source snapshots and matched finalized outcomes. Calibration for each test date used earlier dates only. Production uses the final versioned artifact, not the retrospective per-date fits. Raw inputs and historical outcome archives were not overwritten.

On the six calendar dates on which the new policy emits selections, the new Top lists contain 27 settled entries with 70.4% observed vs 78.5% estimated; legacy lists on those dates contain 35 entries with 68.6% observed vs 86.2% estimated. Brier is 0.2135 vs 0.2470, but portfolios and sizes differ, dates/athletes are correlated, and this is a small retrospective comparison, not proof of a higher future hit rate. No independently untouched prospective validation is available yet.

The first fixed v3 design does NOT improve the full universe uniformly: across 13,192 matched lines Brier is 0.1373 vs legacy 0.1231, and the later block is 0.1246 vs 0.1233. The later 1.20–2.20 odds band is approximately tied (0.2426 vs 0.2427). This limitation is material: the release uses conservative publishing gates and abstention rather than claiming that every displayed estimate or candidate is superior. Most extreme high-odds lines are outside the publication objective.

The unchanged shadow comparisons remain available for future evaluation. Calibration is a statistical estimate, not an assurance that an individual prop will hit.

## Applying to existing future odds

A derived snapshot may be appended from the latest saved upcoming scan with zero provider requests, retaining its original quote timestamp and scan age. Such recalculation must name its source job and be guarded against a newer scan replacing it. Historical and already-official predictions must not be edited.
