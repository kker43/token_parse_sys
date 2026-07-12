"""Contract tests for the layered recall and signal research scan."""

from __future__ import annotations

from dataclasses import replace
import unittest

from stock_lobster.research.steady_uptrend_v3 import MarketTemperature
from stock_lobster.research.trend_breakout_scan import TrendBreakoutMetrics
from workflows.jobs.layered_recall_signal_research_scan import build_stage_payload


class LayeredRecallSignalResearchScanTest(unittest.TestCase):
    def test_scan_outputs_every_stage_count(self) -> None:
        metrics = (
            _metric("000001.SZ"),
            replace(_metric("000002.SZ"), post_impulse_followthrough_return=-0.01),
            replace(
                _metric("000003.SZ"),
                long_shadow_ratio_20d=0.57,
                large_bearish_body_ratio_20d=0.30,
                ma30_hold_ratio_30d=0.83,
                ma30_deviation_pct=0.13,
            ),
            replace(
                _metric("000004.SZ"),
                close_new_high_60d_flag=False,
                close_to_high_60d_pct=-0.20,
                ma20_slope_20d=-0.01,
                ma30_hold_ratio_30d=0.20,
                ma30_hold_ratio_60d=0.20,
                ma30_hold_ratio_90d=0.20,
                return_20d=0.0,
                steady_uptrend=False,
            ),
        )

        payload = build_stage_payload(
            metrics,
            market_temperatures={"20260710": _temperature()},
            config={"signal_policy": {"normal_market_top_n": 5, "cooldown_trade_days": 0}},
            trade_date_order=("20260710",),
        )

        self.assertEqual(
            {
                "minimum_quality_pool": 4,
                "basic_liquidity_pool": 4,
                "recall_union": 3,
                "waiting_pool": 1,
                "hard_risk_rejected": 1,
                "signal_eligible": 1,
                "ranked_topn": 1,
                "final_signal": 1,
            },
            payload["stage_counts"],
        )

    def test_topn_post_rank_rejection_does_not_refill(self) -> None:
        metrics = tuple(
            replace(
                _metric(f"00000{index}.SZ", setup_score=100.0 - index),
                strong_concept_names=("blocked",) if index == 2 else (),
            )
            for index in range(1, 7)
        )

        payload = build_stage_payload(
            metrics,
            market_temperatures={"20260710": _temperature()},
            config={
                "signal_policy": {
                    "normal_market_top_n": 5,
                    "cooldown_trade_days": 0,
                    "blocked_context_names": ["blocked"],
                    "post_rank_no_refill_rejection_reasons": ["blocked_risk_context"],
                }
            },
            trade_date_order=("20260710",),
        )

        self.assertEqual(5, payload["stage_counts"]["ranked_topn"])
        self.assertEqual(4, payload["stage_counts"]["final_signal"])
        self.assertNotIn("000006.SZ", [item["asset_id"] for item in payload["final_signals"]])

    def test_cooldown_counts_actual_trade_days(self) -> None:
        trade_dates = tuple(f"202607{index:02d}" for index in range(1, 13))
        metrics = (
            replace(_metric("000001.SZ"), trade_date=trade_dates[0]),
            replace(_metric("000001.SZ"), trade_date=trade_dates[-1]),
        )

        payload = build_stage_payload(
            metrics,
            market_temperatures={date: replace(_temperature(), trade_date=date) for date in trade_dates},
            config={"signal_policy": {"normal_market_top_n": 5, "cooldown_trade_days": 10}},
            trade_date_order=trade_dates,
        )

        self.assertEqual(2, payload["stage_counts"]["final_signal"])


def _temperature() -> MarketTemperature:
    return MarketTemperature(
        trade_date="20260710",
        sample_size=5000,
        breadth_ma20=0.50,
        breadth_ma60=0.45,
        avg_return_20d=0.01,
        avg_amount_ratio=1.0,
    )


def _metric(asset_id: str, *, setup_score: float = 80.0) -> TrendBreakoutMetrics:
    return TrendBreakoutMetrics(
        asset_id=asset_id,
        trade_date="20260710",
        close=100.0,
        ma5=98.0,
        ma10=96.0,
        ma20=90.0,
        ma30=85.0,
        ma60=70.0,
        ma120=60.0,
        ma20_slope_20d=0.10,
        amount_ratio_20d=1.5,
        max_drawdown_60d=-0.10,
        max_drawdown_120d=-0.20,
        convergence_5_10_20_pct=0.08,
        close_to_high_60d_pct=0.0,
        ma20_deviation_pct=0.11,
        ma30_deviation_pct=0.08,
        ma30_hold_ratio_30d=1.0,
        ma30_hold_ratio_60d=1.0,
        ma30_hold_ratio_90d=1.0,
        ma30_hold_ratio_120d=1.0,
        ma60_hold_ratio_120d=1.0,
        return_20d=0.10,
        red_k_ratio_20d=0.60,
        green_k_ratio_20d=0.40,
        long_shadow_ratio_20d=0.25,
        avg_amount_20d=300000.0,
        close_new_high_60d_flag=True,
        daily_quality_pass=True,
        trend_stability_pass=True,
        market_cap_liquidity_pass=True,
        turnover_quality_pass=True,
        context_strength_pass=True,
        steady_uptrend=True,
        pre_breakout_watch=False,
        breakout_watch=False,
        setup_score=setup_score,
        amount_ratio_prev_20d=1.3,
        large_bearish_body_ratio_20d=0.10,
        max_consecutive_green_k_20d=1,
        single_bull_bar_return_share_20d=0.20,
        impulse_consolidation_days=8,
        ma5_10_20_30_convergence_pct=0.10,
        volume_ratio_5d_20d=1.0,
        turnover_ratio_5d_20d=1.0,
        recent_impulse_return=0.10,
        post_impulse_followthrough_return=0.05,
    )


if __name__ == "__main__":
    unittest.main()
