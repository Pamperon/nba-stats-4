"""The current-single analysis is read-only and bound to saved pregame data."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import unittest
import single_analysis

ROW={'Giocatore':'James, LeBron','Partita':'A - B','Mercato':'PTS','Scelta':'Over','Linea':14.5,'Quota':1.9,'Prob. stimata %':74}
class SingleAnalysisTests(unittest.TestCase):
    def session(self):
        return {'date':'2026-11-04','saved_at':'2026-11-04T11:43:00+00:00','preliminary_single':dict(ROW),'official_single':None,'official_top5':None}
    def test_new_single_replaces_current_payload_without_changing_page_identity(self):
        session=self.session()
        loader=lambda *args:([{'GAME_DATE':'2026-11-01','PTS':18}], '2026-11-04T11:43:00+00:00')
        original=single_analysis.build(session,loader)
        session['preliminary_single']={**ROW,'Giocatore':'Other, Player','Quota':1.8}
        latest=single_analysis.build(session,loader)
        self.assertEqual(original['selection']['Giocatore'],'James, LeBron')
        self.assertEqual(latest['selection']['Giocatore'],'Other, Player')
        self.assertEqual(latest['date'],original['date'])
    def test_official_single_is_never_replaced_by_newer_preview_or_recalculated(self):
        session=self.session();session.update(official_top5={'published_at':'2026-11-04T17:00:00Z'},official_single=dict(ROW),preliminary_single={**ROW,'Quota':2.5})
        result=single_analysis.build(session,lambda *args:([],None))
        self.assertEqual(result['state'],'official')
        self.assertEqual(result['selection'],ROW)
        session['official_single']=None
        self.assertIsNone(single_analysis.build(session)['selection'])
    def test_history_excludes_duplicates_future_rows_and_invalid_values(self):
        rows=[{'GAME_DATE':'2026-11-01','GAME_ID':'g','PTS':18},{'GAME_DATE':'2026-11-01','GAME_ID':'g','PTS':18},
              {'GAME_DATE':'2026-11-05','PTS':50},{'GAME_DATE':'2026-10-31','PTS':float('nan')},
              {'GAME_DATE':'2026-10-30','PTS':None}]
        result=single_analysis.build(self.session(),lambda *args:(rows,'2026-11-04T11:43:00+00:00'))
        self.assertEqual(result['games'],[rows[0]])
    def test_official_history_query_uses_frozen_snapshot_ids_cutoff_and_exact_line(self):
        session=self.session();session['official_top5']={'snapshot_job_ids':{'2026-11-05':'frozen-job'},'published_at':'2026-11-04T17:00:00Z'}
        conn=MagicMock();conn.execute.return_value.fetchone.return_value=([{'GAME_DATE':'2026-11-01','PTS':18}],datetime(2026,11,4,16,tzinfo=timezone.utc))
        with patch.object(single_analysis.storage,'connection') as cx:
            cx.return_value.__enter__.return_value=conn
            result=single_analysis.saved_history(session,ROW)
        query,args=conn.execute.call_args.args
        self.assertIn("payload->'player_logs'",query)
        self.assertEqual(args[-1],['frozen-job'])
        self.assertFalse(args[-2])
        self.assertEqual(args[3],'2026-11-04T17:00:00Z')
        self.assertEqual(args[4].obj,[ROW])
        self.assertEqual(result[0][0]['PTS'],18)
