import json
import subprocess
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from unittest.mock import MagicMock

import availability
import progressive_calibration
import calibration
import recommendations


def row(**overrides):
    result = {"Giocatore": "Player", "ESPN ID": "123", "Partita": "A - B",
              "Mercato": "PTS", "Scelta": "Over", "Linea": 9.5,
              "Quota": 1.8, "Prob. stimata %": 80, "Value stimato %": 44,
              "Stato analisi": "Valutabile (stima empirica)", "Partite": 30,
              "Stagione %": 80, "Minuti medi": 30, "Minuti ultime 5": 29}
    result.update(overrides)
    return result


class RiskTests(unittest.TestCase):
    def test_minutes_filter_excludes_over_without_changing_probability(self):
        risky = row(**{"Minuti ultime 5": 21})  # Passed old 65% threshold.
        self.assertIn("minutaggio in calo", recommendations.rejection_reasons(risky))
        self.assertFalse(recommendations.select([risky])["groups"]["Singola"]["complete"])
        self.assertEqual(risky["Prob. stimata %"], 80)

    def test_known_injury_and_unknown_report_never_become_suggestions(self):
        for status in ("out", "doubtful", "questionable", "day-to-day", "unknown"):
            self.assertTrue(recommendations.rejection_reasons(row(**{"Disponibilità ESPN": status})))
        self.assertFalse(recommendations.rejection_reasons(row(**{"Disponibilità ESPN": "not-listed"})))

    def test_python_and_browser_select_the_same_players(self):
        rows = [row(), row(Giocatore="Risky", **{"Prob. stimata %": 90, "Minuti ultime 5": 21}),
                row(Giocatore="Absent", **{"Prob. stimata %": 95, "Disponibilità ESPN": "out"}),
                row(Giocatore="Double", Quota=1.5), row(Giocatore="Triple", Quota=1.25)]
        script = """
const fs=require('fs'),vm=require('vm');
const s=fs.readFileSync('web/app.js','utf8'),ctx={};vm.createContext(ctx);
vm.runInContext('const number=x=>Number(x)||0;'+s.slice(s.indexOf('function pickRejectionReasons'),s.indexOf('function pickEmptyReason')),ctx);
const rows=JSON.parse(fs.readFileSync(0,'utf8')),out={};
for(const [name,n,lo,hi]of [['Singola',1,1.7,2],['Doppia',2,1.4,1.69],['Tripla',3,1.2,1.39]])out[name]=ctx.pickCandidates(rows,lo,hi,n).map(r=>r.Giocatore);
process.stdout.write(JSON.stringify(out));
"""
        result = subprocess.run(["node", "-e", script], input=json.dumps(rows), text=True, capture_output=True, check=True)
        expected = {name: [r["Giocatore"] for r in group["legs"]]
                    for name, group in recommendations.select(rows)["groups"].items()}
        self.assertEqual(json.loads(result.stdout), expected)

    def test_injury_identity_uses_exact_espn_id_not_ambiguous_name(self):
        now = datetime(2026, 10, 26, 15, tzinfo=timezone.utc)
        payload = {"timestamp": now.isoformat(), "status": "success", "injuries": [
            {"injuries": [{"athlete": {"displayName": "Other", "links": [
                {"href": "https://www.espn.com/nba/player/_/id/123/other"}]}, "status": "Out"}]}]}
        result, status = availability.annotate([row(), row(**{"ESPN ID": "456"})], payload, now)
        self.assertTrue(status["verified"])
        self.assertEqual([r["Disponibilità ESPN"] for r in result], ["out", "not-listed"])
        self.assertEqual(result[0]["Prob. stimata %"], 80)
        payload["timestamp"] = "2026-10-26T13:00:00+00:00"
        stale, status = availability.annotate([row()], payload, now)
        self.assertFalse(status["verified"])
        self.assertEqual(stale[0]["Disponibilità ESPN"], "unknown")

    def test_failed_report_does_not_clear_players(self):
        with patch.object(availability.requests, 'get', side_effect=availability.requests.Timeout):
            rows, status = availability.check([row()])
        self.assertFalse(status['verified'])
        self.assertEqual(rows[0]['Disponibilità ESPN'], 'unknown')

    def test_saved_leg_is_never_replaced_and_dnp_stays_unresolved(self):
        original = row()
        ticket = recommendations.select([original])
        unrelated = row(Giocatore='Other', **{'ESPN ID': '456', 'actual': 50, 'played': True})
        result = recommendations.evaluate(ticket, [unrelated])
        self.assertEqual(result['groups']['Singola']['status'], 'unresolved')
        self.assertIsNone(result['groups']['Singola']['unit_profit'])
        self.assertEqual(result['groups']['Singola']['legs'][0]['player'], 'Player')
        result = recommendations.evaluate(ticket, [{**original, 'actual': 10, 'played': True}])
        self.assertEqual(result['groups']['Singola']['status'], 'won')
        self.assertAlmostEqual(result['groups']['Singola']['unit_profit'], .8)

    def test_legacy_review_does_not_apply_new_minutes_filter_retroactively(self):
        risky = row(**{'Minuti ultime 5': 21})
        self.assertTrue(recommendations.select([risky], screen_risks=False)['groups']['Singola']['complete'])
        self.assertFalse(recommendations.select([risky])['groups']['Singola']['complete'])

    def test_settlement_keeps_saved_ticket_and_is_idempotent_per_snapshot(self):
        import storage
        import settle_espn
        original = row()
        saved = recommendations.select([original])
        payload = {'date': '2026-10-26', 'recommendations': saved, 'results': [original]}
        db = MagicMock()
        db.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [
            ('job', payload, datetime(2026, 10, 25, 16, tzinfo=timezone.utc))]
        with patch.object(storage, 'connection', db), patch.object(settle_espn, 'settle_archive',
                return_value=([{**original, 'actual': 10, 'played': True}], 1)) as verify:
            self.assertEqual(recommendations.settle_snapshots('2026-10-26'), 1)
        query = db.return_value.__enter__.return_value.execute
        self.assertIn('NOT EXISTS', query.call_args_list[0].args[0])
        sql, params = query.call_args_list[1].args
        self.assertIn('ON CONFLICT(snapshot_job_id) DO NOTHING', sql)
        self.assertEqual(params[0], 'job')
        self.assertEqual(params[2].obj['groups']['Singola']['legs'][0]['player'], 'Player')
        self.assertEqual(params[2].obj['groups']['Singola']['status'], 'won')
        self.assertEqual(verify.call_args.args[0]['recommendations'], saved)

    def test_unvalidated_probability_boundaries_are_not_adjusted(self):
        bins = [{"market": "PTS", "probability_bin": 90, "n": 400,
                 "observed": .6, "predicted": .95}]
        with patch.object(calibration, 'approved_adjustments', return_value=bins):
            rows, status = progressive_calibration.apply([row(**{"Prob. stimata %": 95})], [])
        self.assertEqual(rows[0]['Prob. stimata %'], 95)
        self.assertEqual(status['adjusted'], 0)


if __name__ == '__main__':
    unittest.main()
