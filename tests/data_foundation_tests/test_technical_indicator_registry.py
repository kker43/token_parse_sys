"""Tests for the first technical-indicator registry shape."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


class TechnicalIndicatorRegistryTest(unittest.TestCase):
    def test_basic_registry_contains_first_stage_indicator_contracts(self) -> None:
        path = Path(__file__).resolve().parents[2] / "configs" / "technical_indicators" / "basic_technical_indicators.example.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        indicators = {item["name"]: item for item in payload["indicators"]}

        self.assertEqual(1, payload["schema_version"])
        self.assertIn("ma20", indicators)
        self.assertIn("close_new_high_60d_flag", indicators)
        self.assertEqual("pub_stock_daily_indicator", indicators["ma20"]["source_product"])
        self.assertEqual("numeric", indicators["convergence_5_10_20_pct"]["value_type"])


if __name__ == "__main__":
    unittest.main()
