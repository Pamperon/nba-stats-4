import unittest
from unittest.mock import Mock, MagicMock, patch
import odds_date_probe as probe


class DateProbeTests(unittest.TestCase):
    def test_summarizes_target_coverage_without_exposing_other_fields(self):
        fixture={'fixtureId':'target','startTime':'2026-11-05T00:00:00Z','private':'not returned','bookmakerOdds':{'bet365.it':{'bookmakerIsActive':True,'markets':{'p':{'marketActive':True,'outcomes':{'o':{'players':{'1':{'active':True,'playerName':'Player','price':1.8}}}}}}}}}
        result=probe.summarize([fixture],['target','missing'],{'p':{'marketType':'players-points'}})
        self.assertEqual(result['target_fixture_count'],1)
        self.assertEqual(result['target_coverage'][0]['active_selections'],1)
        self.assertEqual(result['target_coverage'][1]['active_selections'],0)
        self.assertNotIn('private',str(result))

    def test_existing_reservation_is_never_replayed(self):
        connection=MagicMock()
        connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value=({'state':'reserved'},)
        with patch.object(probe.storage,'connection',connection),patch.object(probe,'Caller') as caller:
            self.assertEqual(probe.run_once('secret'),{'reused':True,'state':'reserved'})
        caller.assert_not_called()

    def test_variants_use_distinct_parameters_with_three_call_cap(self):
        conn=MagicMock()
        conn.execute.return_value.fetchone.side_effect=[None,(0,),({'data':[{'fixtureId':'f','startTime':'2026-11-05T00:00:00Z'}]},),({'data':{}},),('reserved',)]
        connection=MagicMock();connection.return_value.__enter__.return_value=conn
        caller=Mock();caller.count=3;caller.history=[]
        caller.get.side_effect=[{},[],[],{'fixtureId':'f','bookmakerOdds':{}}]
        with patch.object(probe.storage,'connection',connection),patch.object(probe,'Caller',return_value=caller) as factory:
            result=probe.run_once('secret')
        self.assertEqual(result['state'],'done');self.assertEqual(result['billable_calls'],3)
        factory.assert_called_once_with('secret',limit=3,job_id=probe.TEST_ID)
        calls=caller.get.call_args_list
        self.assertEqual(calls[1].kwargs['bookmakers'],'bet365.it')
        self.assertEqual(calls[2].kwargs['bookmaker'],'bet365.it')
        self.assertEqual(calls[3].kwargs['fixtureId'],'f')
        self.assertNotIn('secret',str(result))

    def test_probe_endpoint_requires_auth_before_any_provider_call(self):
        import importlib,os
        from fastapi.testclient import TestClient
        with patch.dict(os.environ,{'NBA_STATS_ACCESS_TOKEN':'offline-test-token','ODDSPAPI_API_KEY':'offline-test-key'}):
            main=importlib.import_module('main')
        client=TestClient(main.app);self.addCleanup(client.close)
        with patch.object(probe,'run_once') as run:
            self.assertEqual(client.post('/api/diagnostics/odds-date').status_code,401)
        run.assert_not_called()

