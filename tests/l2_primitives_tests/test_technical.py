import unittest

from stock_lobster.core.ids import RunId
from stock_lobster.l1_analysis_snapshot import AnalysisSnapshot
from stock_lobster.l2_primitives.default_registry import build_default_primitive_registry
from stock_lobster.l2_primitives.technical import avg_amount_20d_ge_2e, volume_ratio_5d_20d_high
from stock_lobster.l3_labels.default_registry import build_default_label_registry


def _snapshot(avg_amount_20d: float) -> AnalysisSnapshot:
    return AnalysisSnapshot(
        stock_code="000001.SZ",
        snapshot_date="20260710",
        analysis_version="analysis_v1",
        run_id=RunId("run_amount_unit_fixture"),
        features={
            "pub_stock_daily_indicator.1.indicator_name": "avg_amount_20d",
            "pub_stock_daily_indicator.1.indicator_value": avg_amount_20d,
        },
    )


class TechnicalPrimitiveTest(unittest.TestCase):
    def test_avg_amount_20d_threshold_uses_thousand_cny(self) -> None:
        self.assertTrue(avg_amount_20d_ge_2e(_snapshot(200_000)))
        self.assertFalse(avg_amount_20d_ge_2e(_snapshot(199_999.99)))

    def test_volume_ratio_5d_20d_threshold_is_1_2_across_l2_l3(self) -> None:
        self.assertFalse(volume_ratio_5d_20d_high(_indicator_snapshot("volume_ratio_5d_20d", 1.19)))
        self.assertTrue(volume_ratio_5d_20d_high(_indicator_snapshot("volume_ratio_5d_20d", 1.20)))

        primitive_id = "volume_liquidity.volume_ratio_5d_20d_high"
        primitive_registry = build_default_primitive_registry()
        label_registry = build_default_label_registry()

        self.assertEqual(volume_ratio_5d_20d_high, primitive_registry.get(primitive_id).function)
        self.assertIn(
            primitive_id,
            label_registry.get("technical_pattern.volume_breakout").primitive_ids,
        )


def _indicator_snapshot(indicator_name: str, value: float) -> AnalysisSnapshot:
    return AnalysisSnapshot(
        stock_code="000001.SZ",
        snapshot_date="20260710",
        analysis_version="analysis_v1",
        run_id=RunId("run_volume_ratio_fixture"),
        features={
            "pub_stock_daily_indicator.1.indicator_name": indicator_name,
            "pub_stock_daily_indicator.1.indicator_value": value,
        },
    )


if __name__ == "__main__":
    unittest.main()
