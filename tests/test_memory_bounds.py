"""Memory retention must be bounded without changing data used by the UI/model."""
import copy
import unittest
from unittest.mock import patch, MagicMock
from datetime import date
import match_history
import storage
import settle_espn

class MemoryBoundsTests(unittest.TestCase):
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
