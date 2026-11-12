import copy
import unittest
from unittest.mock import patch
import player_explorer

class PlayerExplorerTests(unittest.TestCase):
    def test_previews_use_one_saved_batch_and_never_fetch_individual_logs(self):
        import player_stats
        player_stats._directory_previews.clear()
        self.addCleanup(player_stats._directory_previews.clear)
        players=[{'id':'22','team_id':'2','name':'Alex','team':'Boston'}]
        games=[{'GAME_DATE':'2026-11-01','PTS':20,'REB':5,'AST':2}]
        def saved(keys, hours):
            self.assertEqual(hours,6)
            return {next(iter(keys)):games}
        with patch.object(player_stats,'directory',return_value=players), \
             patch.object(player_stats.storage,'cached_player_previews',side_effect=saved) as read, \
             patch.object(player_stats,'player_log',side_effect=AssertionError('No ESPN fetch')):
            first=player_stats.directory_with_previews()
            second=player_stats.directory_with_previews()
        self.assertEqual(first[0]['preview_games'],games)
        self.assertEqual(first,second)
        self.assertEqual(read.call_count,1)
        self.assertNotIn('preview_games',players[0])

    def test_projection_preserves_prices_and_only_keeps_ten_saved_games(self):
        row={'ESPN ID':'22','Giocatore':'Test, Alex','Squadra':'Boston Celtics','Mercato':'PTS','Linea':10.5,'Quota':1.9,'Scelta':'Over','Partita':'A - B','Prob. stimata %':75,'private':'no'}
        source={'date':'2026-11-05','results':[row], 'player_logs':{'Test, Alex':[{'GAME_DATE':f'2026-10-{n:02d}','PTS':n,'private':'no'} for n in range(1,22)],'Other':[{'GAME_DATE':'2026-10-01','PTS':99}]}}
        original=copy.deepcopy(source)
        result=player_explorer.project(source)
        self.assertEqual(source,original)
        self.assertEqual(result['rows'][0]['Quota'],1.9)
        self.assertEqual(result['rows'][0]['Prob. stimata %'],75)
        self.assertNotIn('private',result['rows'][0])
        self.assertEqual(len(result['logs']['Test, Alex']),10)
        self.assertEqual(result['logs']['Test, Alex'][0]['GAME_DATE'],'2026-10-21')
        self.assertNotIn('Other',result['logs'])
        self.assertNotIn('private',result['logs']['Test, Alex'][0])
        self.assertEqual(result['odds_api_calls'],0)

    def test_invalid_prices_and_missing_history_are_not_invented(self):
        rows=[{'Giocatore':'X','Mercato':'PTS','Quota':p} for p in [None,'bad',float('nan'),float('inf'),1,0]]
        rows.append({'Giocatore':'Y','Mercato':'AST','Quota':1.5})
        result=player_explorer.project({'results':rows})
        self.assertEqual(len(result['rows']),1)
        self.assertEqual(result['logs'],{})

    def test_endpoint_caches_only_compact_data_and_does_not_scan(self):
        import os,importlib
        with patch.dict(os.environ,{'NBA_STATS_ACCESS_TOKEN':'test','ODDSPAPI_API_KEY':'test'}):
            main=importlib.import_module('main')
        main.players_explorer_cache.clear()
        try:
            with patch.object(main.storage,'latest',return_value={'date':'2026-11-05','results':[]}) as saved, patch.object(main.storage,'recent_fixture_coverage',return_value=[]),patch.object(main,'visible_snapshot',side_effect=lambda x:x):
                self.assertEqual(main.players_explorer()['odds_api_calls'],0)
                self.assertEqual(main.players_explorer()['rows'],[])
                saved.assert_called_once()
                self.assertNotIn('player_logs',main.players_explorer_cache['data'])
        finally:main.players_explorer_cache.clear()