class ConfirmedFixtureTests(unittest.TestCase):
    def test_confirmed_fixture_validates_teams_time_and_counts_before_catalog_filter(self):
        fid=next(iter(probe.CONFIRMED));home,away,start=probe.CONFIRMED[fid]
        fixture={'fixtureId':fid,'participant1Name':home,'participant2Name':away,'startTime':start,
                 'bookmakerOdds':{'bet365.it':{'bookmakerIsActive':True,'markets':{'unknown':{
                     'marketActive':True,'outcomes':{'o':{'players':{'p':{'active':True,'playerName':'Player','price':1.8}}}}}}}}}
        result=probe.confirmed_coverage(fixture,fid,{})
        self.assertEqual(result['active_player_outcomes_all_markets'],1)
        self.assertEqual(result['active_selections'],0)
        self.assertTrue(result['bookmaker_present'])
        for changed in ({'startTime':'2026-11-06T01:00:00+01:00'},{'participant1Name':'Other'},{'fixtureId':'wrong'}):
            with self.assertRaises(probe.ProbeError):probe.confirmed_coverage({**fixture,**changed},fid,{})

    def test_confirmed_probe_reuses_prior_result_without_new_calls(self):
        connection=MagicMock();connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value=({'state':'done'},)
        with patch.object(probe.storage,'connection',connection),patch.object(probe,'Caller') as caller:
            self.assertEqual(probe.run_confirmed_once('secret'),{'reused':True,'state':'done'})
        caller.assert_not_called()

    def test_confirmed_probe_calls_only_the_three_screenshot_fixtures(self):
        conn=MagicMock();conn.execute.return_value.fetchone.side_effect=[None,(0,),({'data':{}},),('reserved',)]
        connection=MagicMock();connection.return_value.__enter__.return_value=conn
        caller=Mock();caller.count=3;caller.history=[]
        caller.get.side_effect=[{'fixtureId':fid,'participant1Name':home,'participant2Name':away,'startTime':start,'bookmakerOdds':{}}
                                for fid,(home,away,start) in probe.CONFIRMED.items()]
        with patch.object(probe.storage,'connection',connection),patch.object(probe,'Caller',return_value=caller) as factory:
            result=probe.run_confirmed_once('secret')
        factory.assert_called_once_with('secret',limit=3,job_id=probe.CONFIRMED_ID)
        self.assertEqual(result['state'],'done')
        self.assertEqual([call.kwargs['fixtureId'] for call in caller.get.call_args_list],list(probe.CONFIRMED))
        self.assertTrue(all(call.args==('odds',) for call in caller.get.call_args_list))
        self.assertEqual(len(result['fixtures']),3)

class UnfilteredTests(unittest.TestCase):
    def test_replay_never_calls_provider(self):
        connection=MagicMock();connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value=({'state':'done'},)
        with patch.object(probe.storage,'connection',connection),patch.object(probe,'Caller') as caller:
            self.assertTrue(probe.run_unfiltered_once('secret')['reused'])
        caller.assert_not_called()

    def test_unfiltered_budget_and_source_separation(self):
        fid=next(iter(probe.CONFIRMED));home,away,start=probe.CONFIRMED[fid]
        fixture={'fixtureId':fid,'participant1Name':home,'participant2Name':away,'startTime':start,
                 'bookmakerOdds':{'bet365':{'bookmakerIsActive':True,'markets':{}}}}
        conn=MagicMock();conn.execute.return_value.fetchone.side_effect=[None,(0,),({'data':{}},),('reserved',)]
        connection=MagicMock();connection.return_value.__enter__.return_value=conn
        caller=Mock();caller.count=3;caller.history=[]
        caller.get.side_effect=[[{'slug':'bet365.it','cloneOf':'bet365','private':'secret'}],fixture,[fixture]]
        with patch.object(probe.storage,'connection',connection),patch.object(probe,'Caller',return_value=caller) as factory:
            result=probe.run_unfiltered_once('secret')
        factory.assert_called_once_with('secret',limit=3,job_id=probe.UNFILTERED_ID)
        self.assertEqual(result['state'],'done')
        self.assertFalse(result['single']['bookmaker_present'])
        self.assertTrue(result['single']['sources']['bet365']['bookmaker_present'])
        self.assertEqual([c.args[0] for c in caller.get.call_args_list],['bookmakers','odds','odds-by-tournaments'])
        for call in caller.get.call_args_list:
            self.assertNotIn('bookmakers',call.kwargs);self.assertNotIn('bookmaker',call.kwargs)
        self.assertNotIn('secret',str(result))
        self.assertTrue(all('nba_provider_probe' in c.args[0] for c in conn.execute.call_args_list if c.args[0].startswith(('INSERT','UPDATE'))))

    def test_metadata_request_is_durably_tracked_before_http(self):
        import odds_provider_probe as provider
        import scan_tracking
        conn=MagicMock();connection=MagicMock();connection.return_value.__enter__.return_value=conn
        response=Mock();response.status_code=200;response.json.return_value=[]
        with patch.object(scan_tracking.storage,'connection',connection),patch.object(provider.requests,'get',return_value=response) as get:
            caller=provider.Caller('secret',limit=1,job_id='offline-probe')
            self.assertEqual(caller.get('bookmakers'),[])
        self.assertEqual(caller.count,1)
        self.assertTrue(any('INSERT INTO nba_odds_request_log' in call.args[0] for call in conn.execute.call_args_list))
        get.assert_called_once()
