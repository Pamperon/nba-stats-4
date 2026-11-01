import unittest
from datetime import datetime, timezone
from public_views import progressive_preview


def snapshot(at, lines):
    return {'saved_at': at, 'is_daily': True, 'lines': lines}


def leg(player, game='A - B', probability=80, odds=1.8):
    return {'Giocatore': player, 'Partita': game, 'Prob. stimata %': probability,
            'Quota': odds}


class ProgressivePreviewTests(unittest.TestCase):
    def test_uses_latest_scan_before_deadline_and_preserves_quote(self):
        versions = [
            snapshot('2026-11-01T16:00:00+00:00', [leg('One', odds=1.8)]),
            snapshot('2026-11-01T17:30:00+00:00', [leg('Two', odds=1.9)]),
            snapshot('2026-11-01T17:50:00+00:00', [leg('Three', odds=2.0)]),
        ]
        result = progressive_preview(versions, {'A - B': '2026-11-01T18:00:00+00:00'},
                                     as_of=datetime(2026, 11, 1, 19, tzinfo=timezone.utc))
        self.assertEqual([r['row']['Giocatore'] for r in result], ['Two'])
        self.assertEqual(result[0]['row']['Quota'], 1.9)

    def test_does_not_confirm_before_deadline_or_without_start(self):
        versions = [snapshot('2026-11-01T16:00:00+00:00', [leg('One')])]
        self.assertEqual(progressive_preview(versions, {'A - B': '2026-11-01T18:00:00+00:00'},
            as_of=datetime(2026, 11, 1, 17, tzinfo=timezone.utc)), [])
        self.assertEqual(progressive_preview(versions, {},
            as_of=datetime(2026, 11, 1, 19, tzinfo=timezone.utc)), [])

    def test_max_five(self):
        versions = [snapshot('2026-11-01T16:00:00+00:00', [leg(str(i)) for i in range(8)])]
        result = progressive_preview(versions, {'A - B': '2026-11-01T18:00:00+00:00'},
                                     as_of=datetime(2026, 11, 1, 19, tzinfo=timezone.utc))
        self.assertEqual(len(result), 5)


if __name__ == '__main__':
    unittest.main()
