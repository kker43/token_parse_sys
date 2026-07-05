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
                ma30=180.0,
                ma60=134.07,
                ma120=93.79,
                ma20_slope_20d=0.558,
                amount_ratio_20d=1.57,
                max_drawdown_60d=-0.123,
                max_drawdown_120d=-0.21,
                convergence_5_10_20_pct=0.129,
                close_to_high_60d_pct=0.0,
                ma20_deviation_pct=0.306,
                ma30_deviation_pct=0.25,
                ma30_hold_ratio_30d=0.90,
                ma30_hold_ratio_60d=0.85,
                ma30_hold_ratio_90d=0.80,
                ma30_hold_ratio_120d=0.78,
                ma60_hold_ratio_120d=0.82,
                return_20d=0.28,
                red_k_ratio_20d=0.65,
                green_k_ratio_20d=0.35,
                long_shadow_ratio_20d=0.30,
                avg_amount_20d=300_000_000.0,
                close_new_high_60d_flag=True,
                daily_quality_pass=True,
                trend_stability_pass=True,
                market_cap_liquidity_pass=True,
                turnover_quality_pass=True,
                context_strength_pass=True,
                steady_uptrend=True,
                pre_breakout_watch=False,
                breakout_watch=True,
                setup_score=72.0,
                weekly_asof_trade_date="20260612",
                weekly_close=220.0,
                weekly_ma5=210.0,
                weekly_ma10=180.0,
                weekly_ma20=140.0,
                weekly_ma20_slope_4w=0.12,
                weekly_max_drawdown_26w=-0.18,
                weekly_trend_pass=True,
                total_mv=2_000_000.0,
                turnover_rate=8.0,
                max_turnover_rate_20d=16.0,
                avg_turnover_rate_20d=8.0,
                strong_industry_hit=True,
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
                ma30=180.0,
                ma60=134.07,
                ma120=93.79,
                ma20_slope_20d=0.558,
                amount_ratio_20d=1.57,
                max_drawdown_60d=-0.123,
                max_drawdown_120d=-0.21,
                convergence_5_10_20_pct=0.129,
                close_to_high_60d_pct=0.0,
                ma20_deviation_pct=0.306,
                ma30_deviation_pct=0.25,
                ma30_hold_ratio_30d=0.90,
                ma30_hold_ratio_60d=0.85,
                ma30_hold_ratio_90d=0.80,
                ma30_hold_ratio_120d=0.78,
                ma60_hold_ratio_120d=0.82,
                return_20d=0.28,
                red_k_ratio_20d=0.65,
                green_k_ratio_20d=0.35,
                long_shadow_ratio_20d=0.30,
                avg_amount_20d=300_000_000.0,
                close_new_high_60d_flag=True,
                daily_quality_pass=True,
                trend_stability_pass=True,
                market_cap_liquidity_pass=True,
                turnover_quality_pass=True,
                context_strength_pass=True,
                steady_uptrend=True,
                pre_breakout_watch=False,
                breakout_watch=True,
                setup_score=72.0,
                weekly_asof_trade_date="20260612",
                weekly_close=220.0,
                weekly_ma5=210.0,
                weekly_ma10=180.0,
                weekly_ma20=140.0,
                weekly_ma20_slope_4w=0.12,
                weekly_max_drawdown_26w=-0.18,
                weekly_trend_pass=True,
                total_mv=2_000_000.0,
                turnover_rate=8.0,
                max_turnover_rate_20d=16.0,
                avg_turnover_rate_20d=8.0,
                strong_industry_hit=True,
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
