"""Validate quote freshness locally, without bookmaker requests."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import engine


class OddsCacheTests(unittest.TestCase):
    def setUp(self):
        engine.odds_cache.clear()
        engine._odds_cache_fetched_at.clear()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.cache_dir = Path(folder.name)
        self.path_patch = patch.object(engine, '_CACHE_DIR', self.cache_dir)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)

    def test_disk_rehydration_does_not_restart_quote_lifetime(self):
        timestamp = 1000000000.0
        path = self.cache_dir / 'fixture.json'
        path.write_text('{"bookmakerOdds":{}}')
        os.utime(path, (timestamp, timestamp))
        with patch.object(engine.time, 'time', return_value=timestamp + 10700):
            self.assertEqual(engine._cache_read('fixture')[1], 'disk')
        # The in-memory TTL just started, but the downloaded data is already old.
        with patch.object(engine.time, 'time', return_value=timestamp + 10801):
            self.assertEqual(engine._cache_read('fixture'), (None, 'none', None))

    def test_scan_reusing_odds_does_not_rewrite_download_timestamp(self):
        fixture = {'fixtureId': 'fixture', 'participant1Name': 'A', 'participant2Name': 'B', 'startTime': '2026-10-26T20:00:00Z'}
        row = {'Giocatore': 'A Player', 'Linea': 4.5, 'Over': 1.8, 'Tipo': 'Soglia +'}
        with patch.object(engine, 'finder_player_index', return_value={}), patch.object(engine, 'historical_player_index', return_value={}), patch.object(engine, '_cache_read', return_value=({}, 'disk', 1000000000.0)), patch.object(engine, '_odds_diagnostics', return_value={}), patch.object(engine, 'odds_source_audit', return_value=[]), patch.object(engine, 'parse_odds', return_value=([row], {})), patch.object(engine, '_cache_write') as write, patch.object(engine, 'get_odds') as paid:
            result = engine.finder_scan([fixture], {}, '2026-27', 15, 1.01, 20, -100)
        self.assertTrue(result[0])
        write.assert_not_called()
        paid.assert_not_called()
        self.assertEqual(result[-1][0]['origine'], 'disk')

    def test_new_download_is_cached_and_reports_original_time(self):
        with patch.object(engine.time, 'time', return_value=1000000000.0):
            engine._cache_write('fixture', {'bookmakerOdds': {}})
            payload, source, timestamp = engine._cache_read('fixture')
        self.assertEqual(source, 'memory')
        self.assertEqual(timestamp, 1000000000.0)
