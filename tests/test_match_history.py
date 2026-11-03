"""Shared history must reduce IO while preserving complete verified samples."""
import importlib
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import Mock,patch
import requests
import match_history as history

class MatchHistoryTests(unittest.TestCase):
    def setUp(self):
        history._daily.clear();history._windows.clear()
    def tearDown(self):
        history._daily.clear();history._windows.clear()
    def test_concurrent_windows_share_exactly_21_daily_requests(self):
        response=Mock();response.json.return_value={'events':[]}
        with patch.object(history.storage,'configured',return_value=False),patch.object(history.requests,'get',return_value=response) as fetch:
            with ThreadPoolExecutor(max_workers=3) as pool:
                result=list(pool.map(history.load_window,[date(2026,11,5)]*3))
        self.assertEqual(result,[([],0)]*3)
        self.assertEqual(fetch.call_count,21)
        self.assertEqual(len({c.kwargs['params']['dates'] for c in fetch.call_args_list}),21)
    def test_complete_saved_window_avoids_all_espn_calls(self):
        events=[{'id':'verified'}]
        with patch.object(history.storage,'configured',return_value=True),patch.object(history.storage,'cache_read',return_value={'date':'2026-11-05','complete':True,'events':events}),patch.object(history.requests,'get') as fetch:
            self.assertEqual(history.load_window(date(2026,11,5)),(events,0))
            self.assertEqual(history.load_window(date(2026,11,5)),(events,0))
            fetch.assert_not_called()
    def test_partial_window_is_retried_and_not_persisted(self):
        with patch.object(history.storage,'configured',return_value=False),patch.object(history,'persist_cache') as persist,patch.object(history,'daily_events',side_effect=requests.Timeout):
            self.assertEqual(history.load_window(date(2026,11,5)),([],21))
            self.assertEqual(len(history._windows),0)
            persist.assert_not_called()
        with patch.object(history.storage,'configured',return_value=False),patch.object(history,'daily_events',return_value=[]) as fetch:
            self.assertEqual(history.load_window(date(2026,11,5)),([],0))
            self.assertEqual(fetch.call_count,21)
    def test_market_enrichment_reads_one_envelope_and_retains_order(self):
        with patch.dict(os.environ,{'NBA_STATS_ACCESS_TOKEN':'offline-test-token','ODDSPAPI_API_KEY':'offline-test-key'}):
            main=importlib.import_module('main')
        with patch.object(main.storage,'configured',return_value=True),patch.object(main.storage,'cache_read',return_value={}) as read:
            self.assertEqual(main._match_market_data('2026-11-05','Boston Celtics','Atlanta Hawks'),{'moneyline_odds':None})
            read.assert_called_once()
    def test_complete_and_warm_match_statistics_are_identical(self):
        with patch.dict(os.environ,{'NBA_STATS_ACCESS_TOKEN':'offline-test-token','ODDSPAPI_API_KEY':'offline-test-key'}):
            main=importlib.import_module('main')
        main._match_form_cache.clear()
        event={'id':'1','date':'2026-11-02T23:00:00Z','status':{'type':{'state':'post'}},'competitions':[{'competitors':[{'score':'110','team':{'displayName':'Boston Celtics'}},{'score':'100','team':{'displayName':'Atlanta Hawks'}}]}]}
        with patch.object(history,'load_window',return_value=([event],0)) as load,patch.object(main,'_match_market_data',return_value={'moneyline_odds':None}):
            cold=main.match_form('2026-11-05','Boston Celtics','Atlanta Hawks')
            warm=main.match_form('2026-11-05','Boston Celtics','Atlanta Hawks')
            self.assertEqual(cold,warm);load.assert_called_once()
            self.assertEqual(cold['teams'][0]['wins'],1)
            self.assertEqual(cold['teams'][0]['avg_points'],110)
            self.assertEqual(cold['teams'][1]['losses'],1)
            self.assertEqual(cold['h2h'][0]['scores'],[110,100])
        main._match_form_cache.clear()
