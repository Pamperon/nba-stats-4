"""Form samples and bounded full-league refresh behavior."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo
import player_form as form

NOW = datetime(2026, 11, 17, 18, tzinfo=ZoneInfo('Europe/Rome'))


def games(recent=30, previous=10, count=12):
    return [{'GAME_ID': str(1000+i), 'GAME_DATE': (NOW-timedelta(days=i+1)).isoformat(),
             'SEASON_TYPE': 2, 'MIN': 30, 'PTS': recent if i < 5 else previous,
             'REB': 8 if i < 5 else 10, 'AST': 5}
            for i in range(count)]


class PlayerFormTests(unittest.TestCase):
    def test_recent_five_and_whole_season_are_sorted_and_deduplicated(self):
        source = games()
        result = form.summarize(list(reversed(source))+[source[0]], NOW)
        self.assertEqual(result['games'], 12)
        self.assertEqual(result['stats']['PTS']['recent_average'], 30)
        self.assertAlmostEqual(result['stats']['PTS']['season_average'], 220/12)
        self.assertAlmostEqual(result['stats']['PTS']['delta'], 30-220/12)
        self.assertEqual(result['stats']['REB']['recent_values'], [8]*5)

    def test_dnp_playoffs_future_and_previous_season_do_not_enter_sample(self):
        source = games()
        extras = [dict(source[0], GAME_ID='dnp', MIN=0, PTS=999),
                  dict(source[0], GAME_ID='po', SEASON_TYPE=3, PTS=999),
                  dict(source[0], GAME_ID='future', GAME_DATE='2026-11-19', PTS=999),
                  dict(source[0], GAME_ID='old', GAME_DATE='2025-11-01', PTS=999)]
        result = form.summarize(source+extras, NOW)
        self.assertEqual(result['games'], 12)
        self.assertEqual(result['stats']['PTS']['recent_average'], 30)

    def test_short_stale_and_incomplete_samples_are_excluded(self):
        self.assertIsNone(form.summarize(games(count=9), NOW))
        self.assertIsNone(form.summarize(games(), NOW+timedelta(days=8)))
        self.assertIsNotNone(form.summarize([dict(g, MIN=5) for g in games()], NOW))
        for value in (None, float('nan'), -1, float('inf'), True):
            source=games();source[0]['PTS']=value
            self.assertIsNone(form.summarize(source, NOW))
        source=games();source[0]['MIN']=None
        self.assertIsNone(form.summarize(source, NOW))
        source=games();source[0]['GAME_DATE']='unknown'
        self.assertIsNone(form.summarize(source, NOW))

    def test_rankings_are_independent_per_market_and_use_one_saved_read(self):
        players=[{'id': str(i), 'team_id': '2', 'team': 'Boston Celtics', 'name': 'Player '+str(i)} for i in range(1,6)]
        saved={'nba:log:final-v4:2:'+p['id']+':2026': {'games': games(recent=10+int(p['id'])*5)} for p in players}
        with patch.object(form.player_stats,'directory',return_value=players), \
             patch.object(form.storage,'cache_read_many',return_value=saved) as read, \
             patch.object(form.player_stats,'player_log',side_effect=AssertionError('No provider loads')):
            result=form.build(NOW)
        read.assert_called_once()
        self.assertEqual(read.call_args.args[1], 6)
        self.assertEqual(result['eligible_players'], 5)
        self.assertEqual([r['id'] for r in result['markets']['PTS']['up']], ['5','4','3'])
        self.assertEqual(result['markets']['PTS']['down'], [])
        self.assertEqual(len(result['markets']['REB']['down']), 3)
        self.assertEqual(result['markets']['AST'], {'up': [], 'down': []})
        self.assertEqual(result['odds_api_calls'], 0)

    def test_read_shares_compact_result_and_retries_failures(self):
        form._cache.clear();self.addCleanup(form._cache.clear)
        with patch.object(form.storage, 'cache_read', return_value=None), patch.object(form,'build',side_effect=[RuntimeError('offline'), {'markets': {}}]) as build:
            with self.assertRaises(RuntimeError):form.read()
            self.assertEqual(form.read(), {'markets': {}})
            self.assertEqual(form.read(), {'markets': {}})
            self.assertEqual(build.call_count, 2)

    def test_endpoint_returns_read_only_projection_and_retryable_error(self):
        import os, importlib
        from fastapi.testclient import TestClient
        with patch.dict(os.environ, {'NBA_STATS_ACCESS_TOKEN': 'test', 'ODDSPAPI_API_KEY': 'test'}), patch.object(form.player_stats.engine, 'API_KEY', 'test'):
            main=importlib.import_module('main')
        with patch.object(form,'read',return_value={'markets': {}, 'odds_api_calls': 0}):
            self.assertEqual(TestClient(main.app).get('/api/players/form').json()['odds_api_calls'], 0)
        with patch.object(form,'read',side_effect=RuntimeError('offline')):
            self.assertEqual(TestClient(main.app).get('/api/players/form').status_code, 503)


class LeagueFormRefreshTests(unittest.TestCase):
    def setUp(self):
        import threading
        self.stop = threading.Event()
        self.players = [{'id': str(i), 'team_id': '2', 'team': 'Boston Celtics', 'name': 'Player '+str(i)} for i in range(1, 5)]
        self.saved = {'nba:log:final-v4:2:1:2026': {'games': games()}}
        form._cache.clear()
        self.addCleanup(form._cache.clear)

    def test_refresh_checks_uncached_players_and_counts_empty_histories(self):
        def log(team, athlete, season):
            return {'games': [] if athlete == '4' else games(recent=30+int(athlete))}
        with patch.object(form.player_stats, 'directory', return_value=self.players), \
             patch.object(form.storage, 'cache_read_many', return_value=self.saved), \
             patch.object(form.storage, 'cache_write') as write, \
             patch.object(form.player_stats, 'player_log', side_effect=log) as load:
            result = form.refresh(self.stop, NOW)
        self.assertEqual({call.args[1] for call in load.call_args_list}, {'2','3','4'})
        self.assertEqual(result['checked_players'], 4)
        self.assertEqual(result['roster_players'], 4)
        self.assertEqual(result['eligible_players'], 3)
        self.assertTrue(result['coverage_complete'])
        self.assertFalse(result['refreshing'])
        self.assertEqual(write.call_args.args[0], 'nba:form:league:v1:2026')
        self.assertNotIn('games', write.call_args.args[1])

    def test_provider_failure_is_partial_and_can_recover_next_cycle(self):
        def log(team, athlete, season):
            if athlete == '3':raise RuntimeError('ESPN temporary failure')
            return {'games': games()}
        with patch.object(form.player_stats, 'directory', return_value=self.players), \
             patch.object(form.storage, 'cache_read_many', return_value=self.saved), \
             patch.object(form.storage, 'cache_write'), \
             patch.object(form.player_stats, 'player_log', side_effect=log):
            result = form.refresh(self.stop, NOW)
        self.assertEqual(result['failed_players'], 1)
        self.assertEqual(result['checked_players'], 3)
        self.assertFalse(result['coverage_complete'])
        with patch.object(form.player_stats, 'directory', return_value=self.players), \
             patch.object(form.storage, 'cache_read_many', return_value=self.saved), \
             patch.object(form.storage, 'cache_write'), \
             patch.object(form.player_stats, 'player_log', return_value={'games': games()}):
            self.assertTrue(form.refresh(self.stop, NOW)['coverage_complete'])

    def test_stop_does_not_publish_incomplete_work_as_complete(self):
        self.stop.set()
        with patch.object(form.player_stats, 'directory') as directory, patch.object(form.storage, 'cache_write') as write:
            self.assertIsNone(form.refresh(self.stop, NOW))
        directory.assert_not_called();write.assert_not_called()

    def test_home_reads_persisted_league_snapshot_without_fetching_histories(self):
        snapshot={'markets': {}, 'checked_players':525, 'coverage_complete':True}
        with patch.object(form.storage,'cache_read',return_value=snapshot), \
             patch.object(form,'build',side_effect=AssertionError('No roster or full histories')):
            self.assertEqual(form.read(),snapshot)

    def test_restart_reuses_fresh_complete_snapshot(self):
        from unittest.mock import Mock
        stop=Mock();stop.wait.side_effect=[False,True];stop.is_set.return_value=False
        snapshot={'checked_players':525, 'roster_players':525, 'coverage_complete':True}
        with patch.object(form.storage,'cache_read',return_value=snapshot), patch.object(form,'refresh') as refresh:
            form.run(stop)
        refresh.assert_not_called()

    def test_background_pauses_for_predictions_and_continues_after(self):
        from unittest.mock import Mock
        busy=Mock(side_effect=[True,False,False])
        stop=Mock();stop.is_set.return_value=False;stop.wait.return_value=False
        with patch.object(form.player_stats,'directory',return_value=self.players), \
             patch.object(form.storage,'cache_read_many',return_value=self.saved), \
             patch.object(form.storage,'cache_write'), \
             patch.object(form.player_stats,'player_log',return_value={'games':games()}):
            result=form.refresh(stop,NOW,busy)
        stop.wait.assert_called_once_with(10)
        self.assertTrue(result['coverage_complete'])
