"""Saved-data views must never infer historic picks or require provider I/O."""
import unittest
from copy import deepcopy
import public_views

ROW = {'Giocatore':'A Player', 'ESPN ID':'123', 'Squadra':'A', 'Partita':'A - B',
       'Mercato':'PTS', 'Scelta':'Over', 'Linea':19.5, 'Quota':1.74, 'Prob. stimata %':80}


class PublicViewsTests(unittest.TestCase):
    def test_missing_final_result_is_unresolved_not_a_loss(self):
        saved={'groups':{'Singola':{'complete':True,'legs':[ROW]}}}
        result=public_views.ticket_groups(saved,None)['Singola']
        self.assertEqual(result['status'],'unresolved')
        self.assertIsNone(result['legs'][0]['actual'])
        self.assertEqual(result['legs'][0]['Quota'],1.74)

    def test_result_must_match_exact_saved_leg_including_line_and_price(self):
        saved={'groups':{'Singola':{'complete':True,'legs':[ROW]}}}
        settled={'Singola':{'legs':[{'player':'A Player','market':'PTS','choice':'Over',
                                    'line':19.5,'odds':1.74,'actual':22}]}}
        self.assertEqual(public_views.ticket_groups(saved,settled)['Singola']['status'],'won')
        settled['Singola']['legs'][0]['line']=14.5
        self.assertEqual(public_views.ticket_groups(saved,settled)['Singola']['status'],'unresolved')

    def test_incomplete_groups_do_not_publish_unshown_partial_ticket_or_reconstruct(self):
        saved={'groups':{'Doppia':{'complete':False,'legs':[ROW]}}}
        result=public_views.ticket_groups(saved,None)
        self.assertEqual(result['Doppia']['status'],'incomplete')
        self.assertFalse(result['Doppia']['legs'])
        self.assertEqual(result['Singola']['status'],'incomplete')

    def test_correlated_multiple_does_not_invent_bookmaker_combined_price(self):
        saved={'groups':{'Doppia':{'complete':True,'legs':[ROW,{**ROW,'Giocatore':'B Player','ESPN ID':'456'}]}}}
        self.assertIsNone(public_views.ticket_groups(saved,None)['Doppia']['combined_odds'])

    def version(self, rows, at='2026-10-28T07:00:00+00:00', name='Singola'):
        saved={'groups':{name:{'complete':True,'legs':rows}}}
        return {'saved_at':at,'groups':public_views.ticket_groups(saved,None)}

    def test_daily_dedup_ignores_changed_odds_and_probability_and_keeps_first_price(self):
        first=self.version([ROW])
        later=self.version([{**ROW,'Quota':1.71,'Prob. stimata %':82}],at='2026-10-28T11:00:00+00:00')
        before=deepcopy([later,first])
        result=public_views.daily_groups([later,first])
        self.assertEqual(len(result['Singola']),1)
        self.assertEqual(result['Singola'][0]['legs'][0]['Quota'],1.74)
        self.assertEqual(result['Singola'][0]['legs'][0]['Prob. stimata %'],80)
        self.assertEqual([later,first],before)

    def test_changed_line_game_or_player_is_a_distinct_daily_prediction(self):
        versions=[self.version([ROW]),self.version([{**ROW,'Linea':24.5}]),
                  self.version([{**ROW,'Partita':'A - C'}]),self.version([{**ROW,'ESPN ID':'456'}])]
        self.assertEqual(len(public_views.daily_groups(versions)['Singola']),4)

    def test_multiples_are_deduplicated_as_whole_tickets_without_inventing_combinations(self):
        second={**ROW,'Giocatore':'B Player','ESPN ID':'456','Partita':'C - D'}
        third={**second,'Giocatore':'C Player','ESPN ID':'789'}
        result=public_views.daily_groups([self.version([ROW,second],name='Doppia'),
            self.version([{**second,'Quota':1.5},ROW],name='Doppia'),
            self.version([ROW,third],name='Doppia')])
        self.assertEqual(len(result['Doppia']),2)
        self.assertFalse(result['Singola'])
        self.assertEqual([r['Giocatore'] for r in result['Doppia'][0]['legs']],['A Player','B Player'])

    def test_daily_merge_uses_verified_evidence_without_repeating_the_same_ticket(self):
        first=self.version([ROW])
        second=self.version([{**ROW,'Quota':1.71}],at='2026-10-28T11:00:00+00:00')
        second['groups']['Singola']['legs'][0].update(actual=22,win=True)
        result=public_views.daily_groups([first,second])['Singola']
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['status'],'won')
        self.assertEqual(result[0]['legs'][0]['Quota'],1.74)
        self.assertEqual(result[0]['legs'][0]['actual'],22)

    def test_conflicting_results_remain_unresolved(self):
        first=self.version([ROW]);second=self.version([ROW])
        first['groups']['Singola']['legs'][0].update(actual=22,win=True)
        second['groups']['Singola']['legs'][0].update(actual=9,win=False)
        result=public_views.daily_groups([first,second])['Singola'][0]
        self.assertEqual(result['status'],'unresolved')
        self.assertIsNone(result['legs'][0]['actual'])
