"""Tests for v3 steady uptrend research selection."""

from __future__ import annotations

import unittest

from stock_lobster.research.steady_uptrend_v3 import (
    MarketTemperature,
    SteadyUptrendV3Policy,
    select_v3_observation_candidates,
    select_v3_signal_candidates,
    v3_rejection_reasons,
)
from stock_lobster.research.trend_breakout_scan import TrendBreakoutMetrics


class SteadyUptrendV3SelectionTest(unittest.TestCase):
    def test_rejects_pre_breakout_when_market_is_overheated(self) -> None:
        metric = _metric("000001.SZ", "20260601", pre_breakout_watch=True)
        temperature = MarketTemperature(
            trade_date="20260601",
            sample_size=100,
            breadth_ma20=0.62,
            breadth_ma60=0.58,
            avg_return_20d=0.05,
            avg_amount_ratio=2.1,
        )

        reasons = v3_rejection_reasons(
            metric,
            market_temperature=temperature,
            policy=SteadyUptrendV3Policy(),
        )

        self.assertIn("market_temperature_overheated", reasons)
        self.assertEqual(
            (),
            select_v3_observation_candidates(
                (metric,),
                market_temperatures={"20260601": temperature},
                policy=SteadyUptrendV3Policy(),
            ),
        )

    def test_blocks_fading_context_unless_preferred_rotation_context_is_present(self) -> None:
        policy = SteadyUptrendV3Policy()
        fading_only = _metric(
            "000001.SZ",
            "20260601",
            pre_breakout_watch=True,
            strong_concept_names=("数据中心",),
        )
        mixed_leader = _metric(
            "000002.SZ",
            "20260601",
            pre_breakout_watch=True,
            strong_concept_names=("数据中心", "PCB概念"),
        )
        temperature = _healthy_temperature("20260601")

        selected = select_v3_observation_candidates(
            (fading_only, mixed_leader),
            market_temperatures={"20260601": temperature},
            policy=policy,
        )

        self.assertIn("fading_context_without_preferred_rotation", v3_rejection_reasons(
            fading_only,
            market_temperature=temperature,
            policy=policy,
        ))
        self.assertEqual(["000002.SZ"], [item.asset_id for item in selected])

    def test_can_disable_market_temperature_hard_thresholds(self) -> None:
        metric = _metric("000001.SZ", "20260601", pre_breakout_watch=True)
        temperature = MarketTemperature(
            trade_date="20260601",
            sample_size=100,
            breadth_ma20=0.80,
            breadth_ma60=0.70,
            avg_return_20d=0.08,
            avg_amount_ratio=2.5,
        )
        policy = SteadyUptrendV3Policy(
            max_market_breadth_ma20=None,
            max_market_avg_return_20d=None,
        )

        reasons = v3_rejection_reasons(
            metric,
            market_temperature=temperature,
            policy=policy,
        )

        self.assertNotIn("market_temperature_overheated", reasons)
        self.assertNotIn("market_breadth_ma20_overheated", reasons)
        self.assertNotIn("market_avg_return_20d_overheated", reasons)

    def test_can_require_minimum_5d_20d_volume_ratio_for_confirmation(self) -> None:
        metric = _metric(
            "000001.SZ",
            "20260601",
            pre_breakout_watch=True,
            volume_ratio_5d_20d=1.19,
        )
        temperature = _healthy_temperature("20260601")
        policy = SteadyUptrendV3Policy(min_volume_ratio_5d_20d=1.2)

        reasons = v3_rejection_reasons(
            metric,
            market_temperature=temperature,
            policy=policy,
        )

        self.assertIn("volume_ratio_5d_20d_below_v3_threshold", reasons)

    def test_rejects_missing_5d_20d_volume_ratio_when_required(self) -> None:
        metric = _metric(
            "000001.SZ",
            "20260601",
            pre_breakout_watch=True,
            volume_ratio_5d_20d=None,
        )

        reasons = v3_rejection_reasons(
            metric,
            market_temperature=_healthy_temperature("20260601"),
            policy=SteadyUptrendV3Policy(min_volume_ratio_5d_20d=1.2),
        )

        self.assertIn("volume_ratio_5d_20d_missing", reasons)

    def test_blocks_explicit_risk_context_without_preferred_rotation_exception(self) -> None:
        metric = _metric(
            "000001.SZ",
            "20260601",
            pre_breakout_watch=True,
            strong_concept_names=("液冷服务器", "PCB概念"),
        )
        temperature = _healthy_temperature("20260601")
        policy = SteadyUptrendV3Policy(blocked_context_names=("液冷服务器",))

        reasons = v3_rejection_reasons(
            metric,
            market_temperature=temperature,
            policy=policy,
        )

        self.assertIn("blocked_risk_context", reasons)

    def test_can_apply_post_rank_rejections_without_daily_refill(self) -> None:
        policy = SteadyUptrendV3Policy(
            top_n_per_date=1,
            min_volume_ratio_5d_20d=1.2,
            post_rank_no_refill_rejection_reasons=("volume_ratio_5d_20d_below_v3_threshold",),
        )
        weak_volume_leader = _metric(
            "000001.SZ",
            "20260601",
            pre_breakout_watch=True,
            setup_score=90,
            volume_ratio_5d_20d=1.19,
        )
        confirmed_laggard = _metric(
            "000002.SZ",
            "20260601",
            pre_breakout_watch=True,
            setup_score=70,
            volume_ratio_5d_20d=1.30,
        )

        selected = select_v3_observation_candidates(
            (weak_volume_leader, confirmed_laggard),
            market_temperatures={"20260601": _healthy_temperature("20260601")},
            policy=policy,
        )

        self.assertEqual((), selected)

    def test_applies_daily_top_n_and_allows_same_stock_on_adjacent_dates(self) -> None:
        policy = SteadyUptrendV3Policy(top_n_per_date=1)
        metrics = (
            _metric("000001.SZ", "20260601", breakout_watch=True, setup_score=60),
            _metric("000002.SZ", "20260601", breakout_watch=True, setup_score=80),
            _metric("000002.SZ", "20260602", breakout_watch=True, setup_score=90),
            _metric("000003.SZ", "20260603", breakout_watch=True, setup_score=70),
        )
        temperatures = {date: _healthy_temperature(date) for date in ("20260601", "20260602", "20260603")}

        selected = select_v3_signal_candidates(
            metrics,
            market_temperatures=temperatures,
            policy=policy,
            trade_date_order=("20260601", "20260602", "20260603"),
        )

        self.assertEqual(
            [
                ("000002.SZ", "20260601"),
                ("000002.SZ", "20260602"),
                ("000003.SZ", "20260603"),
            ],
            [(item.asset_id, item.trade_date) for item in selected],
        )


