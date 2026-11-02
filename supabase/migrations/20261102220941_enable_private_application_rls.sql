-- Backend-only tables: application queries run as postgres (BYPASSRLS).
-- No client policies: accidental future client grants must not expose rows.
-- Do not use FORCE ROW LEVEL SECURITY or add permissive public policies.
ALTER TABLE public.nba_scan_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nba_player_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nba_scan_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nba_calibration_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nba_calibration_settled ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nba_scan_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nba_odds_request_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nba_deploy_guard ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nba_recommendation_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nba_provider_probe ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nba_audience_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nba_audience_unique_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nba_audience_unique_seen ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nba_official_daily_top5 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nba_official_daily_singles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nba_official_sessions ENABLE ROW LEVEL SECURITY;
