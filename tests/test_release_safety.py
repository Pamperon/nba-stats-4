"""Release gate: experimental ranking and unvalidated calibration stay offline."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ReleaseSafetyTests(unittest.TestCase):
    def test_live_calibration_requires_explicit_release_even_when_evidence_qualifies(self):
        tree = ast.parse((ROOT / 'main.py').read_text(encoding='utf-8'))
        flag = next(node for node in tree.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == 'LIVE_CALIBRATION_ENABLED'
                            for target in node.targets))
        self.assertIs(flag.value.value, False)
        scan = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'do_scan')
        gate = next(node for node in ast.walk(scan) if isinstance(node, ast.If)
                    and 'LIVE_CALIBRATION_ENABLED' in ast.unparse(node.test))
        self.assertIn('progressive_calibration.apply', ast.unparse(gate))

    def test_live_server_does_not_import_experimental_selector(self):
        tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertNotIn("scripts.recommendation_backtest", imports)
        self.assertNotIn("scripts.multiday_backtest", imports)

    def test_odds_cache_refreshes_within_each_scheduled_window(self):
        tree = ast.parse((ROOT / "engine.py").read_text(encoding="utf-8"))
        assignments = {
            target.id: node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        cache_ttl = assignments["ODDS_CACHE_TTL_SECONDS"]
        self.assertIsInstance(cache_ttl, ast.BinOp)
        self.assertEqual(cache_ttl.left.value * cache_ttl.right.value, 10800)
        self.assertIn("quota_rilevata_at", (ROOT / "engine.py").read_text(encoding="utf-8"))

    def test_http_request_counter_is_not_quote_line_counter(self):
        import engine
        engine.reset_odds_api_request_count()
        self.assertEqual(engine.odds_api_request_count(), 0)
        self.assertIn("odds_api_http_requests_scan", (ROOT / "main.py").read_text(encoding="utf-8"))

    def test_live_engine_does_not_use_offline_calibration(self):
        tree = ast.parse((ROOT / "engine.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                function = node.func
                if isinstance(function, ast.Name):
                    self.assertNotEqual(function.id, "calibrated_probability")
                if isinstance(function, ast.Attribute):
                    self.assertNotEqual(function.attr, "calibrated_probability")

if __name__ == "__main__":
    unittest.main()
