"""Live scoreboard consistency, shared refreshes and retryable provider failures."""
import importlib
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch
from cachetools import TTLCache
import requests

with patch.dict(os.environ, {'NBA_STATS_ACCESS_TOKEN': 'offline-test', 'ODDSPAPI_API_KEY': 'offline-test'}):
    main = importlib.import_module('main')


def payload(state='in', away='24', home='22', points='10'):
    return {'header': {'competitions': [{
        'status': {'type': {'state': state, 'description': 'In Progress' if state == 'in' else 'Final'}, 'period': 2, 'displayClock': '10:00'},
        'competitors': [{'homeAway': 'home', 'score': home, 'linescores': [{'displayValue': home}]},
                        {'homeAway': 'away', 'score': away, 'linescores': [{'displayValue': away}]}]}]},
        'boxscore': {'players': [{'team': {'displayName': 'Boston Celtics'}, 'statistics': [{
            'labels': ['MIN','PTS','REB','AST'], 'athletes': [{'athlete': {'id': '22', 'displayName': 'Alex'},
                                                          'stats': ['8', points, '2', '1']}]}]}]}}


class LiveBoxscoreTests(unittest.TestCase):
    def setUp(self):
        main._boxscore_cache.clear()
        self.addCleanup(main._boxscore_cache.clear)

    def test_state_scores_quarters_and_players_share_one_summary(self):
        response=Mock();response.json.return_value=payload()
        with patch.object(main.requests,'get',return_value=response) as get:
            result=main.public_nba_boxscore('123456')
        self.assertEqual(result['game']['away_score'],'24')
        self.assertEqual(result['game']['home_score'],'22')
        self.assertEqual(result['game']['display_clock'],'10:00')
        self.assertEqual(result['quarters'][0], {'period':1,'label':'Q1','away':'24','home':'22'})
        self.assertEqual(result['teams'][0]['players'][0]['points'],'10')
        self.assertEqual(result['odds_api_calls'],0)
        self.assertIn('/summary',get.call_args.args[0])

    def test_shared_short_cache_expires_and_transitions_to_final(self):
        clock=[0];cache=TTLCache(maxsize=4,ttl=20,timer=lambda:clock[0])
        response=Mock();response.json.side_effect=[payload(),payload('post','110','100','30')]
        with patch.object(main,'_boxscore_cache',cache),patch.object(main.requests,'get',return_value=response) as get:
            self.assertEqual(main.public_nba_boxscore('123456')['state'],'in')
            main.public_nba_boxscore('123456');self.assertEqual(get.call_count,1)
            clock[0]=21
            final=main.public_nba_boxscore('123456')
        self.assertEqual(final['state'],'post')
        self.assertEqual(final['game']['away_score'],'110')
        self.assertEqual(final['teams'][0]['players'][0]['points'],'30')
        self.assertEqual(get.call_count,2)

    def test_provider_error_is_not_cached_and_next_tick_can_retry(self):
        response=Mock();response.json.return_value=payload()
        with patch.object(main.requests,'get',side_effect=[requests.RequestException('offline'),response]) as get:
            with self.assertRaises(main.HTTPException):main.public_nba_boxscore('123456')
            self.assertEqual(main.public_nba_boxscore('123456')['state'],'in')
        self.assertEqual(get.call_count,2)

    def test_concurrent_visitors_share_a_provider_read(self):
        entered,release=threading.Event(),threading.Event()
        response=Mock();response.json.return_value=payload()
        def fetch(*args,**kwargs):
            entered.set();release.wait(2);return response
        with patch.object(main.requests,'get',side_effect=fetch) as get, ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(main.public_nba_boxscore,'123456');self.assertTrue(entered.wait(1))
            second=pool.submit(main.public_nba_boxscore,'123456');release.set()
            self.assertEqual(first.result(2),second.result(2))
        self.assertEqual(get.call_count,1)
