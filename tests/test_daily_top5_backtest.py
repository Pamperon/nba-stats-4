import unittest
from unittest.mock import patch
from scripts.daily_top5_backtest import evaluate_day, score


def row(i, probability=80):
    return {"Giocatore":f"Player {i}","ESPN ID":str(i),"Partita":"A - B",
            "Squadra":"A","Mercato":"PTS","Scelta":"Over","Linea":9.5,
            "Quota":1.8,"Prob. stimata %":probability,"Stato analisi":"Valutabile (stima empirica)",
            "Partite":30,"Stagione %":80,"Minuti medi":30,"Minuti ultime 5":29}


class DailyTopFiveTests(unittest.TestCase):
    def test_score_keeps_unresolved_and_uses_exact_saved_odds(self):
        saved=[row(1,80),row(2,70),row(3,90)]
        verified=[{**saved[0],"played":True,"actual":11},
                  {**saved[1],"played":True,"actual":8}]
        result=score(saved,verified)
        self.assertEqual((result["selected"],result["resolved"],result["unresolved"]),(3,2,1))
        self.assertEqual((result["wins"],result["losses"]),(1,1))
        self.assertEqual(result["hit_rate"],0.5)
        self.assertEqual(result["flat_stake_roi"],-0.1)
        self.assertEqual(result["brier"],0.265)

    def test_top_five_uses_pregame_ranking_not_outcomes(self):
        saved=[row(i,95-i) for i in range(1,9)]
        verified=[{**r,"played":True,"actual":11 if int(r["ESPN ID"])>5 else 8} for r in saved]
        with patch("recommendations.select_daily", wraps=__import__("recommendations").select_daily) as selected:
            result=evaluate_day({"date":"2026-10-25","results":saved},verified)
        selected.assert_called_once()
        self.assertEqual(result["top5"]["selected"],5)
        self.assertEqual(result["top5"]["wins"],0)
        self.assertEqual(result["remaining"]["selected"],3)
        self.assertEqual(result["remaining"]["wins"],3)
        self.assertEqual(result["selection_origin"],"reconstructed_from_pregame_snapshot")


if __name__=="__main__":
    unittest.main()
