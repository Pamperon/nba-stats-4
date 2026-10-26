"""Latency regressions using synchronization, without external requests."""
import threading
import unittest
from unittest.mock import patch
import engine
import player_stats

class StatsLatencyTests(unittest.TestCase):
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
