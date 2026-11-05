import copy,unittest
from datetime import date,timedelta
import probability_model_v3 as m
import recommendations

def games(minutes=30,points=20,season='2026-27',n=20):
 return [{'GAME_ID':str(i),'GAME_DATE':str(date(2026,11,4)-timedelta(days=i)),
 'MIN':minutes,'PTS':points,'REB':8,'AST':5,'SEASON_TYPE':2,'ANNO_STAGIONE':season} for i in range(n)]
def training(p=.8,n=100):
 return {'model_version':m.VERSION,'trained_through':'2026-11-04','days':8,'markets':{s:[{'bin':i,'effective_n':n,'days':5,'probability':p} for i in range(10)] for s in m.MARKETS}}
def row(**kw):
 r={'Giocatore':'A','ESPN ID':'1','Partita':'A - B','Mercato':'PTS','Scelta':'Over','Linea':9.5,'Quota':1.8,'Prob. stimata %':80,'Partite':30,'Stagione %':80,'Minuti medi':30,'Minuti ultime 5':30,'Disponibilità ESPN':'not-listed','Stato analisi':'Valutabile (stima empirica)','Modello probabilità':m.VERSION,'Ruolo stabile':True,'Calibrazione supportata':True,'Partite ruolo attuale':8,'Minuti attesi':30,'Campione effettivo':20,'Limite prudente %':65,'Variabilità minuti':.1};r.update(kw);return r

class ModelV3Tests(unittest.TestCase):
 def test_future_records_and_duplicate_games_do_not_change_estimate(self):
  original=games();before=copy.deepcopy(original);extra={**original[0],'GAME_ID':'future','GAME_DATE':'2026-11-06','PTS':100}
  a=m.context(original,'2026-27','2026-11-05T12:00:00+00:00');b=m.context(original+[original[0],extra],'2026-27','2026-11-05T12:00:00+00:00')
  self.assertEqual(m.estimate(a,'PTS',14.5),m.estimate(b,'PTS',14.5));self.assertEqual(original,before)
 def test_minutes_reduction_lowers_probability(self):
  high=games();low=games()
  for g in low[:5]:g['MIN']=20;g['PTS']=13
  a=m.estimate(m.context(high,'2026-27','2026-11-05T12:00:00+00:00'),'PTS',17.5)
  b=m.estimate(m.context(low,'2026-27','2026-11-05T12:00:00+00:00'),'PTS',17.5)
  self.assertLess(b['expected_minutes'],a['expected_minutes']);self.assertLess(b['raw_probability'],a['raw_probability'])
 def test_previous_season_cannot_override_current_role(self):
  current=games(n=6,minutes=20,points=10);old=games(n=50,minutes=38,points=40,season='2025-26')
  for i,g in enumerate(old):g['GAME_ID']='old'+str(i);g['GAME_DATE']=str(date(2026,4,1)-timedelta(days=i))
  ctx=m.context(current+old,'2026-27','2026-11-05T12:00:00+00:00');self.assertEqual(ctx['expected_minutes'],20)
  self.assertLessEqual(sum(w for g,w in ctx['weighted'] if g['_season']!='2026-27'),.5*sum(w for g,w in ctx['weighted'] if g['_season']=='2026-27')+.00001)
 def test_calibration_never_uses_same_or_future_day(self):
  f=m.estimate(m.context(games(),'2026-27','2026-11-05T12:00:00+00:00'),'PTS',14.5)
  self.assertFalse(m.calibrated(f,'PTS','2026-11-04',training())['calibration_supported'])
  self.assertTrue(m.calibrated(f,'PTS','2026-11-05',training())['calibration_supported'])
  self.assertFalse(m.calibrated(f,'PTS','2026-11-05',training(n=1))['calibration_supported'])
 def test_no_forced_single_or_ten_and_stability_gate(self):
  unsupported=row(**{'Calibrazione supportata':False});unstable=row(**{'Ruolo stabile':False})
  self.assertEqual(recommendations.select_daily([unsupported,unstable])['lines'],[])
  self.assertIsNone(recommendations.select_single([unsupported,unstable]))
  self.assertEqual(len(recommendations.select_daily([row()])['lines']),1)
 def test_single_prefers_probability_over_value(self):
  a=row(Quota=1.7,**{'Prob. stimata %':80});b=row(Giocatore='B',**{'ESPN ID':'2','Quota':1.9,'Prob. stimata %':76})
  self.assertEqual(recommendations.select_single([a,b])['Giocatore'],'A')
 def test_stability_breaks_equal_probability_ties(self):
  a=row(**{'Variabilità minuti':.2});b=row(Giocatore='B',**{'ESPN ID':'2','Variabilità minuti':.1})
  self.assertEqual(recommendations.select_daily([a,b])['lines'][0]['Giocatore'],'B')

class PublicationV3Tests(unittest.TestCase):
 def test_modern_publication_is_not_expanded_on_read(self):
  from unittest.mock import MagicMock,patch
  import nba_session_picks
  saved=[row()];connection=MagicMock()
  connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value=(__import__('datetime').datetime(2026,11,5,18,tzinfo=__import__('datetime').timezone.utc),{'2026-11-06':'job'},saved,None,nba_session_picks.POLICY)
  with patch.object(nba_session_picks.storage,'connection',connection),patch.object(recommendations,'expand_saved_picks',side_effect=AssertionError('Do not fill modern selections')):
   self.assertEqual(nba_session_picks.read('2026-11-05')['lines'],saved)
 def test_new_probability_fields_survive_and_inputs_remain_immutable(self):
  from unittest.mock import patch
  original=row();before=copy.deepcopy(original)
  with patch.object(m,'artifact',return_value=training()):
   rows,status=m.apply_rows([original],{'A':games()},'2026-27','2026-11-06','2026-11-05T12:00:00+00:00')
  self.assertEqual(original,before);self.assertEqual(rows[0]['Prob. storica %'],80)
  self.assertEqual(rows[0]['Modello probabilità'],m.VERSION)
  self.assertEqual(rows[0]['Minuti attesi'],30)
  self.assertTrue(rows[0]['Calibrazione supportata'])
