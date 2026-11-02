-- Basket Lab accesses these tables through trusted backend PostgreSQL sessions.
-- Existing client CRUD is already denied. Remove residual dangerous privileges,
-- including TRUNCATE/REFERENCES/TRIGGER/MAINTAIN, without changing server grants.
REVOKE ALL PRIVILEGES ON TABLE
  public.nba_scan_snapshots,
  public.nba_player_cache,
  public.nba_scan_slots,
  public.nba_calibration_daily,
  public.nba_calibration_settled,
  public.nba_scan_attempts,
  public.nba_odds_request_log,
  public.nba_deploy_guard,
  public.nba_recommendation_results,
  public.nba_provider_probe,
  public.nba_audience_daily,
  public.nba_audience_unique_daily,
  public.nba_audience_unique_seen,
  public.nba_official_daily_top5,
  public.nba_official_daily_singles,
  public.nba_official_sessions
FROM anon, authenticated;

-- Only tables created by the application owner in public are covered here.
-- Supabase-managed schemas and service_role grants remain unchanged.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL PRIVILEGES ON TABLES FROM anon, authenticated;
