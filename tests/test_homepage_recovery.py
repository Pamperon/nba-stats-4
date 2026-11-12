"""Offline regressions for bounded feed decoding and precomputed home responses."""
import io
import json
import os
import time
import tracemalloc
import unittest
from unittest.mock import patch

import odds_feed


class StreamTests(unittest.TestCase):
    def test_stream_matches_existing_projection_for_all_supported_shapes(self):
        fixture = {'fixtureId':'f','tournamentId':132,'bookmakerOdds':{
            'bet365.it':{'bookmakerIsActive':True,'suspended':False,'markets':{
                'keep':{'marketActive':True,'outcomes':{'p':{'price':1.81}}},
                'drop':{'outcomes':[1,2,3]}}}, 'another-book':{'markets':{'x':{}}}}}
        for payload in ([fixture],fixture,{'fixtures':[fixture]}, {'data':{'f':fixture}}):
            with self.subTest(shape=type(payload).__name__):
                streamed=odds_feed.stream_tournament(io.BytesIO(json.dumps(payload).encode()), {'keep'})
                self.assertEqual(odds_feed.slim_tournament(streamed,{'keep'}),
                                 odds_feed.slim_tournament(payload,{'keep'}))

    def test_unused_bulk_markets_do_not_enter_python_object_tree(self):
        payload=[{'fixtureId':'f','tournamentId':132,'bookmakerOdds':{'bet365.it':{
            'markets':{'keep':{'price':1.8},'drop':[{'junk':'x'*100} for _ in range(20000)]}}}}]
        encoded=json.dumps(payload).encode()
        del payload
        def peak(loader):
            tracemalloc.start()
            result=loader()
            size=tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            return result,size
        _,full_peak=peak(lambda:json.loads(encoded))
        result,stream_peak=peak(lambda:odds_feed.stream_tournament(io.BytesIO(encoded),{'keep'}))
        self.assertEqual(set(result[0]['bookmakerOdds']['bet365.it']['markets']),{'keep'})
        self.assertLess(stream_peak,full_peak/3)


class HomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib
        with patch.dict(os.environ,{'NBA_STATS_ACCESS_TOKEN':'offline','ODDSPAPI_API_KEY':'offline'}):
            cls.main=importlib.import_module('main')

    def tearDown(self):
        self.main._compact_picks_cache.clear()
        self.main._performance_cache.clear()

    def test_prepared_response_avoids_calendar_database_and_recomputation(self):
        main=self.main
        payload={'publication_date':'2026-11-12','recommendations':{'lines':[]}}
        main._compact_picks_cache['session']=(payload,time.time()+120)
        main._performance_cache['summary']={'won':10}
        with patch.object(main,'_build_session_picks',side_effect=AssertionError('cold picks')), \
             patch.object(main,'_build_history_performance',side_effect=AssertionError('cold performance')):
            self.assertEqual(main.session_picks(True),payload)
            self.assertEqual(main.public_history_performance(),{'won':10})

    def test_publication_boundary_never_serves_old_preliminary(self):
        main=self.main
        main._compact_picks_cache['session']=({'preliminary':True},time.time()-1)
        with patch.object(main,'_build_session_picks',return_value=({'official':True},time.time()+120)) as build:
            self.assertEqual(main.session_picks(True),{'official':True})
        build.assert_called_once_with(True)
