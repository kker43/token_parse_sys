"""Tests for steady uptrend breakout case workflow helpers."""

from __future__ import annotations

import unittest

from stock_lobster.research import (
    TrendBreakoutMetrics,
    run_steady_uptrend_breakout_case,
)


class SteadyUptrendBreakoutCaseTest(unittest.TestCase):
    def test_runs_full_case_to_l4_draft(self) -> None:
        result = run_steady_uptrend_breakout_case(
            TrendBreakoutMetrics(
                asset_id="603256.SH",
                trade_date="20260617",
                close=258.9,
                ma5=250.0,
                ma10=230.0,
                ma20=198.22,
                ma60=134.07,
                ma120=93.79,
                ma20_slope_20d=0.558,
                amount_ratio_20d=1.57,
                max_drawdown_60d=-0.123,
                convergence_5_10_20_pct=0.129,
                close_new_high_60d_flag=True,
                steady_uptrend=True,
                breakout_watch=True,
            )
        )

        self.assertFalse(result.experience_build_plan.has_gaps)
        self.assertEqual("draft", result.strategy.status)
        self.assertIn(
            "composite_setup.steady_uptrend_breakout_watch",
            result.strategy.label_fields,
        )


if __name__ == "__main__":
    unittest.main()
