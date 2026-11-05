import unittest
from scripts.full_selection_audit import select,summarize

def row(name,p=80,q=1.5,win=1):
 return {'Giocatore':name,'ESPN ID':name,'Partita':'A - B','Mercato':'PTS','Scelta':'Over','Linea':9.5,'Quota':q,'Prob. stimata %':p,'Partite':25,'Stagione %':80,'Minuti medi':30,'Minuti ultime 5':30,'Stato analisi':'Valutabile (stima empirica)','Disponibilità ESPN':'not-listed','_day':'2026-10-23','_win':win}

class AuditTests(unittest.TestCase):
 def test_selection_never_reads_outcomes(self):
  rows=[row('A',85,1.3,0),row('B',80,1.6,1)]
  before=[r['Giocatore'] for r in select(rows)]
  for r in rows:r['_win']=1-r['_win']
  self.assertEqual(before,[r['Giocatore'] for r in select(rows)])
 def test_one_line_per_athlete_game(self):
  a=row('A',85,1.3);b={**a,'Mercato':'REB','Linea':4.5,'Prob. stimata %':80}
  self.assertEqual(len(select([a,b])),1)
 def test_unresolved_is_not_a_loss(self):
  result=summarize([row('A',win=None),row('B',win=0),row('C',win=1)])
  self.assertEqual(result['n'],2);self.assertEqual(result['hit_pct'],50)
