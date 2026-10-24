"""Release gate: experimental ranking and unvalidated calibration stay offline."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ReleaseSafetyTests(unittest.TestCase):
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
