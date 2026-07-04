"""Tests for steady uptrend breakout case workflow helpers."""

from __future__ import annotations

import unittest

from stock_lobster.research import (
    TrendBreakoutMetrics,
    run_steady_uptrend_breakout_case,
)
from stock_lobster.l6_backtest_engine import BacktestResult


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

    def test_promotes_case_when_backtest_gate_passes(self) -> None:
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
            ),
            backtest_result=BacktestResult(
                strategy_id="strategy.steady_uptrend_breakout_watch",
                strategy_version="candidate_v1",
                backtest_period=("20250101", "20260703"),
                benchmark="000300.SH",
                holding_horizon=20,
                return_metrics={"annual_return": 0.12},
                drawdown_metrics={"max_drawdown": -0.18},
                win_rate=0.6,
                sample_size=30,
            ),
        )

        self.assertEqual("test_tracking", result.strategy.status)
        self.assertTrue(result.backtest_decision.passed)


if __name__ == "__main__":
    unittest.main()
