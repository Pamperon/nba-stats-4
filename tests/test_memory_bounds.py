"""Memory retention must be bounded without changing data used by the UI/model."""
import copy
import unittest
from unittest.mock import patch, MagicMock
from datetime import date
import match_history
import storage
import settle_espn
import engine
import odds_feed
import nba_hub
import pandas as pd
from memory_cache import bounded_cache, payload_size, remember

class MemoryBoundsTests(unittest.TestCase):
    def test_nested_response_growth_evicts_before_byte_budget_is_exceeded(self):
        cache = bounded_cache(0.01, 60)
        for index in range(100):
            payload = {'players': [{'name': str(index), 'data': 'x' * 2048}]}
            self.assertTrue(remember(cache, index, payload))
            self.assertLessEqual(cache.currsize, cache.maxsize)
        self.assertLess(len(cache), 10)
        self.assertEqual(cache[99], payload)
        self.assertGreater(payload_size(pd.DataFrame({'name': ['x' * 5000]})), 5000)
        cyclic = []
        cyclic.append(cyclic)
        self.assertGreater(payload_size(cyclic), 0)

    def test_oversized_espn_roster_is_returned_intact_without_retention(self):
        engine.espn_roster.cache_clear()
        self.addCleanup(engine.espn_roster.cache_clear)
        payload = {'athletes': [], 'large': 'x' * (7 * 1024 * 1024)}
        with patch.object(engine, 'espn_json', return_value=payload):
            self.assertIs(engine.espn_roster('1'), payload)
        self.assertEqual(len(engine.espn_roster.cache), 0)

    def test_oversized_paid_feed_reuses_persistence_without_another_download(self):
        saved = {}
        data = {'lines': 'x' * 5000}
        loader = MagicMock(return_value=data)
        with patch.object(odds_feed, '_MEMORY', bounded_cache(0.001, 60)), \
             patch.object(odds_feed.storage, 'configured', return_value=True), \
             patch.object(odds_feed.storage, 'cache_read', side_effect=lambda key, **kw: saved.get(key)), \
             patch.object(odds_feed.storage, 'cache_write', side_effect=lambda key, value: saved.update({key: value})):
            first = odds_feed.cached_payload('feed:v1:slot', 60, loader)
            second = odds_feed.cached_payload('feed:v1:slot', 60, loader)
        self.assertEqual(first['data'], data)
        self.assertEqual(second['data'], data)
        self.assertEqual(first['fetched_at'], second['fetched_at'])
        self.assertEqual(second['source'], 'cache')
        loader.assert_called_once()

    def test_oversized_nba_response_does_not_fail_the_shared_request(self):
        payload = {'events': [], 'large': 'x' * 5000}
        response = MagicMock()
        response.json.return_value = payload
        with patch.object(nba_hub, '_cache', bounded_cache(0.001, 60)), \
             patch.object(nba_hub.requests, 'get', return_value=response):
            self.assertIs(nba_hub.fetch('/test'), payload)
        self.assertNotIn('/test', nba_hub._pending)

    def test_odds_timestamp_metadata_follows_byte_eviction(self):
        with patch.object(engine, 'odds_cache', bounded_cache(0.001, 60)), \
             patch.object(engine, '_odds_cache_fetched_at', {}):
            for index in range(100):
                engine._remember_odds(str(index), {'data': str(index) * 100}, 1000)
            self.assertEqual(set(engine._odds_cache_fetched_at), set(engine.odds_cache))
            self.assertLess(len(engine._odds_cache_fetched_at), 10)

    def test_quote_cache_does_not_retain_every_expired_time_bucket(self):
        storage._cached_fixture_coverage.cache_clear()
        self.addCleanup(storage._cached_fixture_coverage.cache_clear)
        row={'Partita':'A - B','Giocatore':'Player','Quota':1.8,'Prob. stimata %':75}
        conn=MagicMock()
        conn.execute.return_value.fetchall.return_value=[({'results':[row]},)]
        with patch.object(storage,'connection') as connection:
            connection.return_value.__enter__.return_value=conn
            for bucket in range(40):
                result=storage._cached_fixture_coverage('2026-11-05',24,bucket)
                self.assertEqual(result,(row,))
        self.assertLessEqual(storage._cached_fixture_coverage.cache_info().currsize,2)

    def test_history_projection_preserves_form_inputs_without_mutating_source(self):
        event={'id':'game','date':'2026-11-01T00:00Z','status':{'type':{'state':'post','completed':True}},
               'competitions':[{'competitors':[{'team':{'displayName':'A','logos':['large']},'score':'110'},
                                               {'team':{'displayName':'B'},'score':'100'}]}],
               'links':['large'],'headlines':['unused']}
        original=copy.deepcopy(event)
        compact=match_history.compact_event(event)
        self.assertEqual(compact['id'],event['id'])
        self.assertEqual(compact['date'],event['date'])
        self.assertEqual(compact['status'],event['status'])
        self.assertEqual([(c['team']['displayName'],c['score']) for c in compact['competitions'][0]['competitors']], [('A','110'),('B','100')])
        self.assertNotIn('headlines',compact)
        self.assertEqual(event,original)

    def test_old_persistent_history_is_compacted_before_entering_memory(self):
        event={'id':'g','links':['unused']}
        payload={'date':'2026-11-05','complete':True,'events':[event]}
        match_history._windows.clear()
        self.addCleanup(match_history._windows.clear)
        with patch.object(storage,'configured',return_value=True),patch.object(storage,'cache_read',return_value=payload):
            events,failed=match_history.load_window(date(2026,11,5))
        self.assertEqual((events,failed),([{'id':'g'}],0))
        self.assertIn('links',event)

    def test_settlement_projection_preserves_played_and_dnp_evidence(self):
        summary={'plays':['unused']*1000,'boxscore':{'players':[{'team':{'displayName':'A'},'statistics':[{
            'labels':['PTS','AST','REB'],'athletes':[
                {'athlete':{'id':'1','displayName':'Played'},'stats':['12','2','8']},
                {'athlete':{'id':'2','displayName':'Absent'},'didNotPlay':True,'stats':[]}]}]}]},
            'article':{'story':'A was without <a href="https://www.espn.com/nba/player/_/id/2/absent">Absent</a>.'}}
        compact=settle_espn.compact_summary(summary)
        self.assertEqual(settle_espn.player_stats(compact),settle_espn.player_stats(summary))
        self.assertTrue(compact['boxscore']['players'][0]['statistics'][0]['athletes'][1]['didNotPlay'])
        self.assertEqual(compact['article']['story'],summary['article']['story'])
        self.assertNotIn('plays',compact)
