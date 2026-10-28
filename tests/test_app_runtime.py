"""HTTP and scan lifecycle regressions; external I/O is mocked throughout."""
import contextlib
import datetime as dt
import importlib
import io
import os
import socket
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

with patch.dict(os.environ, {'NBA_STATS_ACCESS_TOKEN': 'offline-test-token', 'ODDSPAPI_API_KEY': 'offline-test-key'}):
    main = importlib.import_module('main')


class AppRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.network = patch.object(socket.socket, 'connect', side_effect=AssertionError('Network is disabled'))
        self.network.start()
        self.addCleanup(self.network.stop)
        feed = patch.object(main.engine, 'get_tournament_odds',
                            return_value={'data': {}, 'fetched_at': 1000000000, 'source': 'api'})
        feed.start()
        self.addCleanup(feed.stop)
        main.jobs.clear()
        heartbeat = patch.object(main, '_scan_heartbeat')
        heartbeat.start()
        self.addCleanup(heartbeat.stop)
        finish = patch.object(main.scan_tracking, 'finish_attempt')
        finish.start()
        self.addCleanup(finish.stop)
        # No context manager: these HTTP tests do not run startup or the scheduler.
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def test_public_search_metadata(self):
        home = self.client.get('/')
        self.assertEqual(home.status_code, 200)
        self.assertIn('<title>Basket Lab | Statistiche e analisi NBA</title>', home.text)
        self.assertIn('rel="canonical" href="https://basketlab.it/"', home.text)
        robots = self.client.get('/robots.txt')
        self.assertEqual(robots.status_code, 200)
        self.assertIn('Sitemap: https://basketlab.it/sitemap.xml', robots.text)
        sitemap = self.client.get('/sitemap.xml')
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn('application/xml', sitemap.headers['content-type'])
        self.assertIn('<loc>https://basketlab.it/</loc>', sitemap.text)

    def test_scan_requires_authentication(self):
        with patch.object(main.engine, 'get_fixtures') as odds:
            self.assertEqual(self.client.post('/api/scan?date=2026-10-25').status_code, 401)
            odds.assert_not_called()

    def test_archive_includes_exact_saved_history_only_when_requested(self):
        snapshot = {'date':'2026-10-23', 'season':'2026-27',
                    'scan_finished_at':'2026-10-23T16:00:00+00:00',
                    'player_logs':{'Saved Player':[{'GAME_ID':'before', 'PTS':12}]}}
        with patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'latest', return_value=snapshot):
            compact = self.client.get('/api/saved/archive?date=2026-10-23').json()
            expanded = self.client.get('/api/saved/archive?date=2026-10-23&include_logs=true').json()
        self.assertNotIn('player_logs', compact)
        self.assertEqual(expanded['player_logs'], snapshot['player_logs'])
        self.assertEqual(expanded['scan_finished_at'], snapshot['scan_finished_at'])

    def test_parallel_research_is_not_sent_in_public_snapshot(self):
        snapshot={'date':'2026-10-27','results':[], 'model_shadow':{'probability_panel':['large research data']}}
        with patch.object(main,'schedule',return_value={'games':[]}):
            result=main.visible_snapshot(snapshot)
        self.assertNotIn('model_shadow',result)
        self.assertIn('model_shadow',snapshot)

    def test_saved_time_reports_actual_http_requests_including_zero(self):
        for count in (0, 4):
            snapshot = {'saved_at': '2026-10-25T11:48:23+00:00', 'odds_api_http_requests_scan': count, 'quote_lines_scan': 328}
            with patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'latest', return_value=snapshot):
                response = self.client.get('/api/saved/time?date=2026-10-25')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['odds_api_requests_scan'], count)
            self.assertEqual(response.json()['quote_lines_scan'], 328)

    def test_legacy_snapshot_never_invents_http_request_count(self):
        snapshot = {'saved_at': '2026-10-25T11:48:23+00:00', 'odds_api_calls_scan': 328}
        with patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'latest', return_value=snapshot):
            response = self.client.get('/api/saved/time?date=2026-10-25')
        self.assertEqual(response.json()['odds_api_requests_scan'], 'non misurate')
        self.assertIsNone(response.json()['odds_api_http_requests_scan'])

    def test_job_survives_restart_even_when_newer_snapshot_exists(self):
        snapshot = {'job_id': 'older', 'date': '2026-10-25', 'state': 'done'}
        with patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'by_job_id', return_value=snapshot) as read:
            response = self.client.get('/api/scan/older', headers={'Authorization': 'Bearer ' + main.TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['job_id'], 'older')
        read.assert_called_once_with('older')

    def test_storage_lookup_uses_requested_job(self):
        connection = MagicMock()
        connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (
            'older', {'date': '2026-10-25'}, dt.datetime(2026, 10, 25, tzinfo=dt.timezone.utc))
        with patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'connection', connection):
            result = main.storage.by_job_id('older')
        self.assertEqual(result['job_id'], 'older')
        execute = connection.return_value.__enter__.return_value.execute
        self.assertEqual(execute.call_args.args[1], ('older',))
        self.assertIn('WHERE job_id=%s', execute.call_args.args[0])

    def test_complete_scan_saves_count_and_partial_state(self):
        for status in ('ok', 'vuota'):
            main.jobs['offline'] = {'date': '2026-10-25', 'state': 'queued', 'scan_source': 'github'}
            report = [{'stato': status}]
            connection = MagicMock()
            connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
            with patch.object(main.engine, 'get_fixtures', return_value=[{}]), patch.object(main.engine, 'fixture_is_upcoming', return_value=True), patch.object(main.engine, 'get_markets', return_value={}), patch.object(main.engine, 'finder_scan', return_value=([], [], 328, 0, [], [], {}, report)), patch.object(main.engine, 'odds_api_request_count', return_value=4), patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'connection', connection), patch.object(main.storage, 'save') as save, contextlib.redirect_stdout(io.StringIO()) as log:
                main.do_scan('offline', '2026-10-25')
            saved = save.call_args.args[1]
            self.assertEqual(saved['state'], 'done' if status == 'ok' else 'partial')
            self.assertEqual(saved['odds_api_http_requests_scan'], 4)
            self.assertIn('odds_api_http_requests=4', log.getvalue())
            self.assertTrue(main.jobs['offline']['cloud_saved'])
            self.assertNotIn('results', main.jobs['offline'])
            self.assertNotIn('player_logs', main.jobs['offline'])

    def test_saved_job_is_restored_instead_of_retaining_full_snapshot_in_memory(self):
        main.jobs['saved'] = {'state': 'done', 'cloud_saved': True}
        snapshot = {'job_id':'saved', 'date':'2026-10-25', 'state':'done',
                    'results':[{'Giocatore':'A','Quota':1.8}], 'player_logs':{'A':[]}}
        headers = {'Authorization': 'Bearer ' + main.TOKEN}
        with patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'by_job_id', return_value=snapshot) as read:
            result = self.client.get('/api/scan/saved', headers=headers)
            self.assertEqual(result.json()['results'], snapshot['results'])
            main.jobs.clear()  # CSV remains usable after process restart too.
            csv = self.client.get('/api/scan/saved/csv', headers=headers)
        self.assertEqual(read.call_count, 2)
        self.assertEqual(csv.status_code, 200)
        self.assertIn('Giocatore', csv.text)
        self.assertIn('A', csv.text)
        self.assertFalse(main.jobs)

    def test_database_outage_does_not_report_saved_job_as_missing_or_empty(self):
        main.jobs['saved'] = {'state':'done', 'cloud_saved':True}
        with patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'by_job_id', side_effect=RuntimeError('db unavailable')), self.assertLogs(main.logger, 'ERROR'):
            response = self.client.get('/api/scan/saved', headers={'Authorization':'Bearer '+main.TOKEN})
        self.assertEqual(response.status_code, 503)

    def test_unsaved_results_remain_available_for_emergency_export(self):
        main.jobs['unsaved'] = {'state':'save_failed', 'results':[{'Giocatore':'A','Quota':1.8}]}
        with patch.object(main.storage, 'by_job_id', side_effect=AssertionError('No database read')):
            response = self.client.get('/api/scan/unsaved/csv', headers={'Authorization':'Bearer '+main.TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertIn('A', response.text)

    def test_public_snapshot_expiry_tracks_next_tipoff_and_delays_recheck_without_looping(self):
        now = dt.datetime.now(dt.timezone.utc)
        future = now + dt.timedelta(hours=1)
        snapshot = {'date':'2026-10-29','results':[]}
        game = {'home':'A','away':'B','upcoming':True,'start_at':future.isoformat()}
        with patch.object(main, 'schedule', return_value={'games':[game]}):
            result = main.visible_snapshot(snapshot)
        self.assertEqual(result['visibility_valid_until'], future.isoformat())
        game['start_at'] = (now-dt.timedelta(minutes=5)).isoformat()
        with patch.object(main, 'schedule', return_value={'games':[game]}):
            result = main.visible_snapshot(snapshot)
        expiry = dt.datetime.fromisoformat(result['visibility_valid_until'])
        self.assertGreater(expiry, now + dt.timedelta(seconds=59))
        self.assertLess(expiry, now + dt.timedelta(seconds=65))
        with patch.object(main, 'schedule', return_value={'games':[]}):
            self.assertIsNone(main.visible_snapshot(snapshot)['visibility_valid_until'])

    def test_large_responses_are_compressed_without_changing_snapshot_contents(self):
        snapshot = {'date':'2026-10-29', 'results':[{'Giocatore':'Player','Nota':'x'*10000}]}
        with patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'latest', return_value=snapshot), patch.object(main, 'visible_snapshot', return_value=snapshot):
            response = self.client.get('/api/saved/latest?date=2026-10-29', headers={'Accept-Encoding':'gzip'})
        self.assertEqual(response.headers.get('content-encoding'), 'gzip')
        self.assertEqual(response.json(), snapshot)
        self.assertLess(int(response.headers['content-length']), 1000)

    def test_shadow_failure_cannot_change_or_block_live_predictions(self):
        import availability
        import shadow_study
        main.jobs['shadow-test']={'state':'queued','scan_source':'test'}
        row={'Giocatore':'Player','ESPN ID':'123','Squadra':'A','Partita':'A - B',
             'Mercato':'PTS','Scelta':'Over','Linea':9.5,'Quota':1.8,
             'Prob. stimata %':80,'Value stimato %':44,'Partite':30,
             'Stagione %':80,'Minuti medi':30,'Minuti ultime 5':29,
             'Stato analisi':'Valutabile (stima empirica)',
             '_shadow_probabilities':{'candidate':.1}}
        connection=MagicMock()
        connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value=[]
        with patch.object(main.engine,'get_fixtures',return_value=[{}]), patch.object(main.engine,'fixture_is_upcoming',return_value=True), patch.object(main.engine,'get_markets',return_value={}), patch.object(main.engine,'finder_scan',return_value=([row],[],0,1,[],[],{},[{'stato':'ok'}])), patch.object(main.storage,'configured',return_value=True), patch.object(main.storage,'connection',connection), patch.object(main.storage,'save') as save, patch.object(availability,'check',side_effect=lambda rows:(rows,{})), patch.object(shadow_study,'capture',side_effect=RuntimeError('Optional research unavailable')), self.assertLogs(main.logger,'ERROR'), contextlib.redirect_stdout(io.StringIO()):
            main.do_scan('shadow-test','2026-10-27')
        saved=save.call_args.args[1]
        self.assertEqual(saved['state'],'done')
        self.assertEqual(saved['results'][0]['Prob. stimata %'],80)
        self.assertNotIn('_shadow_probabilities',saved['results'][0])
        self.assertIsNone(saved['model_shadow'])

    def test_failed_scan_records_requests_and_error_without_saving(self):
        main.jobs['offline'] = {'date': '2026-10-25', 'state': 'queued'}
        with patch.object(main.engine, 'get_fixtures', side_effect=RuntimeError('Simulated provider failure')), patch.object(main.engine, 'odds_api_request_count', return_value=2), patch.object(main.storage, 'save') as save, self.assertLogs(main.logger, 'ERROR'), contextlib.redirect_stdout(io.StringIO()) as log:
            main.do_scan('offline', '2026-10-25')
        self.assertEqual(main.jobs['offline']['state'], 'error')
        self.assertEqual(main.jobs['offline']['odds_api_http_requests_scan'], 2)
        self.assertIn('odds_api_http_requests=2', log.getvalue())
        save.assert_not_called()

    def test_started_games_are_removed_from_public_snapshot(self):
        snapshot = {'date': '2026-10-25', 'results': [
            {'Partita': 'Boston Celtics - New York Knicks', 'Giocatore': 'A'},
            {'Partita': 'Miami Heat - Orlando Magic', 'Giocatore': 'B'}]}
        with patch.object(main, 'schedule', return_value={'games': [
                {'home': 'Boston Celtics', 'away': 'New York Knicks', 'upcoming': False},
                {'home': 'Miami Heat', 'away': 'Orlando Magic', 'upcoming': True}]}):
            result = main.visible_snapshot(snapshot)
        self.assertEqual([r['Giocatore'] for r in result['results']], ['B'])
        self.assertEqual(len(snapshot['results']), 2)


class FixtureCounterTests(unittest.TestCase):
    def test_upcoming_games_count_even_without_provider_odds(self):
        snapshot = {'date': '2026-10-27', 'results': [], 'fixture_count': 0}
        games = [
            {'home': 'Boston Celtics', 'away': 'Chicago Bulls', 'upcoming': True},
            {'home': 'Miami Heat', 'away': 'Dallas Mavericks', 'upcoming': True},
            {'home': 'New York Knicks', 'away': 'Orlando Magic', 'upcoming': False}]
        with patch.object(main, 'schedule', return_value={'games': games}):
            result = main.visible_snapshot(snapshot)
        self.assertEqual(result['fixture_count'], 2)
        self.assertEqual(result['results'], [])
        self.assertEqual(result['player_count'], 0)
        self.assertEqual(snapshot['fixture_count'], 0)

    def test_finished_games_are_not_counted(self):
        with patch.object(main, 'schedule', return_value={'games': [
                {'home': 'Boston Celtics', 'away': 'Chicago Bulls', 'upcoming': False}]}):
            result = main.visible_snapshot({'date': '2026-10-27', 'results': [], 'fixture_count': 1})
        self.assertEqual(result['fixture_count'], 0)
