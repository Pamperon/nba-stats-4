# Daily Top 5 — validation before release (2026-11-01)

Source: [GitHub Actions read-only historical audit](https://github.com/Pamperon/nba-stats-4/actions/runs/41311765314), archived artifact `daily-top5-historical-audit`.

## Reconstructed pregame selections, October 23–30, 2026

| Group | Selected | Resolved | Won | Hit rate | Mean predicted | Brier | Mean odds | Flat-stake ROI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Top 5 | 40 | 37 | 28 | 75.7% | 87.3% | 0.2076 | 1.323 | +1.2% |
| Remaining eligible | 280 | 276 | 174 | 63.0% | 74.0% | 0.2488 | 1.578 | -2.0% |

Values pooled from daily output and rounded; profit and ROI use one theoretical unit per settled line, not actual bets. Three Top-5 and four remaining lines were unresolved and excluded from rate denominators.

## Interpretation and guardrails

- Top-5 display is a **presentation choice**, not a guarantee of performance or a new probability threshold.
- The Top 5 outperformed the remaining lines on historical hit rate and Brier, but the groups have different average odds and sample sizes. Do not claim statistical significance or future profitability.
- Estimated probabilities exceeded observed win rates by approximately 11.7 percentage points (Top 5) and 11.0 points (remaining). Investigate calibration with more **out-of-sample** results before changing probabilities.
- This is **retrospective reconstruction**, not a backtest of exactly the historical published selections. The archive's snapshot rows were selected using `select_daily(..., screen_risks=False)`, so some contemporaneous injury/minutes risk checks were not reproduced. Do not use these results to silently recalibrate live predictions.
- Keep saved pregame odds, probability, and player identity immutable. Resolve final results separately and preserve historical legacy ticket groups.
- The archive and Top 5 must render with zero, fewer than five, or more than five eligible lines; all remaining eligible lines stay accessible.

## Release checklist

- [x] Offline tests passed: [workflow #533](https://github.com/Pamperon/nba-stats-4/actions/runs/41311770418)
- [x] Read-only historical audit passed: [audit](https://github.com/Pamperon/nba-stats-4/actions/runs/41311765314)
- [x] Preserve historical selections and legacy ticket archive
- [x] Keep old live deployment unchanged until merge
- [ ] Confirm production deployment and API response after merge
- [ ] Confirm first actual saved daily scan has `recommendations.policy=daily-lines-v1`, ranked lines and expected saved timestamp
- [ ] Compare future Top 5 against settled outcomes **without** adjusting probabilities based on this tiny historical sample
