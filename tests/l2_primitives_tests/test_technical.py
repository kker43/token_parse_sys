import unittest

from stock_lobster.core.ids import RunId
from stock_lobster.l1_analysis_snapshot import AnalysisSnapshot
from stock_lobster.l2_primitives.technical import avg_amount_20d_ge_2e


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


if __name__ == "__main__":
    unittest.main()
