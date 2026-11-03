# Basket Lab: section loading, prewarming and browser release checks

Baseline: b7e483f (after the first optimization cycle). Model, probability formulas, thresholds, official selections and settlement logic are untouched.

## Delivered changes

1. A single background loop waits until the server has started, then checks at most three dates in the next 72 hours. Only future fixtures warm historical windows. It shares the existing complete-only cache, respects existing TTLs, stops cooperatively and isolates provider errors. No OddsPapi scan, paid service, queue or schema migration.
2. Home/Pronostici request compact session selections rather than full saved quote snapshots. Quotes load when their section opens. Statistics and archives avoid unrelated prediction requests. Active sections refresh expired data; hidden sections do not poll. A failed session request retains the existing archive fallback. Actual saved metadata supplies the update timestamp.
3. Calendar transport, archived ticket rendering, quarter/player boxscore rendering and match-player rendering have separate modules. Archive, boxscore and match-player code downloads only when needed, with retryable/deduplicated asset loading. The coordinator retains navigation state and request tokens.
4. Mobile tab events are restricted to the legacy tab bar: previously the handler also captured bottom navigation buttons and could call `.click()` on a missing tab. The new browser suite caught this existing bug.
5. Every relevant PR gets Chromium checks for desktop and Pixel 7 emulation. Each run compares the same fixed baseline and candidate on the same runner. Tests cover direct routes, Back/Forward, archive values, match charts, players, quote delays, JS exceptions and unnecessary API requests. CI records JSON metrics and failure traces. Syntax checks include every JS module recursively.

## Measured first section-loading candidate

See `browser-section-loading.json`, GitHub Actions run 41654444959, candidate f5eaa046. Three samples per profile. Synthetic read-only API fixtures, a 1200 ms quote delay, blocked third-party images; mobile: CPU x4, latency 150 ms, download 200000 B/s, upload 100000 B/s. Local fixture server does not simulate production gzip, backend latency or actual ESPN variability. Service workers are blocked to measure a repeatable cold frontend.

| Metric (median of 3) | Baseline | Section loading |
| --- | --- | --- |
| Home API requests, including headshots | 9 | 4 |
| Desktop selections visible | 260 ms | 256 ms |
| Mobile selections visible | 2973 ms | 2948 ms |
| Mobile LCP (lab) | 2536 ms | 2548 ms |
| Mobile CLS | 0 | 0 |

The clear result is lower API fanout and the fixed mobile navigation error. First-paint/selection timing is essentially unchanged in this small sample; do not advertise a meaningful loading-time percentage. These are browser lab measurements, not physical-device tests or field Core Web Vitals. Final module extraction is tested against the same baseline again before merge.

## Safety and limits

Caches never replace missing data with synthetic production values. Incomplete history is retried rather than treated as complete. First load before background warmup can still depend on ESPN. Warming can finish after startup but never delays readiness. API/admin data remains excluded from the existing service worker. No service-worker scope migration is part of this change.

The original app/hub still coordinate legacy controls. These changes isolate concrete components without a framework migration. GitHub checks run on PRs; repository protection and Render trigger settings were not altered. A reversible PR revert remains the rollback procedure.

## Repeat locally or in CI

`npm ci`

`npx playwright install --with-deps chromium`

`npm test`

`npm run test:browser`

`python scripts/run_offline_tests.py`

Local browser download was restricted in the execution environment; the actual Chromium runs completed on GitHub's pinned Ubuntu 24.04 runner.


## Final module run and release budget

Run 41655776703 re-tested final module candidate 81093d184 against the same baseline (three samples each). Mobile median selections: 3012 → 2957 ms; mobile LCP: 2564 → 2520 ms. Home API fanout remains 9 → 4. This remains a small controlled sample with essentially stable first-load timing, not a guaranteed production percentage. `browser-final.json` contains every sample.

The release check now compares candidate medians with baseline medians on the same runner. It fails if selections or LCP regress by more than 25% + 250 ms, if measurements are missing, or if Home exceeds four API requests in this fixture. Tests separately fail on JS exceptions, navigation/data errors, hidden match analysis during quote loading, or missing player lines. These are lab regression limits, not claimed Core Web Vitals targets.

`/api/health` exposes `history_warmup` state, completion timestamp and successfully warmed dates (no credentials or user data). This permits read-only production verification that the worker actually completed a cycle, without initiating scans or restarting the service.

Final local verification: 102 JavaScript tests and 287 Python tests. Chromium desktop/mobile tests run on GitHub before merge. All model-related source files remain unchanged from b7e483f.

## Live fixture-order correction

Production verification found a stored `Detroit Pistons - Philadelphia 76ers` quote fixture displayed as `Philadelphia 76ers - Detroit Pistons` by the calendar. The prior exact-order comparison hid existing player quotes. Match-day lookup now compares the two normalized team identities without depending on order; it still reads only the currently selected date and returns original saved rows unchanged. It does not change prices, probabilities, line selection, model or fixture orientation in the UI. Diagnostics use the same identity. The browser fixture deliberately reverses provider order so the candidate must show player quotes; baseline player matching is a documented known failure. Local JavaScript tests: 103.

`warmup-live.json` records the read-only health verification of the operational warmup on production, including the successfully prepared dates. This is distinct from synthetic browser measurements.
