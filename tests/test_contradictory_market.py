import unittest
from datetime import datetime, timedelta, timezone
from engine import parse_odds


class ContradictoryMarketTests(unittest.TestCase):
    def parse(self, *, age=60, active=True, market=False, suspended=False, changed=True):
        player = {'active': active, 'playerName': 'Player', 'price': 1.8}
        if changed:
            player['changedAt'] = (datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat()
        data = {'bookmakerOdds': {'bet365.it': {'bookmakerIsActive': True,
            'suspended': suspended, 'markets': {'m': {'marketActive': market,
            'outcomes': {'o': {'players': {'p': player}}}}}}}}
        catalog = {'m': {'marketType': 'players-points',
            'outcomes': [{'outcomeId': 'o', 'outcomeName': '10+'}]}}
        return parse_odds(data, catalog, 'Punti (PTS)')[0]

    def test_recent_active_quote_survives_contradictory_market(self):
        self.assertEqual(self.parse()[0]['Linea'], 9.5)

    def test_inactive_stale_missing_or_future_quotes_are_excluded(self):
        for kwargs in ({'active': False}, {'age': 10801}, {'changed': False}, {'age': -60}):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(self.parse(**kwargs), [])

    def test_suspension_overrides_recent_quote(self):
        self.assertEqual(self.parse(suspended=True), [])

    def test_consistent_active_market_unchanged(self):
        self.assertEqual(len(self.parse(market=True, changed=False)), 1)


if __name__ == '__main__':
    unittest.main()
