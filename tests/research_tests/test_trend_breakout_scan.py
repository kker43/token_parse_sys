"""Tests for the steady uptrend breakout scanner."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from stock_lobster.research import (
    KlineBar,
    StockSignalContext,
    TrendBreakoutMetrics,
    TrendBreakoutScanPolicy,
    scan_trend_breakouts,
    select_candidates,
    read_stock_signal_context_tsv,
    summarize_breakout_scan,
)


class TrendBreakoutScanTest(unittest.TestCase):
    def test_amount_ratio_prev_20d_excludes_signal_day(self) -> None:
        bars = _daily_breakout_bars("000099.SZ")
        previous_average = sum(bar.amount for bar in bars[-21:-1]) / 20

        latest = scan_trend_breakouts(bars)[-1]

        self.assertAlmostEqual(
            bars[-1].amount / previous_average,
            latest.amount_ratio_prev_20d,
            places=6,
        )
        self.assertLess(latest.amount_ratio_20d, latest.amount_ratio_prev_20d)

    def test_detects_breakout_watch_candidate(self) -> None:
        bars: list[KlineBar] = []
        price = 10.0
        for index in range(140):
            if index > 20:
                price += 0.2
            amount = 100.0
            if index == 139:
                price += 5.0
                amount = 300.0
            bars.append(
                KlineBar(
                    asset_id="000001.SZ",
                    trade_date=f"2026{index + 1:04d}",
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    amount=amount,
                )
            )

        metrics = scan_trend_breakouts(
            bars,
            TrendBreakoutScanPolicy(start_date="20260001"),
        )
        candidates = [metric for metric in metrics if metric.breakout_watch]

        self.assertTrue(candidates)
        self.assertEqual("000001.SZ", candidates[-1].asset_id)
        self.assertGreaterEqual(candidates[-1].amount_ratio_20d, 1.5)
        self.assertGreaterEqual(candidates[-1].red_k_ratio_20d, 0.45)
        self.assertTrue(candidates[-1].daily_quality_pass)
        self.assertEqual(1, summarize_breakout_scan(candidates)["000001.SZ"]["breakout_watch_count"])

    def test_filters_breakout_when_weekly_context_fails(self) -> None:
        daily_bars = _daily_breakout_bars("000003.SZ")
        weekly_bars = _weekly_bars("000003.SZ", rising=False)

        metrics = scan_trend_breakouts(
            daily_bars,
            TrendBreakoutScanPolicy(
                start_date="20260001",
                require_weekly_uptrend=True,
            ),
            weekly_bars=weekly_bars,
        )
        candidates = [metric for metric in metrics if metric.breakout_watch]

        self.assertFalse(candidates)
        self.assertFalse(metrics[-1].weekly_trend_pass)
        self.assertEqual("20260030", metrics[-1].weekly_asof_trade_date)

    def test_aligns_latest_weekly_context_asof_daily_signal_date(self) -> None:
        daily_bars = _daily_breakout_bars("000004.SZ")
        weekly_bars = _weekly_bars("000004.SZ", rising=True)

        metrics = scan_trend_breakouts(
            daily_bars,
            TrendBreakoutScanPolicy(
                start_date="20260001",
                require_weekly_uptrend=True,
            ),
            weekly_bars=weekly_bars,
        )
        candidates = [metric for metric in metrics if metric.breakout_watch]

        self.assertTrue(candidates)
        self.assertTrue(candidates[-1].weekly_trend_pass)
        self.assertEqual("20260030", candidates[-1].weekly_asof_trade_date)
        self.assertGreater(candidates[-1].weekly_ma10, candidates[-1].weekly_ma20)

    def test_filters_breakout_when_recent_red_green_ratio_is_weak(self) -> None:
        bars: list[KlineBar] = []
        price = 10.0
        for index in range(140):
            if index > 20:
                price += 0.2
            amount = 100.0
            open_price = price
            close_price = price
            if index >= 120:
                open_price = price + 0.3
                close_price = price
            if index == 139:
                price += 5.0
                open_price = price + 0.3
                close_price = price
                amount = 300.0
            bars.append(
                KlineBar(
                    asset_id="000002.SZ",
                    trade_date=f"2026{index + 1:04d}",
                    open=open_price,
                    high=max(open_price, close_price),
                    low=min(open_price, close_price),
                    close=close_price,
                    amount=amount,
                )
            )

        metrics = scan_trend_breakouts(
            bars,
            TrendBreakoutScanPolicy(start_date="20260001"),
        )
        latest = metrics[-1]

        self.assertTrue(latest.close_new_high_60d_flag)
        self.assertGreaterEqual(latest.amount_ratio_20d, 1.5)
        self.assertLess(latest.red_k_ratio_20d, 0.45)
        self.assertFalse(latest.daily_quality_pass)
        self.assertFalse(latest.breakout_watch)

    def test_detects_pre_breakout_watch_candidate(self) -> None:
        bars: list[KlineBar] = []
        price = 10.0
        for index in range(140):
            if index > 20:
                price += 0.2
            close_price = price
            if index == 139:
                close_price = price - 0.45
            bars.append(
                KlineBar(
                    asset_id="000005.SZ",
                    trade_date=f"2026{index + 1:04d}",
                    open=close_price,
                    high=close_price,
                    low=close_price,
                    close=close_price,
                    amount=120.0,
                )
            )

        metrics = scan_trend_breakouts(
            bars,
            TrendBreakoutScanPolicy(start_date="20260001"),
        )
        latest = metrics[-1]

        self.assertTrue(latest.steady_uptrend)
        self.assertFalse(latest.close_new_high_60d_flag)
        self.assertLess(latest.close_to_high_60d_pct, -0.002)
        self.assertGreaterEqual(latest.close_to_high_60d_pct, -0.08)
        self.assertTrue(latest.pre_breakout_watch)
        self.assertFalse(latest.breakout_watch)

    def test_filters_pre_breakout_when_ma30_hold_ratio_is_not_sustained(self) -> None:
        bars = _mostly_below_ma30_then_recent_repair_bars("000006.SZ")

        metrics = scan_trend_breakouts(
            bars,
            TrendBreakoutScanPolicy(start_date="20260001"),
        )
        latest = metrics[-1]

        self.assertGreaterEqual(latest.ma30_hold_ratio_30d, 0.75)
        self.assertLess(latest.ma30_hold_ratio_90d, 0.75)
        self.assertTrue(latest.trend_stability_pass)
        self.assertFalse(latest.pre_breakout_watch)
        self.assertIn("pre_breakout_ma30_sustained_failed", latest.quality_failure_reasons)

    def test_allows_base_breakout_start_when_longer_ma30_hold_ratio_is_lower(self) -> None:
        bars = _base_breakout_start_bars("000007.SZ")

        metrics = scan_trend_breakouts(
            bars,
            TrendBreakoutScanPolicy(start_date="20260001"),
        )
        latest = metrics[-1]

        self.assertLess(latest.ma30_hold_ratio_90d, 0.75)
        self.assertGreaterEqual(latest.ma30_hold_ratio_60d, 0.50)
        self.assertTrue(latest.close_new_high_60d_flag)
        self.assertTrue(latest.trend_stability_pass)
        self.assertTrue(latest.breakout_watch)

    def test_filters_breakout_when_weak_shape_filter_flags_user_rejected_pattern(self) -> None:
        bars = _one_bar_pump_after_choppy_green_bars("000009.SZ")

        metrics = scan_trend_breakouts(
            bars,
            TrendBreakoutScanPolicy(
                start_date="20260001",
                min_red_k_ratio_20d=0.35,
                enable_weak_shape_filter=True,
                max_large_bearish_body_ratio_20d=0.20,
                max_consecutive_green_k_20d=4,
                max_single_bull_bar_return_share_20d=0.55,
                min_impulse_consolidation_days=5,
                min_ma5_10_20_30_convergence_pct=0.08,
            ),
        )
        latest = metrics[-1]

        self.assertTrue(latest.close_new_high_60d_flag)
        self.assertGreater(latest.large_bearish_body_ratio_20d, 0.20)
        self.assertGreater(latest.max_consecutive_green_k_20d, 4)
        self.assertGreater(latest.single_bull_bar_return_share_20d, 0.55)
        self.assertLess(latest.impulse_consolidation_days, 5)
        self.assertLess(latest.ma5_10_20_30_convergence_pct, 0.08)
        self.assertFalse(latest.weak_shape_pass)
        self.assertFalse(latest.daily_quality_pass)
        self.assertFalse(latest.breakout_watch)
        self.assertIn("large_bearish_body_ratio_failed", latest.quality_failure_reasons)
        self.assertIn("consecutive_green_k_failed", latest.quality_failure_reasons)
        self.assertIn("single_bull_bar_dominance_failed", latest.quality_failure_reasons)
        self.assertIn("impulse_consolidation_days_failed", latest.quality_failure_reasons)
        self.assertIn("ma5_10_20_30_convergence_failed", latest.quality_failure_reasons)

    def test_weak_shape_metrics_are_observational_until_filter_is_enabled(self) -> None:
        bars = _one_bar_pump_after_choppy_green_bars("000010.SZ")

        metrics = scan_trend_breakouts(
            bars,
            TrendBreakoutScanPolicy(
                start_date="20260001",
                min_red_k_ratio_20d=0.35,
                enable_weak_shape_filter=False,
                max_large_bearish_body_ratio_20d=0.20,
                max_consecutive_green_k_20d=4,
                max_single_bull_bar_return_share_20d=0.55,
                min_impulse_consolidation_days=5,
                min_ma5_10_20_30_convergence_pct=0.08,
            ),
        )
        latest = metrics[-1]

        self.assertTrue(latest.weak_shape_pass)
        self.assertTrue(latest.daily_quality_pass)
        self.assertTrue(latest.breakout_watch)
        self.assertGreater(latest.large_bearish_body_ratio_20d, 0.20)
        self.assertGreater(latest.single_bull_bar_return_share_20d, 0.55)

    def test_applies_external_market_cap_turnover_and_context_filters(self) -> None:
        bars = _daily_breakout_bars("000008.SZ")
        contexts = [
            StockSignalContext(
                asset_id="000008.SZ",
                trade_date=bars[-1].trade_date,
                name="测试股份",
                list_status="L",
                total_mv=900_000.0,
                turnover_rate=8.0,
                max_turnover_rate_20d=18.0,
                avg_turnover_rate_20d=6.0,
                strong_industry_hit=True,
            )
        ]

        metrics = scan_trend_breakouts(
            bars,
            TrendBreakoutScanPolicy(
                start_date="20260001",
                require_normal_listing=True,
                min_total_mv=1_000_000.0,
                max_turnover_rate_20d=20.0,
                require_context_strength=True,
            ),
            stock_contexts=contexts,
        )
        latest = metrics[-1]

        self.assertFalse(latest.market_cap_liquidity_pass)
        self.assertFalse(latest.breakout_watch)
        self.assertIn("total_mv_below_threshold", latest.quality_failure_reasons)

    def test_reads_stock_signal_context_tsv_without_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "context.tsv"
            path.write_text(
                "000001.SZ\t20260703\t测试股份\t半导体\t主板\tL\t1000000\t8\t18\t6\t300000000\t1\t0\t半导体\t\t1.25\n",
                encoding="utf-8",
            )

            contexts = read_stock_signal_context_tsv(path)

        self.assertEqual(1, len(contexts))
        self.assertEqual(300_000_000.0, contexts[0].avg_amount_20d)
        self.assertTrue(contexts[0].strong_industry_hit)
        self.assertFalse(contexts[0].strong_concept_hit)
        self.assertEqual(("半导体",), contexts[0].strong_industry_names)
        self.assertEqual(1.25, contexts[0].volume_ratio_5d_20d)

    def test_select_candidates_limits_top_n_per_date_by_setup_score(self) -> None:
        candidates = (
            _metric("000001.SZ", "20260601", breakout_watch=True, setup_score=55),
            _metric("000002.SZ", "20260601", breakout_watch=True, setup_score=80),
            _metric("000003.SZ", "20260601", breakout_watch=True, setup_score=70),
            _metric("000004.SZ", "20260602", breakout_watch=True, setup_score=60),
        )

        selected = select_candidates(candidates, mode="breakout", top_n_per_date=2)

        self.assertEqual(
            ["000002.SZ", "000003.SZ", "000004.SZ"],
            [item.asset_id for item in selected],
        )

    def test_select_candidates_without_limit_does_not_rank_by_incomplete_score(self) -> None:
        candidates = (
            _metric("000002.SZ", "20260601", breakout_watch=True, setup_score=80),
            _metric("000001.SZ", "20260601", breakout_watch=True, setup_score=55),
        )

        selected = select_candidates(candidates, mode="breakout")

        self.assertEqual(["000001.SZ", "000002.SZ"], [item.asset_id for item in selected])


def _daily_breakout_bars(asset_id: str) -> list[KlineBar]:
    bars: list[KlineBar] = []
    price = 10.0
    for index in range(140):
        if index > 20:
            price += 0.2
        amount = 100.0
        if index == 139:
            price += 5.0
            amount = 300.0
        bars.append(
            KlineBar(
                asset_id=asset_id,
                trade_date=f"2026{index + 1:04d}",
                open=price,
                high=price,
                low=price,
                close=price,
                amount=amount,
            )
        )
    return bars


def _weekly_bars(asset_id: str, rising: bool) -> list[KlineBar]:
    bars: list[KlineBar] = []
    price = 20.0
    for index in range(30):
        price = price + 1.0 if rising else price - 0.1
        if not rising and index >= 20:
            price -= 0.6
        bars.append(
            KlineBar(
                asset_id=asset_id,
                trade_date=f"2026{index + 1:04d}",
                open=price,
                high=price,
                low=price,
                close=price,
                amount=100.0,
            )
        )
    return bars


def _mostly_below_ma30_then_recent_repair_bars(asset_id: str) -> list[KlineBar]:
    bars: list[KlineBar] = []
    price = 30.0
    for index in range(140):
        if index < 80:
            price -= 0.06
        elif index < 115:
            price += 0.08
        else:
            price += 0.18
        close_price = price
        if index == 139:
            close_price = max(price - 0.20, price * 0.995)
        bars.append(
            KlineBar(
                asset_id=asset_id,
                trade_date=f"2026{index + 1:04d}",
                open=close_price,
                high=close_price * 1.01,
                low=close_price * 0.99,
                close=close_price,
                amount=150.0,
            )
        )
    return bars


def _base_breakout_start_bars(asset_id: str) -> list[KlineBar]:
    bars: list[KlineBar] = []
    price = 30.0
    for index in range(140):
        if index < 70:
            price -= 0.05
        elif index < 118:
            price += 0.04
        else:
            price += 0.25
        amount = 100.0
        if index == 139:
            price += 1.5
            amount = 250.0
        bars.append(
            KlineBar(
                asset_id=asset_id,
                trade_date=f"2026{index + 1:04d}",
                open=price,
                high=price,
                low=price,
                close=price,
                amount=amount,
            )
        )
    return bars


def _one_bar_pump_after_choppy_green_bars(asset_id: str) -> list[KlineBar]:
    bars: list[KlineBar] = []
    close_price = 30.0
    for index in range(140):
        amount = 120.0
        if index < 120:
            close_price += 0.05
            open_price = close_price - 0.02
        elif index < 134:
            close_price += 0.02
            if index % 2 == 0:
                open_price = close_price + 0.95
            else:
                open_price = close_price - 0.04
        elif index < 139:
            close_price += 0.03
            open_price = close_price + 0.12
        else:
            previous_close = close_price
            close_price = previous_close + 6.0
            open_price = previous_close + 0.25
            amount = 300.0
        high = max(open_price, close_price) + 0.05
        low = min(open_price, close_price) - 0.05
        bars.append(
            KlineBar(
                asset_id=asset_id,
                trade_date=f"2026{index + 1:04d}",
                open=open_price,
                high=high,
                low=low,
                close=close_price,
                amount=amount,
            )
        )
    return bars


def _metric(
    asset_id: str,
    trade_date: str,
    *,
    breakout_watch: bool = False,
    pre_breakout_watch: bool = False,
    setup_score: float = 0.0,
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
        amount_ratio_20d=1.5,
        max_drawdown_60d=-0.10,
        max_drawdown_120d=-0.20,
        convergence_5_10_20_pct=0.08,
        close_to_high_60d_pct=0.0 if breakout_watch else -0.03,
        ma20_deviation_pct=0.11,
        ma30_deviation_pct=0.18,
        ma30_hold_ratio_30d=1.0,
        ma30_hold_ratio_60d=1.0,
        ma30_hold_ratio_90d=1.0,
        ma30_hold_ratio_120d=1.0,
        ma60_hold_ratio_120d=1.0,
        return_20d=0.10,
        red_k_ratio_20d=0.60,
        green_k_ratio_20d=0.40,
        long_shadow_ratio_20d=0.25,
        large_bearish_body_ratio_20d=0.0,
        max_consecutive_green_k_20d=1,
        single_bull_bar_return_share_20d=0.20,
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
    )


if __name__ == "__main__":
    unittest.main()
