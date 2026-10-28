"""Saved-data views must never infer historic picks or require provider I/O."""
import unittest
from copy import deepcopy
import public_views

ROW = {'Giocatore':'A Player', 'ESPN ID':'123', 'Squadra':'A', 'Partita':'A - B',
       'Mercato':'PTS', 'Scelta':'Over', 'Linea':19.5, 'Quota':1.74, 'Prob. stimata %':80}


class PublicViewsTests(unittest.TestCase):
    def test_quote_change_matches_exact_selection_and_preserves_original_prices(self):
        before=[dict(ROW),{**ROW,'Linea':14.5,'Quota':1.2}]
        current=[{**ROW,'Quota':1.71},{**ROW,'Linea':24.5,'Quota':2.3}]
        original=deepcopy(before)
        result=public_views.compare_quotes(current,before)
        self.assertEqual(result['summary']['down'],1)
        self.assertEqual(result['summary']['added'],1)
        self.assertEqual(result['summary']['removed'],1)
        self.assertEqual(result['summary']['comparable'],1)
        self.assertEqual(result['summary']['line_groups_changed'],1)
        changed=next(row for row in result['changes'] if row['kind']=='down')
        self.assertEqual((changed['before'],changed['after']),(1.74,1.71))
        self.assertEqual(before,original)

    def test_different_games_or_players_are_not_same_selection(self):
        result=public_views.compare_quotes([{**ROW,'Partita':'A - C'}],[ROW])
        self.assertEqual(result['summary']['comparable'],0)
        self.assertEqual(result['summary']['down'],0)
        self.assertEqual(result['summary']['added'],1)

    def test_search_input_includes_all_movements_beyond_one_thousand_players(self):
        rows=[{**ROW,'ESPN ID':str(i),'Giocatore':f'Player {i:04d}'} for i in range(1251)]
        result=public_views.compare_quotes(rows,[])
        self.assertEqual(len(result['changes']),1251)
        self.assertEqual(result['changes'][-1]['player'],'Player 1250')
        self.assertFalse(result['truncated'])

    def test_unchanged_quotes_not_reported_as_changes_and_ambiguous_rows_excluded(self):
        result=public_views.compare_quotes([ROW],[ROW])
        self.assertEqual(result['summary']['unchanged'],1)
        self.assertEqual(result['changes'],[])
        index,ambiguous=public_views.selection_index([ROW,{**ROW,'Quota':1.71}])
        self.assertFalse(index)
        self.assertEqual(ambiguous,1)
        self.assertEqual(public_views.selection_index([{**ROW,'Quota':float('nan')}]),({},0))

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
