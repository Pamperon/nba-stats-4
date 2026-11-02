# Bounded database connections — 2 November 2026

The public API opened a fresh TLS PostgreSQL connection for each storage operation. Saved/latest performs multiple reads, while session picks combines an official archive read with fixture coverage reads. The database statement averages measured before this change were 19–41 ms for the three latest-snapshot SELECT shapes; warm API server-to-header samples remained much larger. This is evidence to investigate connection acquisition, not a precise attribution of all server time.

The persistent web process now warms one psycopg_pool 3.3.3 connection before startup and reuses up to four. At most sixteen callers can queue, with a ten-second acquisition timeout. Connections older than five minutes are replaced; excess idle connections shrink after one minute. A checkout health check detects broken connections. TLS remains required, and automatic prepared statements are disabled for compatibility with Supavisor transaction mode. Existing DATABASE_URL, database roles, SQL, transaction boundaries, data and prediction rules are preserved. CLI imports do not start a pool and standalone jobs retain their direct connection behavior.

Shutdown drains running scans before closing the pool. Late work sees the closed pool rather than silently opening unbounded connections. Setting NBA_DATABASE_POOL_ENABLED=0 before process startup preserves the previous direct-connection path. Pool exhaustion and closed-pool errors return a retryable HTTP 503 without private diagnostics. Operational counters are available only through the existing authenticated admin report; no URL or credential is returned. There is no new quote cache or paid provider request.

Validation: 255 offline Python tests and 85 JavaScript tests pass locally, along with the existing isolated tracking and grants/RLS database checks. New tests cover concurrent pool initialization, bounded configuration, startup failure cleanup, the disable switch and shutdown behavior. CI adds a loopback-only PostgreSQL 17 integration on Python 3.14 for actual commit/rollback, transaction-local setting reset, concurrent writes within the four-connection bound, timeout under exhaustion and replacement of an externally terminated connection. The integration refuses non-loopback hosts and never runs against production records. Its local-only TLS override exists in the test script, not application configuration.

Reference behavior checked against the current official psycopg pool guide/API and Supabase connection guide:
- https://www.psycopg.org/psycopg3/docs/advanced/pool.html
- https://www.psycopg.org/psycopg3/docs/api/pool.html
- https://supabase.com/docs/guides/database/connecting-to-postgres

Deployment results and before/after timing samples will be recorded in the pull request after verification. Small synthetic samples are not mobile benchmarks or production percentiles. The public model remains unchanged.
