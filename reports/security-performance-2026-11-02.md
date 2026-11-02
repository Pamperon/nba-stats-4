# Security and transport optimization — 2 November 2026

## Supabase: applied and verified

The application accesses PostgreSQL from its backend using DATABASE_URL; the browser has no Supabase REST/client-library integration. Client SELECT/INSERT/UPDATE/DELETE were already denied, but anon/authenticated retained TRUNCATE, REFERENCES, TRIGGER and MAINTAIN privileges.

Migration `20261102220330_restrict_client_table_privileges` removes all table privileges for those two roles from the sixteen named application tables. It also removes automatic client table grants for future public-schema tables created by postgres. Server/service-role grants, table contents, existing selections and calibration records are not altered. Supabase-managed schemas and defaults belonging to supabase_admin are outside this migration's scope.

Verified directly after application:

- All sixteen tables checked for both client roles: no effective SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER or MAINTAIN privilege.
- Neither client role has CREATE on public.
- No client-callable SECURITY DEFINER functions in public.
- No remaining postgres/public default table grants to those roles.
- Supabase security advisor returns no WARNING/ERROR findings. After RLS activation it reports sixteen INFO-only “RLS enabled, no policy” notices: intentional for backend-only tables with no client grants. [Linter reference](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).
- Public saved-date, saved-quote and session endpoints still return HTTP 200 after the migration.

The migration is tested twice against isolated PostgreSQL/PGlite, including newly created tables, denial of client grants, preservation of trusted server grants and successful server reads/writes. CI now includes this check.

A second migration, `20261102220941_enable_private_application_rls`, enables RLS on all sixteen application tables with no client-access policies. Before applying it, the database statement history confirmed that the application snapshot query runs as postgres (5,125 recorded calls), and role metadata confirmed postgres owns all sixteen tables and has BYPASSRLS. The isolated test also verifies that an accidental SELECT grant cannot expose rows to anon, while trusted server access still works. Production verification confirms all sixteen tables have RLS enabled and both client roles have no table privileges. No FORCE RLS or permissive public policy was added. Future frontend access must define explicit grants and appropriate row policies; future postgres-created tables are protected by default-denied client grants and should enable RLS before being exposed.

Reference verified: https://supabase.com/docs/guides/api/securing-your-api

## Lighter public quote responses

The browser reads saved player_logs only in pickExplanation, for displayed selections. Compact responses now transfer those players' frozen logs, preserving every observation and the four fields already used by that explanation. All quote rows, selections, probabilities, player statistics and the full-format API are unchanged. Legacy snapshots without a recognized selection manifest retain their old compact behavior.

The pre-deploy compact response contained 150 players' logs: 2,498,030 decoded bytes and 211,295 compressed bytes. Replaying the same payload through the projection retains six players' logs and predicts about 146,900 compressed bytes. Published measurements are recorded separately after deployment; projections are not a real mobile benchmark.

## Requests and timing

Concurrent session refreshes now share one in-flight request. Later refreshes remain fresh requests; no new TTL cache was introduced. The request is aborted after twenty seconds so a hung request cannot permanently hold subsequent refreshes. Failures release the in-flight slot and can retry.

API responses add a Server-Timing app duration measured until response headers. It includes work performed before those headers are emitted and does not buffer streaming responses. It is not download duration or p95 latency. The administrative monitor displays its local request-and-body-read duration separately from this server duration. These measurements collect no visitor data and add no external analytics requests.

The client's actual mobile network and painting performance cannot be inferred from the assistant's proxy connection. These headers and the private monitor provide measurements in the browser that is actually being used, while deployment verification checks response sizes and unchanged content.

## Validation

249 offline Python tests, JavaScript/DOM regressions, isolated tracking/database integration, the new privilege/RLS migration integration, compilation and diff checks are run before merge. Relevant cases cover streaming-body preservation, exact frozen selection logs, legacy payloads, concurrent refresh coalescing, bounded abort/retry and retry after failure. Public model definitions and selection policies are unchanged.
