# Inactive reconciliation and minutes experiment — 2 November 2026

## All 181 absent-athlete lines now explained

The original audit found 9,083 eligible lines, 8,793 binary matches, 109 explicit ESPN DNP lines and 181 lines missing an athlete in the exact game's boxscore. The 181 lines represent 14 player-games.

The team-specific **Inactive** sections of the NBA official scorer reports independently explain all 14 cases. Exact game/date/team, archived athlete identity and inactive surname were manually cross-checked; no automatic surname-only settlement was added. Each case's official URL, file SHA-256 and affected-line count are retained in `inactive-evidence-2026-11-02.json`.

| Italian date | Player | Lines | Official inactive reason category |
| --- | --- | ---: | --- |
| 24 Oct | Reed Sheppard | 11 | Injury/illness |
| 26 Oct | Ausar Thompson | 14 | Injury/illness |
| 26 Oct | Keegan Murray | 12 | Injury/illness |
| 27 Oct | Chet Holmgren | 13 | Injury/illness |
| 27 Oct | Marcus Smart | 11 | Injury/illness |
| 27 Oct | Cason Wallace | 12 | Injury/illness |
| 29 Oct | Lauri Markkanen | 15 | Injury/illness |
| 29 Oct | Luka Doncic | 16 | Injury/illness |
| 29 Oct | Ziaire Williams | 12 | Injury/illness |
| 30 Oct | Robert Williams III | 10 | Injury/illness |
| 30 Oct | Dejounte Murray | 17 | Personal |
| 31 Oct | LeBron James | 17 | Injury/illness |
| 1 Nov | Mitchell Robinson | 10 | Rest |
| 2 Nov | Ziaire Williams | 11 | Injury/illness |

**No binary results are added.** Inactivity is not a losing prop, and bookmaker refund rules are not inferred. The original calibration denominator and settled outcomes are unchanged. All 290 original differences are explained as nonparticipation, rather than a date-join bug or player-name typo. This does not imply that there can never be missing data in later cohorts.

## Historical injury information is not automatically pregame evidence

An ESPN summary retrieved after a historical game can contain an injury section updated later. For example, Reed Sheppard's 24 October Italian-date summary contained an injury entry dated 1 November. Such an entry must not be used to reconstruct what the model knew before the older game. NBA gamebooks above establish postgame participation status only.

In the selected source snapshots, six of the fourteen cases have no saved availability annotation. Five are saved as `not-listed` and three as `day-to-day`. `not-listed` does not guarantee participation. No later injury report was backfilled into those rows.

## Frozen experiment: minutes-v1

The experiment preserves one PTS Over per player/fixture, with saved odds between 1.20 and 2.00, choosing the saved price nearest 1.80 before reading outcomes. It records:

- Median and mean minutes of the latest five eligible games.
- Minutes coefficient of variation and low-minutes frequency over the latest ten games.
- Last-game minutes relative to the five-game median.
- Pre-capture availability if the archived verification timestamp is valid.
- Unknown starter and role values explicitly, since archived logs do not provide them.

Only uniquely identified regular-season history strictly before capture is eligible. Nonfinite statistics, unknown timestamps, missing identity and conflicting history fail closed. Date-only observations are excluded unless the whole UTC day has elapsed. The scoring candidate transfers recent historical points-per-minute to the five-game median minutes, with Jeffreys smoothing. This assumption is provisional and is not a causal model of playing time.

## Development results: simple rescaling is not an improvement

The historical replay uses the exact saved logs of the original daily calibration snapshots, not fresh ESPN player logs. It covers 606 verified player-game PTS lines across 53 games and 11 Italian dates. This is a different population from the earlier 75 selected-line report.

| Metric | Public baseline | Minutes scaling candidate |
| --- | ---: | ---: |
| Mean forecast | 62.60% | 64.33% |
| Observed hit rate | 58.58% | 58.58% |
| Brier | 0.25009 | 0.26247 |

The candidate worsens Brier by 0.01239. Exploratory paired bootstrap intervals for candidate-minus-baseline Brier remain positive when resampling whole games (approximately 0.00255–0.02310) or whole dates (0.00428–0.01926). These are descriptive development intervals, not confirmatory significance tests: candidate design followed inspection of the historical outcomes, and only eleven dates are available.

Pregame last-game minute drops are not equivalent to knowing that the next game will have low minutes. The high-volatility and latest-minute-drop subgroups do not justify a blanket public exclusion or a new probability correction.

**Decision: no public promotion, recalibration or selection change.** The known underperforming candidate remains a research benchmark; prospective feature collection can inform a better future model and determine whether the same behavior persists. The candidate is never read by the live probability engine or recommendation policy, and promotion is explicitly disabled.

## Deployment and reproducibility

`minutes_research.capture` is optional scan-side work with no new network requests. It freezes features and parallel estimates in the private snapshot payload. Errors are isolated so public scans continue unchanged. The research payload is removed from public saved views. A replay across the eleven source snapshots averaged roughly 11 ms per snapshot in this environment; this is not a production latency benchmark.

`scripts/review_minutes_research.py --input <snapshots.json> --verified <verified-audit.json> --output <report.json>` regenerates the development comparison from read-only exports. Without a verified export, it uses finalized ESPN evidence through the existing guarded settlement verifier. Duplicate daily snapshots, conflicting results and invalid outcomes are not counted as independent trials.

Prospective collection begins with the next scheduled scan after deployment. No retrospective rows are relabeled as prospective. No schema migration, extra OddsPapi request, public model update or historical outcome write is required.
