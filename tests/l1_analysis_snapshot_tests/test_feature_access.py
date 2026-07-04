"""Tests for AnalysisSnapshot feature access helpers."""

from __future__ import annotations

import unittest

from stock_lobster.core.ids import RunId
from stock_lobster.l1_analysis_snapshot import (
    AnalysisSnapshot,
    FeatureNotFoundError,
    get_indicator_value,
    has_requirement,
)


class FeatureAccessTest(unittest.TestCase):
    def test_reads_row_expanded_indicator_values(self) -> None:
        snapshot = AnalysisSnapshot(
            stock_code="603256.SH",
            snapshot_date="20260703",
            analysis_version="analysis_v1",
            run_id=RunId("run_fixture"),
            features={
                "pub_stock_daily_indicator.1.indicator_name": "ma20",
                "pub_stock_daily_indicator.1.indicator_value": "240.8990",
                "pub_stock_daily_indicator.2.indicator_name": "amount_ratio_20d",
                "pub_stock_daily_indicator.2.indicator_value": 1.7,
            },
        )

        self.assertEqual(240.899, get_indicator_value(snapshot, "ma20"))
        self.assertTrue(has_requirement(snapshot, "indicator:amount_ratio_20d"))
        self.assertFalse(has_requirement(snapshot, "indicator:ma60"))

    def test_raises_for_missing_indicator(self) -> None:
        snapshot = AnalysisSnapshot(
            stock_code="603256.SH",
            snapshot_date="20260703",
            analysis_version="analysis_v1",
            run_id=RunId("run_fixture"),
            features={},
        )

        with self.assertRaises(FeatureNotFoundError):
            get_indicator_value(snapshot, "ma20")


if __name__ == "__main__":
    unittest.main()
