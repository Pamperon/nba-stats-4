import copy
from datetime import datetime
import importlib
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import nba_session_picks

with patch.dict(os.environ, {'NBA_STATS_ACCESS_TOKEN': 'offline-test-token', 'ODDSPAPI_API_KEY': 'offline-test-key'}):
    main = importlib.import_module('main')


class CompactTransportTests(unittest.TestCase):
    def test_saved_logs_keep_exact_scoring_history_without_mutating_archive(self):
        snapshot = {'date': '2026-10-23', 'results': [{'Giocatore': 'A'}],
                    'player_logs': {'A': [{'GAME_DATE': '2026-10-20', 'PTS': 20, 'AST': 4, 'REB': 6,
                                          'MIN': 32, 'OTHER': 'unused'*100}]}}
        original = copy.deepcopy(snapshot)
        client = TestClient(main.app)
        self.addCleanup(client.close)
        with patch.object(main.storage, 'configured', return_value=True), \
             patch.object(main.storage, 'latest', return_value=snapshot), \
             patch.object(main, 'visible_snapshot', return_value=snapshot):
            compact = client.get('/api/saved/latest?date=2026-10-23&compact=true').json()
            full = client.get('/api/saved/latest?date=2026-10-23').json()
        self.assertEqual(full, original)
        self.assertEqual(snapshot, original)
        self.assertEqual(compact['results'], full['results'])
        self.assertEqual(compact['player_logs']['A'], [{'GAME_DATE': '2026-10-20', 'PTS': 20, 'AST': 4, 'REB': 6}])

    def test_compact_session_keeps_frozen_picks_and_counts(self):
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 11, 2, 19, tzinfo=tz)
        manifest = {'games': [{'home': 'Home', 'away': 'Away', 'upcoming': True,
                               'start_at': '2026-11-03T02:00:00+01:00'}],
                    'start_at': '2026-11-02T18:00:00+01:00', 'end_at': '2026-11-03T12:00:00+01:00'}
        row = {'Partita': 'Home - Away', 'Giocatore': 'A', 'Mercato': 'PTS', 'Linea': 10.5, 'Scelta': 'Over'}
        official = {'lines': [row], 'single': None, 'policy': 'frozen'}
        with patch.object(main, 'datetime', Clock), \
             patch.object(main, 'nba_publication_session', return_value=manifest), \
             patch.object(main.storage, 'recent_fixture_coverage', return_value=[row]), \
             patch.object(nba_session_picks, 'read', return_value=official):
            full = main.session_picks(compact=False)
            compact = main.session_picks(compact=True)
        self.assertEqual(full['results'], [row])
        self.assertEqual(compact, {**full, 'results': []})
        self.assertEqual(compact['quote_count'], 1)