def _healthy_temperature(trade_date: str) -> MarketTemperature:
    return MarketTemperature(
        trade_date=trade_date,
        sample_size=100,
        breadth_ma20=0.30,
        breadth_ma60=0.35,
        avg_return_20d=0.01,
        avg_amount_ratio=1.1,
    )


def _metric(
    asset_id: str,
    trade_date: str,
    *,
    breakout_watch: bool = False,
    pre_breakout_watch: bool = False,
    setup_score: float = 60.0,
    amount_ratio_20d: float = 1.2,
    volume_ratio_5d_20d: float | None = 1.2,
    strong_concept_names: tuple[str, ...] = ("PCB概念",),
) -> TrendBreakoutMetrics:
    return TrendBreakoutMetrics(
        asset_id=asset_id,
        trade_date=trade_date,
        close=100.0,
        ma5=98.0,
        ma10=96.0,
        ma20=90.0,
        ma30=85.0,
        ma60=70.0,
        ma120=60.0,
        ma20_slope_20d=0.10,
        amount_ratio_20d=amount_ratio_20d,
        max_drawdown_60d=-0.10,
        max_drawdown_120d=-0.20,
        convergence_5_10_20_pct=0.08,
        close_to_high_60d_pct=0.0 if breakout_watch else -0.04,
        ma20_deviation_pct=0.11,
        ma30_deviation_pct=0.18,
        ma30_hold_ratio_30d=1.0,
        ma30_hold_ratio_60d=1.0,
        ma30_hold_ratio_90d=1.0,
        ma30_hold_ratio_120d=1.0,
        ma60_hold_ratio_120d=1.0,
        return_20d=0.10,
        red_k_ratio_20d=0.65,
        green_k_ratio_20d=0.35,
        long_shadow_ratio_20d=0.25,
        large_bearish_body_ratio_20d=0.20,
        max_consecutive_green_k_20d=2,
        single_bull_bar_return_share_20d=0.18,
        impulse_consolidation_days=8,
        ma5_10_20_30_convergence_pct=0.15,
        avg_amount_20d=120.0,
        close_new_high_60d_flag=breakout_watch,
        daily_quality_pass=True,
        trend_stability_pass=True,
        weak_shape_pass=True,
        market_cap_liquidity_pass=True,
        turnover_quality_pass=True,
        context_strength_pass=True,
        steady_uptrend=True,
        pre_breakout_watch=pre_breakout_watch,
        breakout_watch=breakout_watch,
        setup_score=setup_score,
        strong_concept_names=strong_concept_names,
        volume_ratio_5d_20d=volume_ratio_5d_20d,
    )


if __name__ == "__main__":
    unittest.main()
