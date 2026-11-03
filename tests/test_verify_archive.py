import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import verify_archive


class ArchiveVerificationTests(unittest.TestCase):
    def test_read_only_report(self):
        rows = [{"Mercato": "PTS", "Scelta": "Over", "Linea": 10.5,
                 "Prob. stimata %": 70, "actual": 15, "played": True}]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "archive.json"
            path.write_text(json.dumps({"date": "2026-10-24", "results": rows}))
            with patch.object(verify_archive.settle_espn, "settle_archive",
                              return_value=(rows, 1)):
                report = verify_archive.run(path, "2026-10-24")
            self.assertEqual(report["verified_predictions"], 1)
            self.assertEqual(report["coverage"], 1.0)
            self.assertTrue(report["ready_for_settlement"])
            self.assertEqual(report["database_writes"], 0)

    def test_rejects_mismatched_date(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "archive.json"
            path.write_text(json.dumps({"date": "2026-10-23", "results": []}))
            with self.assertRaisesRegex(ValueError, "date"):
                verify_archive.run(path, "2026-10-24")


if __name__ == "__main__":
    unittest.main()
