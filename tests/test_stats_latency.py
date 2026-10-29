"""Latency regressions using synchronization, without external requests."""
import threading
from datetime import datetime
import unittest
from unittest.mock import patch
import engine
import pandas as pd
import player_stats

class StatsLatencyTests(unittest.TestCase):
    def test_public_player_log_returns_minutes_and_preserves_missing(self):
        frame = pd.DataFrame([
            {"GAME_ID": "12345", "GAME_DATE": pd.Timestamp("2026-10-25"), "PTS": 20, "REB": 4, "AST": 3, "SEASON_TYPE": 2, "MATCHUP": "vs BOS", "MIN": "28:30"},
            {"GAME_DATE": pd.Timestamp("2026-10-24"), "PTS": 10, "REB": 3, "AST": 2, "SEASON_TYPE": 2, "MATCHUP": "? LAL", "MIN": None},
        ])
        with patch.object(player_stats, 'validate_season', return_value=(2026, 2026)), \
             patch.object(player_stats, 'cached', side_effect=lambda key, hours, loader: loader()), \
             patch.object(player_stats, 'roster', return_value=[{'id': '123'}]), \
             patch.object(engine, 'selected_game_log', return_value=frame), \
             patch.object(engine, 'prepare_game_log', return_value=frame):
            result = player_stats.player_log('1', '123', '2026')
        self.assertEqual(result['games'][0]['MIN'], 28.5)
        self.assertEqual(result['games'][0]['GAME_ID'], '12345')
        self.assertIsNone(result['games'][1]['MIN'])
        self.assertEqual(result['games'][1]['MATCHUP'], '? LAL')

    def test_completed_seasons_use_long_cache_but_current_season_stays_fresh(self):
        with patch.object(player_stats, 'datetime') as clock:
            clock.now.return_value = datetime(2026, 10, 26)
            self.assertEqual(player_stats.log_cache_hours(2026), 6)
            self.assertEqual(player_stats.log_cache_hours(2025), 720)
            clock.now.return_value = datetime(2026, 2, 1)
            self.assertEqual(player_stats.log_cache_hours(2025), 6)
            self.assertEqual(player_stats.log_cache_hours(2024), 720)

    def test_completed_season_revisit_avoids_database_and_provider(self):
        key = 'historical-cache-test'
        player_stats._historical_cache.pop(key, None)
        try:
            with patch.object(player_stats.storage, 'cache_read', return_value={'games': []}) as read:
                player_stats.cached(key, 720, lambda: self.fail('Saved season must not reload ESPN'))
                player_stats.cached(key, 720, lambda: self.fail('Revisit must use server memory'))
            self.assertEqual(read.call_count, 1)
        finally:
            player_stats._historical_cache.pop(key, None)

    def test_independent_schedules_are_requested_concurrently(self):
        engine.espn_season_schedule_payloads.cache_clear()
        self.addCleanup(engine.espn_season_schedule_payloads.cache_clear)
        barrier = threading.Barrier(2)
        def fetch(url, **params):
            barrier.wait(timeout=2)
            return {'events': []}
        with patch.object(engine, 'espn_json', side_effect=fetch) as request:
            result = engine.espn_season_schedule_payloads('latency-test', 2027)
        self.assertEqual([kind for kind, _ in result], [2, 3])
        self.assertEqual(request.call_count, 2)

    def test_slow_persistence_does_not_block_stats_response(self):
        started, release, finished = threading.Event(), threading.Event(), threading.Event()
        key = 'latency-test'
        player_stats._memory_cache.pop(key, None)
        def write(*args):
            started.set()
            release.wait(timeout=3)
            finished.set()
        try:
            with patch.object(player_stats.storage, 'cache_read', return_value=None), patch.object(player_stats.storage, 'cache_write', side_effect=write):
                result = player_stats.cached(key, 1, lambda: {'games': []})
                self.assertEqual(result, {'games': []})
                self.assertTrue(started.wait(timeout=2))
                self.assertFalse(finished.is_set())
                release.set()
                self.assertTrue(finished.wait(timeout=2))
        finally:
            release.set()
            player_stats._memory_cache.pop(key, None)

    def test_saved_log_does_not_require_catalog_or_roster_round_trips(self):
        player_stats._memory_cache.clear()
        payload = {'games': [{'PTS': 12}], 'athlete_id': '123', 'season': '2026'}
        with patch.object(player_stats.storage, 'cache_read', return_value=payload) as read, patch.object(player_stats, 'roster', side_effect=AssertionError('Unneeded roster request')):
            self.assertEqual(player_stats.player_log('1', '123', '2026'), payload)
        self.assertEqual(read.call_count, 1)
        player_stats._memory_cache.clear()

    def test_uncached_log_still_checks_roster(self):
        player_stats._memory_cache.clear()
        with patch.object(player_stats.storage, 'cache_read', return_value=None), patch.object(player_stats, 'roster', return_value=[]), patch.object(engine, 'selected_game_log') as load:
            with self.assertRaises(ValueError):
                player_stats.player_log('1', '123', '2026')
            load.assert_not_called()

    def test_concurrent_visitors_share_one_cold_load(self):
        from concurrent.futures import ThreadPoolExecutor
        key = 'single-flight-test'
        started, release = threading.Event(), threading.Event()
        player_stats._memory_cache.pop(key, None)
        def load():
            started.set()
            self.assertTrue(release.wait(timeout=2))
            return {'games': []}
        with patch.object(player_stats.storage, 'cache_read', return_value=None), patch.object(player_stats, 'persist_cache'), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(player_stats.cached, key, 1, load)
            self.assertTrue(started.wait(timeout=2))
            second = pool.submit(player_stats.cached, key, 1, lambda: self.fail('Duplicate provider load'))
            release.set()
            self.assertEqual(first.result(timeout=2), second.result(timeout=2))
        player_stats._memory_cache.pop(key, None)

    def test_team_batch_reads_only_current_roster_and_season_without_espn(self):
        player_stats._memory_cache.clear()
        key = 'nba:log:final-v4:1:123:2026'
        payload = {'athlete_id': '123', 'season': '2026', 'games': []}
        with patch.object(player_stats, 'roster', return_value=[{'id': '123'}]), patch.object(player_stats.storage, 'cache_read_many', return_value={key: payload, 'unrelated': {}}) as read, patch.object(engine, 'selected_game_log', side_effect=AssertionError('Batch must not call providers')):
            self.assertEqual(player_stats.team_cached_logs('1', '2026'), {'123': payload})
        read.assert_called_once_with([key], 6)

    def test_failed_shared_load_can_be_retried(self):
        key = 'failed-single-flight-test'
        player_stats._memory_cache.pop(key, None)
        with patch.object(player_stats.storage, 'cache_read', return_value=None), patch.object(player_stats, 'persist_cache'):
            with self.assertRaises(ValueError):
                player_stats.cached(key, 1, lambda: (_ for _ in ()).throw(ValueError('Unavailable')))
            self.assertNotIn(key, player_stats._pending)
            self.assertEqual(player_stats.cached(key, 1, lambda: {'games': []}), {'games': []})
        player_stats._memory_cache.pop(key, None)

    def test_directory_reuses_rosters_without_loading_statistics(self):
        teams = [{'id': '1', 'name': 'Boston Celtics'}, {'id': '2', 'name': 'Miami Heat'}]
        with patch.object(player_stats, 'cached', side_effect=lambda key, hours, loader: loader()), \
             patch.object(player_stats, 'catalog', return_value=teams), \
             patch.object(player_stats, 'roster', side_effect=lambda team: [{'id': team + '1', 'name': 'Same Name'}]) as rosters, \
             patch.object(engine, 'selected_game_log', side_effect=AssertionError('No game downloads')), \
             patch.object(engine, 'get_json', side_effect=AssertionError('No OddsPapi')):
            result = player_stats.directory()
        self.assertEqual([(p['id'], p['team_id']) for p in result], [('11', '1'), ('21', '2')])
        self.assertEqual(rosters.call_count, 2)

    def test_directory_does_not_cache_a_partial_roster_failure(self):
        key = 'nba:player-directory:v1'
        player_stats._memory_cache.pop(key, None)
        teams = [{'id': '1', 'name': 'Boston Celtics'}, {'id': '2', 'name': 'Miami Heat'}]
        def load(team):
            if team == '2':
                raise RuntimeError('ESPN unavailable')
            return [{'id': '11', 'name': 'First Player'}]
        with patch.object(player_stats.storage, 'cache_read', return_value=None), \
             patch.object(player_stats, 'persist_cache') as persist, \
             patch.object(player_stats, 'catalog', return_value=teams), \
             patch.object(player_stats, 'roster', side_effect=load):
            with self.assertRaises(RuntimeError):
                player_stats.directory()
            self.assertNotIn(key, player_stats._memory_cache)
            persist.assert_not_called()
