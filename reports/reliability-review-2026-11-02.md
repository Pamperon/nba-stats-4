# Basket Lab: reliability audit, 2 November 2026

Source inspected: `85c7bfaaebc3b615fee0082dd03eb2af09aa5211`. Supabase read-only reconciliation against finalized ESPN boxscores, using Europe/Rome tipoff dates. No bookmaker API calls, settlement writes, historical selection edits, or public probability changes.

## Data reconciliation

All 11 daily settlement records reproduce exactly: **9,083 eligible predictions, 8,793 binary matches (96.81%), 290 gaps**.

| Classification | Lines | Distinct player-games |
| --- | ---: | ---: |
| Explicit ESPN didNotPlay | 109 | 8 |
| Athlete absent from exact fixture's boxscore | 181 | 14 |

The second category remains unresolved. It is not evidence of a loss, an automatic bookmaker refund, or an explicit DNP. Do not borrow outcomes from another date or another fixture. There were no missing fixtures, post-tipoff snapshots, pushes, or date-boundary discrepancies in this settled cohort. All source snapshots remain available. See `reliability-audit-2026-11-02.json` for each affected line and date.

No identical matched lines repeat within the daily snapshots, but the 8,793 lines represent only **630 player-games**, with multiple thresholds and markets tied to the same outcomes. These are not 8,793 independent trials. Historical daily calibration is an all-lines diagnostic, not the performance of the published Top 5.

## Parallel model evaluation

The repository already captures frozen pregame alternatives (`weights-v1`). This audit takes the earliest stored shadow snapshot per date, chosen without outcome ranking. Seven dates were inspected; six have nonempty panels. Of 1,098 frozen panel selections, 1,069 are independently verified. Each model is evaluated on the same rows. No candidate was fitted to this evaluation set. November 2's earliest snapshot has an empty panel; no later snapshot was substituted to improve coverage.

| Model | Mean forecast | Observed | Brier |
| --- | ---: | ---: | ---: |
| Public baseline weights | 61.73% | 59.21% | 0.24952 |
| Last 40 games | 61.11% | 59.21% | 0.24805 |
| Current season + prior | 61.30% | 59.21% | 0.24799 |

On **points alone (430 panel lines)**, the baseline forecasts 62.50% against 56.05% observed. Its Brier is 0.25246, compared with 0.25423 for last 40 and 0.25404 for current season + prior. The alternatives are worse on this key market despite their small pooled improvement. This panel differs from the earlier 75 recommended-line sample; their percentages must not be directly compared.

**Decision: no public model promotion.** Six nonempty dates, correlated markets/player outcomes, and inconsistent per-market performance do not establish a robust improvement. Continue prospective collection under frozen candidate definitions. A later evaluation needs more independent game dates, market-specific calibration, uncertainty clustered by game/date, and an untouched final evaluation period. Changing prior-season weights alone does not resolve points overconfidence.

Current baseline uses 80% pooled historical hit frequency and 20% recent-20 frequency with Jeffreys smoothing. Current season may contain few observations. Minutes, starts, role changes and teammate availability need timestamped pregame features; adding today's injury information to older predictions would introduce hindsight. Minutes diagnostics already run in shadow mode; further feature changes remain experimental.

## Safe implementation changes

- Added read-only settlement-gap CLI and line-by-line reason classification, retaining identity/date/timestamp guards.
- Added `/admin/monitor` and authenticated `/api/admin/monitor`: coverage, weighted calibration by market, 12 recent scans/attempts, actual feed download timestamps, HTTP requests distinct from quote lines, partial-scan issues and minutes diagnostics.
- Administrative data responses use `no-store`; password remains in the page, not browser storage. Logout clears data and invalidates late responses. CSP blocks framing and external script/connect destinations. The HTML login shell is public; monitoring data requires the existing server-side administrative bearer token.
- Added compact transport options. Session forecasts preserve official/preliminary picks and all counts without transferring the entire quote list a second time. Saved quote responses retain all explanation observations and values, projecting logs to the four fields actually used by the browser. Default API formats remain compatible.
- Coverage reads now project only JSONB results rather than full logs and shadow research. Existing partial-scan merge/cache behavior is retained.
- Removed unreachable obsolete homepage fixture-rendering code after an unconditional return.
- Repaired stale scheduler, selection, settlement and archive UI test fixtures without loosening public rules. Added private-monitor, logout race, gap-classification and compact-transport tests. Failed DOM tests now close windows instead of leaving test processes running indefinitely.
- Added a manually invocable post-deploy verification workflow using the existing repository administrative secret. It checks the exact published commit and real authenticated monitoring behavior. It is deliberately separate from required predeploy CI to avoid a deployment/check dependency cycle.

## Security and operational limits

All 16 public-schema tables have RLS disabled. Direct privilege inspection found no SELECT/INSERT/UPDATE/DELETE grants to `anon` or `authenticated`, so the list-tables tool's generic claim of unrestricted public CRUD was not supported. Supabase security/performance advisors returned no findings. Residual TRUNCATE/REFERENCES/TRIGGER privileges warrant a separate compatibility review; RLS alone does not restrict TRUNCATE. No schema or privilege changes were made during this audit.

Render MCP has no selected workspace. It lists `My Workspace` (`tea-dbd83esipgvc73edd8ig`) but explicitly requires user confirmation before using that workspace. Public health/HTTP verification is available independently. Render's internal service status, logs and metrics are not claimed verified.

Initial public probes returned HTTP 200 on health, saved dates, saved quotes, history dates, session picks and home. Baseline decoded responses measured about 3.4 MB for saved quotes and 2.0 MB for session picks; gzip was already enabled. Proxy round-trip overhead is several seconds even for health, so these timings are not user mobile performance benchmarks. The private `/api/schedule` endpoint correctly returned 401; public calendar checks use `/api/nba/fixtures`.

Release state and final verification are recorded in the pull request and this work's completion message, rather than assuming that a saved commit is online.
