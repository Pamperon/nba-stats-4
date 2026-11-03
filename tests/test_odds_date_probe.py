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
