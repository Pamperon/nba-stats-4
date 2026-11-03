"""Final score display uses verified ESPN evidence and cannot change predictions."""
import unittest
import os
import importlib
from fastapi.testclient import TestClient
from unittest.mock import patch
import player_stats


def payload(final=True, score='120'):
    return {'header': {'id': '123', 'competitions': [{'status': {'type': {'completed': final}}, 'competitors': [
        {'homeAway': 'home', 'score': score, 'team': {'id': '2', 'abbreviation': 'BOS', 'displayName': 'Boston Celtics'}},
        {'homeAway': 'away', 'score': '115', 'team': {'id': '18', 'abbreviation': 'NYK', 'displayName': 'New York Knicks'}}]}]},
        'boxscore': {'large': 'unneeded payload'}}


class GameDetailsTests(unittest.TestCase):
    def read(self, data):
        with patch.object(player_stats, 'cached', side_effect=lambda key, hours, loader: loader()), \
             patch.object(player_stats.engine, 'espn_json', return_value=data):
            return player_stats.game_details('123')

    def test_only_compact_final_score_returned(self):
        result = self.read(payload())
        self.assertEqual(result['home']['score'], 120)
        self.assertEqual(result['away']['abbreviation'], 'NYK')
        self.assertEqual(result['event_id'], '123')
        self.assertTrue(result['final'])
        self.assertNotIn('boxscore', result)

    def test_live_unknown_or_inconsistent_results_never_published(self):
        for data in [payload(False), payload(None), payload(True, 'NaN'), payload(True, '115')]:
            with self.assertRaises(ValueError): self.read(data)
        data = payload();data['header']['id'] = '456'
        with self.assertRaises(ValueError): self.read(data)
        data = payload();data['header']['competitions'][0]['competitors'][1]['homeAway'] = 'home'
        with self.assertRaises(ValueError): self.read(data)

    def test_successful_score_uses_shared_persistent_cache(self):
        key='nba:game-details:v1:123'
        player_stats._historical_cache.pop(key, None)
        try:
            with patch.object(player_stats.storage, 'cache_read', return_value=None), \
                 patch.object(player_stats, 'persist_cache') as persist, \
                 patch.object(player_stats.engine, 'espn_json', return_value=payload()) as fetch:
                first=player_stats.game_details('123');second=player_stats.game_details('123')
            self.assertEqual(first,second);fetch.assert_called_once();persist.assert_called_once()
        finally: player_stats._historical_cache.pop(key,None)


class GameDetailsHttpTests(unittest.TestCase):
    def test_public_endpoint_is_bounded_and_does_not_use_odds(self):
        with patch.dict(os.environ, {'NBA_STATS_ACCESS_TOKEN': 'offline-test-token', 'ODDSPAPI_API_KEY': 'offline-test-key'}):
            app=importlib.import_module('main')
        client=TestClient(app.app)
        try:
            with patch.object(player_stats, 'game_details', return_value={'event_id':'123','final':True}) as read:
                self.assertEqual(client.get('/api/players/game?event_id=invalid').status_code,422)
                read.assert_not_called()
                result=client.get('/api/players/game?event_id=123')
                self.assertEqual(result.status_code,200)
                self.assertEqual(result.json()['odds_api_calls'],0)
            with patch.object(player_stats, 'game_details', side_effect=ValueError('Not final')):
                self.assertEqual(client.get('/api/players/game?event_id=123').status_code,404)
        finally: client.close()
