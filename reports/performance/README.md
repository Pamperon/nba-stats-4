# Basket Lab performance audit — 3 November 2026

Baseline production commit: bdb1c78. PR 182 (charts) and 183 (progressive calendar/client cache) merged; PR 184 was open at baseline. Render service srv-dbd86sifngtc73fv09l0, main, Frankfurt, 0.5 CPU/512 MB, one Python instance. Auto-deploy on commit; no infrastructure migration performed.

## Measurements before architectural changes

See baseline-http.json (three requests per endpoint). First observation is not a guaranteed empty server cache.

| Request | Server processing | HTTP total from execution environment |
| --- | --- | --- |
| Health | 0.51–0.57 ms | 4.08–4.22 s |
| Fixtures, Nov 5 | 1.32–9.04 ms | 3.94–4.08 s |
| Match form, first observed | 2538.77 ms | 6.59 s |
| Match form, repeats | 272.14–281.19 ms | 4.23–4.97 s |

The roughly four-second transport overhead also affects tiny health responses. Do not present these HTTP totals as mobile Core Web Vitals or promise the same improvement on users' phones. Browser smoke checks were possible, but browser performance APIs were unavailable and local Chromium was not installed. Real mobile hardware, LCP/INP/CLS, throttled network percentiles remain unmeasured.

Baseline: 89 JavaScript tests passed. PR 184 plus regression: 90 JS and 276 Python tests passed. Existing GitHub CI (including PostgreSQL pool tests) passed before merging PR 184.

## Findings

* Calendar-to-match navigation waited for quotes-loaded when changing dates. PR 184 removes this dependency and preserves late-response guards.
* Cold match analysis requests 21 ESPN daily scoreboards, seven at a time. Server daily cache reduces repeat traffic; overlapping requests can duplicate cold loads.
* Warm match form still reads the saved odds envelope twice to enrich prices and fixture metadata. This is independent of statistical calculation.
* SPA views had no canonical path/history. Session restoration could override explicit destinations without a router.
* app.js (~74 KB) and hub-nav.js (~77 KB baseline) mix UI, transport and presentation. Splitting makes safe follow-up optimization possible; splitting by itself does not reduce total transferred bytes.
* Production CPU samples do not show sustained saturation; memory observed ~353 MB. Render returned no HTTP latency series. No justification for changing paid infrastructure yet.
* Existing gzip and API Server-Timing are already enabled. API and admin data must remain outside service-worker caches.

## Architecture and release sequence

1. Tested immediate match navigation (PR 184).
2. Explicit shell routes: /, /pronostici, /partite, /analisi-partita?data=YYYY-MM-DD&trasferta=...&casa=..., /archivio; retain /statistiche, /analisi-quote, /come-funziona and legacy hashes. Isolate router, match charts and match request cache. Share current DOM and calculations. Unknown API/assets must remain 404.
3. Deduplicate backend scoreboard requests and saved-odds enrichment; do not cache incomplete history as complete. No changes to engine, probabilities, publication thresholds, settlements or provider scan schedule.
4. Compare identical requests and deterministic navigation tests after each stage. Merge only passing PR heads, verify Render live commit and read-only smoke requests.

Rollback: revert the relevant PR and let main auto-deploy. All changes are code-only and reversible, with no schema or stored-data migrations. Previous root/hash links remain supported.

## Repeatable checks

`python scripts/measure_http.py --output reports/performance/after-http.json`

`npm test`

`NBA_STATS_ACCESS_TOKEN=offline-test-token ODDSPAPI_API_KEY=offline-test-key python -m unittest discover -s tests`

Do not publish a speedup percentage unless the same cache state and measurement method have been compared. Separate time to visible screen from time to complete external data.

## Backend and delivery changes

* `match_history.py`: bounded daily/window caches and fixed-size locks. Simultaneous requests for the same 21-day window issue 21 daily requests in total, rather than 21 per visitor. A complete persisted window avoids all 21 ESPN requests after a process restart. Cache age remains 30 minutes; daily cache remains two hours.
* Partial windows are not persisted, not entered in the match-form cache and not retained by the browser cache. A retry can recover missing days. Statistical processing and verified-final filtering stay in the existing endpoint.
* One saved odds envelope now supplies both price and fixture metadata on cold and warm responses. Warm enrichment uses one database read rather than two. No paid quote calls.
* Versioned static resources receive a one-day browser cache; unversioned files (including the service worker) revalidate. HTML always revalidates. API/admin data is never added to these caches.
* Deterministic verification: 93 JS and 282 Python tests passed locally, including concurrent requests, persistent cache reuse, incomplete sample retry, exact cold/warm stats equality, one-envelope enrichment and static cache policy.

These are request-count guarantees verified with controlled inputs, not measured mobile speedup percentages. The first request for a genuinely uncached historical window still depends on ESPN response time. No synthetic data substitutes for slow external data.
