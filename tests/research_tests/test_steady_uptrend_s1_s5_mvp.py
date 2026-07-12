"""Behavior tests for the steady-uptrend S1-S5 MVP evaluator."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
import math
import unittest

from stock_lobster.research.steady_uptrend_s1_s5_mvp import (
    StageDecision,
    SteadyUptrendMvpCandidate,
    SteadyUptrendMvpPolicy,
    build_steady_uptrend_mvp_report,
    evaluate_stability_refinement,
    evaluate_structure_recall,
    evaluate_steady_uptrend_mvp,
    ma20_deviation_level,
)
from stock_lobster.research.trend_breakout_scan import KlineBar, StockSignalContext


class SteadyUptrendS1S5MvpTest(unittest.TestCase):
    def test_healthy_mature_trend_passes_s1_and_s2(self) -> None:
        daily = _rising_bars("301217.SZ", 150, step=0.35)
        weekly = _rising_bars("301217.SZ", 130, step=1.0, weekly=True)

        result = evaluate_steady_uptrend_mvp(
            daily,
            weekly,
            _context("301217.SZ", daily[-1].trade_date),
            signal_date=daily[-1].trade_date,
        )

        self.assertTrue(result.stages["s1_quality_filter"].passed)
        self.assertTrue(result.stages["s2_mature_trend_filter"].passed)
        self.assertTrue(result.stages["s3_structure_recall"].passed)
        self.assertTrue(result.stages["s4_stability_refinement"].passed)
        self.assertGreaterEqual(result.metrics["ma60_hold_ratio_60d"], 0.50)
        self.assertGreaterEqual(result.metrics["return_60d"], 0.05)

    def test_s1_thresholds_are_inclusive(self) -> None:
        daily = _rising_bars("301217.SZ", 150, step=0.35, amount=200_000.0)
        weekly = _rising_bars("301217.SZ", 130, step=1.0, weekly=True)
        context = replace(
            _context("301217.SZ", daily[-1].trade_date),
            total_mv=1_000_000.0,
            avg_amount_20d=200_000.0,
        )

        result = evaluate_steady_uptrend_mvp(
            daily,
            weekly,
            context,
            signal_date=daily[-1].trade_date,
        )

        self.assertTrue(result.stages["s1_quality_filter"].passed)

    def test_s1_reports_market_cap_and_liquidity_blockers(self) -> None:
        daily = _rising_bars("301217.SZ", 150, step=0.35)
        weekly = _rising_bars("301217.SZ", 130, step=1.0, weekly=True)
        context = replace(
            _context("301217.SZ", daily[-1].trade_date),
            total_mv=999_999.0,
            avg_amount_20d=199_999.0,
        )

        result = evaluate_steady_uptrend_mvp(
            daily,
            weekly,
            context,
            signal_date=daily[-1].trade_date,
        )

        self.assertEqual(
            ("market_cap_below_minimum", "avg_amount_20d_below_minimum"),
            result.stages["s1_quality_filter"].blockers,
        )
        self.assertFalse(result.stages["s2_mature_trend_filter"].evaluated)

    def test_s2_requires_strict_weekly_ma_stack(self) -> None:
        daily = _rising_bars("301217.SZ", 150, step=0.35)
        weekly = list(_rising_bars("301217.SZ", 130, step=1.0, weekly=True))
        flat_close = weekly[-1].close
        for index in range(70, len(weekly)):
            weekly[index] = _with_close(weekly[index], flat_close)

        result = evaluate_steady_uptrend_mvp(
            daily,
            weekly,
            _context("301217.SZ", daily[-1].trade_date),
            signal_date=daily[-1].trade_date,
        )

        self.assertFalse(result.stages["s2_mature_trend_filter"].passed)
        self.assertIn(
            "weekly_mature_trend_failed",
            result.stages["s2_mature_trend_filter"].blockers,
        )

    def test_s1_rejects_stale_weekly_context(self) -> None:
        daily = _rising_bars("301217.SZ", 150, step=0.35)
        weekly = _rising_bars("301217.SZ", 130, step=1.0, weekly=True)[:-1]

        result = evaluate_steady_uptrend_mvp(
            daily,
            weekly,
            _context("301217.SZ", daily[-1].trade_date),
            signal_date=daily[-1].trade_date,
        )

        self.assertIn(
            "weekly_asof_mismatch",
            result.stages["s1_quality_filter"].blockers,
        )

    def test_s1_rejects_duplicate_daily_trade_date(self) -> None:
        daily = _rising_bars("301217.SZ", 150, step=0.35)
        duplicate = replace(daily[-1], close=daily[-1].close * 2)
        weekly = _rising_bars("301217.SZ", 130, step=1.0, weekly=True)

        result = evaluate_steady_uptrend_mvp(
            daily + (duplicate,),
            weekly,
            _context("301217.SZ", daily[-1].trade_date),
            signal_date=daily[-1].trade_date,
        )

        self.assertIn(
            "duplicate_daily_trade_date",
            result.stages["s1_quality_filter"].blockers,
        )
        self.assertFalse(result.stages["s2_mature_trend_filter"].evaluated)

    def test_policy_uses_approved_thresholds(self) -> None:
        policy = SteadyUptrendMvpPolicy()

        self.assertEqual(1_000_000.0, policy.min_total_mv)
        self.assertEqual(200_000.0, policy.min_avg_amount_20d)
        self.assertEqual(0.50, policy.min_ma60_hold_ratio_60d)
        self.assertEqual(-0.10, policy.min_close_to_high_60d_pct)
        self.assertEqual(0.60, policy.min_upper_shadow_ratio)
        self.assertEqual(5, policy.min_upper_shadow_days_20d)
        self.assertEqual(0.56, policy.min_avg_total_shadow_share_60d)
        self.assertEqual(5, policy.min_ma_alignment_transitions_60d)
        self.assertEqual(0.45, policy.min_red_k_ratio_60d)
        self.assertEqual(0.07, policy.min_extreme_bearish_drop)
        self.assertEqual(3, policy.min_extreme_bearish_days_10d)

    def test_s3_a_accepts_exactly_ten_percent_below_60d_high(self) -> None:
        closes = [70.0] * 100
        closes[-20] = 100.0
        closes[-1] = 90.0
        bars = _bars_from_closes("301217.SZ", closes)

        decision = evaluate_structure_recall(bars, signal_date=bars[-1].trade_date)

        self.assertIn("s3_a_high_position", decision.matched_structures)
        self.assertAlmostEqual(-0.10, decision.metrics["close_to_high_60d_pct"])

    def test_s3_b_recalls_healthy_pullback_and_recovery(self) -> None:
        closes = [50.0 + index * 0.25 for index in range(100)]
        closes.extend(
            [
                78.0,
                82.0,
                86.0,
                90.0,
                94.0,
                100.0,
                97.0,
                94.0,
                91.0,
                88.0,
                89.0,
                90.0,
                91.0,
                92.0,
                93.0,
                94.0,
                95.0,
                96.0,
                97.0,
                98.0,
                99.0,
            ]
        )
        bars = _bars_from_closes("301217.SZ", closes)

        decision = evaluate_structure_recall(bars, signal_date=bars[-1].trade_date)

        self.assertIn("s3_b_pullback_recovery", decision.matched_structures)
        self.assertLessEqual(decision.metrics["pullback_depth"], -0.05)
        self.assertGreaterEqual(decision.metrics["recovery_from_trough"], 0.03)

    def test_s3_b_rejects_effective_ma60_breakdown(self) -> None:
        closes = [80.0 + index * 0.1 for index in range(100)]
        closes.extend(
            [
                100.0,
                98.0,
                95.0,
                88.0,
                70.0,
                69.0,
                72.0,
                75.0,
                78.0,
                80.0,
                82.0,
                84.0,
                86.0,
                88.0,
                90.0,
                92.0,
                94.0,
                95.0,
                96.0,
                97.0,
                98.0,
            ]
        )
        bars = _bars_from_closes("301217.SZ", closes)

        decision = evaluate_structure_recall(bars, signal_date=bars[-1].trade_date)

        self.assertTrue(decision.metrics["effective_ma60_breakdown"])
        self.assertNotIn("s3_b_pullback_recovery", decision.matched_structures)

    def test_s3_c_rejects_wide_swing_rebound(self) -> None:
        closes = [50.0 + index * 0.3 for index in range(110)]
        start = closes[-1]
        closes.extend(
            [
                start * 0.99,
                start * 0.98,
                start * 0.97,
                start * 0.95,
                start * 0.94,
                start * 0.98,
                start * 1.02,
                start * 1.08,
                start * 1.14,
                start * 1.20,
            ]
        )
        bars = _bars_from_closes("301217.SZ", closes)

        decision = evaluate_structure_recall(bars, signal_date=bars[-1].trade_date)

        self.assertTrue(decision.metrics["wide_swing_rebound"])
        self.assertNotIn("s3_c_steady_ma", decision.matched_structures)

    def test_s4_shadow_noise_requires_all_three_composite_conditions(self) -> None:
        bars = _noisy_shadow_bars("301217.SZ")

        decision = evaluate_stability_refinement(
            bars,
            signal_date=bars[-1].trade_date,
        )

        self.assertEqual(5, decision.metrics["upper_shadow_days_20d"])
        self.assertGreaterEqual(decision.metrics["avg_total_shadow_share_60d"], 0.56)
        self.assertGreaterEqual(decision.metrics["ma_alignment_transitions_60d"], 5)
        self.assertIn("noisy_shadow_ma_flip_composite", decision.blockers)

    def test_s4_upper_shadows_alone_do_not_reject(self) -> None:
        bars = list(_noisy_shadow_bars("301217.SZ"))
        for index in range(len(bars) - 61, len(bars) - 1):
            bar = bars[index]
            bars[index] = replace(
                bar,
                open=bar.close - 0.8,
                high=bar.close + 0.2,
                low=bar.close - 0.8,
            )
        for index in range(len(bars) - 21, len(bars) - 16):
            bar = bars[index]
            bars[index] = replace(
                bar,
                open=bar.close - 0.4,
                high=bar.close + 0.6,
                low=bar.close - 0.4,
            )

        decision = evaluate_stability_refinement(
            bars,
            signal_date=bars[-1].trade_date,
        )

        self.assertEqual(5, decision.metrics["upper_shadow_days_20d"])
        self.assertLess(decision.metrics["avg_total_shadow_share_60d"], 0.56)
        self.assertNotIn("noisy_shadow_ma_flip_composite", decision.blockers)

    def test_s4_rejects_red_k_ratio_below_45_percent(self) -> None:
        bars = list(_rising_bars("301217.SZ", 100, step=0.2))
        prior_60_start = len(bars) - 61
        for offset in range(60):
            index = prior_60_start + offset
            bar = bars[index]
            open_value = bar.close - 0.2 if offset < 26 else bar.close + 0.2
            bars[index] = replace(bar, open=open_value)

        decision = evaluate_stability_refinement(
            bars,
            signal_date=bars[-1].trade_date,
        )

        self.assertAlmostEqual(26 / 60, decision.metrics["red_k_ratio_60d"])
        self.assertIn("low_red_k_ratio_60d", decision.blockers)

    def test_s4_rejects_three_extreme_bearish_days_in_previous_ten(self) -> None:
        closes = [100.0] * 89 + [100.0, 92.0, 96.0, 88.0, 93.0, 85.0, 90.0, 91.0, 92.0, 93.0, 94.0, 95.0]
        bars = list(_bars_from_closes("301217.SZ", closes))
        for index in (-11, -9, -7):
            bars[index] = replace(bars[index], open=bars[index].close + 1.0)

        decision = evaluate_stability_refinement(
            bars,
            signal_date=bars[-1].trade_date,
        )

        self.assertEqual(3, decision.metrics["extreme_bearish_days_10d"])
        self.assertIn("frequent_extreme_bearish_days_10d", decision.blockers)

    def test_s4_inclusive_composite_boundaries_reject(self) -> None:
        bars = _boundary_composite_bars("301217.SZ")

        decision = evaluate_stability_refinement(
            bars,
            signal_date=bars[-1].trade_date,
        )

        self.assertEqual(5, decision.metrics["upper_shadow_days_20d"])
        self.assertAlmostEqual(0.56, decision.metrics["avg_total_shadow_share_60d"])
        self.assertEqual(5, decision.metrics["ma_alignment_transitions_60d"])
        self.assertIn("noisy_shadow_ma_flip_composite", decision.blockers)

    def test_s4_red_k_ratio_exactly_45_percent_passes(self) -> None:
        bars = list(_rising_bars("301217.SZ", 100, step=0.2))
        prior_60_start = len(bars) - 61
        for offset in range(60):
            index = prior_60_start + offset
            bar = bars[index]
            open_value = bar.close - 0.2 if offset < 27 else bar.close + 0.2
            bars[index] = replace(bar, open=open_value)

        decision = evaluate_stability_refinement(
            bars,
            signal_date=bars[-1].trade_date,
        )

        self.assertEqual(0.45, decision.metrics["red_k_ratio_60d"])
        self.assertNotIn("low_red_k_ratio_60d", decision.blockers)

    def test_s4_extreme_bearish_drop_exactly_seven_percent_counts(self) -> None:
        closes = [100.0] * 89 + [100.0, 93.0, 100.0, 93.0, 100.0, 93.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
        bars = list(_bars_from_closes("301217.SZ", closes))
        for index in (-11, -9, -7):
            bars[index] = replace(bars[index], open=bars[index].close + 1.0)

        decision = evaluate_stability_refinement(
            bars,
            signal_date=bars[-1].trade_date,
        )

        self.assertEqual(3, decision.metrics["extreme_bearish_days_10d"])
        self.assertIn("frequent_extreme_bearish_days_10d", decision.blockers)

    def test_s5_accepts_either_strong_industry_or_strong_concept(self) -> None:
        daily = _rising_bars("301217.SZ", 150, step=0.35)
        weekly = _rising_bars("301217.SZ", 130, step=1.0, weekly=True)
        context = replace(
            _context("301217.SZ", daily[-1].trade_date),
            strong_industry_hit=False,
            strong_concept_hit=True,
        )

        result = evaluate_steady_uptrend_mvp(
            daily,
            weekly,
            context,
            signal_date=daily[-1].trade_date,
        )

        self.assertTrue(result.stages["s5_entry_selection"].passed)
        self.assertIn("ma20_deviation_pct", result.metrics)
        self.assertIn("ma20_deviation_level", result.metrics)

    def test_s5_rejects_when_neither_context_is_strong(self) -> None:
        daily = _rising_bars("301217.SZ", 150, step=0.35)
        weekly = _rising_bars("301217.SZ", 130, step=1.0, weekly=True)
        context = replace(
            _context("301217.SZ", daily[-1].trade_date),
            strong_industry_hit=False,
            strong_concept_hit=False,
        )

        result = evaluate_steady_uptrend_mvp(
            daily,
            weekly,
            context,
            signal_date=daily[-1].trade_date,
        )

        self.assertEqual(
            ("context_strength_unavailable",),
            result.stages["s5_entry_selection"].blockers,
        )

    def test_s5_requires_close_strictly_above_ma5(self) -> None:
        daily = list(_rising_bars("301217.SZ", 150, step=0.35))
        weekly = _rising_bars("301217.SZ", 130, step=1.0, weekly=True)
        previous_four_average = sum(bar.close for bar in daily[-5:-1]) / 4
        daily[-1] = _with_close(daily[-1], previous_four_average)

        result = evaluate_steady_uptrend_mvp(
            daily,
            weekly,
            _context("301217.SZ", daily[-1].trade_date),
            signal_date=daily[-1].trade_date,
        )

        self.assertAlmostEqual(result.metrics["close"], result.metrics["ma5"])
        self.assertIn(
            "close_not_above_ma5",
            result.stages["s5_entry_selection"].blockers,
        )
        self.assertIn("ma20_deviation_pct", result.metrics)

    def test_s5_requires_close_strictly_above_prior_20d_close_high(self) -> None:
        daily = list(_rising_bars("301217.SZ", 150, step=0.35))
        weekly = _rising_bars("301217.SZ", 130, step=1.0, weekly=True)
        prior_20d_close_high = max(bar.close for bar in daily[-21:-1])
        daily[-1] = _with_close(daily[-1], prior_20d_close_high)

        result = evaluate_steady_uptrend_mvp(
            daily,
            weekly,
            _context("301217.SZ", daily[-1].trade_date),
            signal_date=daily[-1].trade_date,
        )

        self.assertGreater(result.metrics["close"], result.metrics["ma5"])
        self.assertAlmostEqual(
            result.metrics["close"],
            result.metrics["prior_high_close_20d"],
        )
        self.assertIn(
            "close_not_above_prior_high_20d",
            result.stages["s5_entry_selection"].blockers,
        )

    def test_ma20_deviation_boundaries_enter_the_higher_level(self) -> None:
        self.assertEqual("normal", ma20_deviation_level(0.199999))
        self.assertEqual("20", ma20_deviation_level(0.20))
        self.assertEqual("30", ma20_deviation_level(0.30))
        self.assertEqual("40", ma20_deviation_level(0.40))
        self.assertEqual("50", ma20_deviation_level(0.50))
        self.assertEqual("50", ma20_deviation_level(0.80))

    def test_report_groups_once_by_industry_and_sorts_as_approved(self) -> None:
        candidates = (
            _entry_candidate("000003.SZ", "丙", "半导体", 0.08, True, ("光刻机",)),
            _entry_candidate("000002.SZ", "乙", "半导体", 0.06, True, ()),
            _entry_candidate("000001.SZ", "甲", "半导体", 0.04, False, ("先进封装",)),
            _entry_candidate("000004.SZ", "丁", "电子元件", 0.03, True, ("消费电子",)),
            _entry_candidate("000005.SZ", "戊", "电子元件", 0.02, False, ("铜箔",)),
            _entry_candidate("000006.SZ", "己", "有色金属", 0.01, True, ()),
        )

        report = build_steady_uptrend_mvp_report(
            candidates,
            strategy_id="steady_uptrend_s1_s5_mvp_candidate_v1",
            run_id="test-run",
            signal_date="20260710",
            data_dependency_versions={"daily": "fixture-v1"},
        )

        self.assertEqual(
            ["半导体", "电子元件", "有色金属"],
            [group["industry"] for group in report["industry_groups"]],
        )
        semiconductor = report["industry_groups"][0]
        self.assertEqual(
            ["000002.SZ", "000003.SZ", "000001.SZ"],
            [stock["asset_id"] for stock in semiconductor["stocks"]],
        )
        self.assertEqual(6, report["stage_counts"]["s5_entry_selection"]["passed"])
        self.assertEqual(6, len(report["candidates"]))
        self.assertEqual(6, report["markdown"].count("（偏离"))
        self.assertNotIn("概念：；", report["markdown"])


def _rising_bars(
    asset_id: str,
    count: int,
    *,
    step: float,
    amount: float = 300_000.0,
    weekly: bool = False,
) -> tuple[KlineBar, ...]:
    start = (
        date(2023, 5, 26) - timedelta(weeks=count - 1)
        if weekly
        else date(2023, 1, 2)
    )
    spacing = 7 if weekly else 1
    bars = []
    for index in range(count):
        close = 30.0 + step * index
        bars.append(
            KlineBar(
                asset_id=asset_id,
                trade_date=(start + timedelta(days=index * spacing)).strftime("%Y%m%d"),
                open=close - 0.2,
                high=close + 0.4,
                low=close - 0.5,
                close=close,
                amount=amount,
                volume=100_000.0,
            )
        )
    return tuple(bars)


def _context(asset_id: str, trade_date: str) -> StockSignalContext:
    return StockSignalContext(
        asset_id=asset_id,
        trade_date=trade_date,
        name="铜冠铜箔",
        industry="电子元件",
        market="创业板",
        list_status="L",
        total_mv=1_200_000.0,
        avg_amount_20d=300_000.0,
        strong_industry_hit=True,
        strong_concept_hit=False,
        strong_industry_names=("电子元件",),
        strong_concept_names=("先进封装",),
    )


def _bars_from_closes(asset_id: str, closes: list[float]) -> tuple[KlineBar, ...]:
    start = date(2023, 1, 2)
    return tuple(
        KlineBar(
            asset_id=asset_id,
            trade_date=(start + timedelta(days=index)).strftime("%Y%m%d"),
            open=close - 0.2,
            high=close + 0.4,
            low=close - 0.5,
            close=close,
            amount=300_000.0,
            volume=100_000.0,
        )
        for index, close in enumerate(closes)
    )


def _noisy_shadow_bars(asset_id: str) -> tuple[KlineBar, ...]:
    start = date(2023, 1, 2)
    bars = []
    for index in range(100):
        close = 100.0 + index * 0.12 + 3.0 * math.sin(index * math.pi / 4)
        bars.append(
            KlineBar(
                asset_id=asset_id,
                trade_date=(start + timedelta(days=index)).strftime("%Y%m%d"),
                open=close - 0.44,
                high=close + 0.30,
                low=close - 0.70,
                close=close,
                amount=300_000.0,
                volume=100_000.0,
            )
        )
    for index in range(len(bars) - 21, len(bars) - 16):
        bar = bars[index]
        bars[index] = replace(
            bar,
            open=bar.close - 0.4,
            high=bar.close + 0.6,
            low=bar.close - 0.8,
        )
    return tuple(bars)


def _boundary_composite_bars(asset_id: str) -> tuple[KlineBar, ...]:
    start = date(2023, 1, 2)
    base_shadow_share = (0.56 * 60 - 0.60 * 5) / 55
    base_total_shadow = base_shadow_share / (1 - base_shadow_share)
    bars = []
    for index in range(100):
        close = 100.0 + index * 0.12 + math.sin(index * 2 * math.pi / 22)
        open_value = close - 1.0
        upper_shadow = 0.2
        lower_shadow = base_total_shadow - upper_shadow
        bars.append(
            KlineBar(
                asset_id=asset_id,
                trade_date=(start + timedelta(days=index)).strftime("%Y%m%d"),
                open=open_value,
                high=close + upper_shadow,
                low=open_value - lower_shadow,
                close=close,
                amount=300_000.0,
                volume=100_000.0,
            )
        )
    for index in range(len(bars) - 21, len(bars) - 16):
        bar = bars[index]
        bars[index] = replace(
            bar,
            high=bar.close + 1.5,
            low=bar.open,
        )
    return tuple(bars)


def _entry_candidate(
    asset_id: str,
    name: str,
    industry: str,
    deviation: float,
    strong_industry_hit: bool,
    concepts: tuple[str, ...],
) -> SteadyUptrendMvpCandidate:
    stages = {
        stage: StageDecision(True, True)
        for stage in (
            "s1_quality_filter",
            "s2_mature_trend_filter",
            "s3_structure_recall",
            "s4_stability_refinement",
            "s5_entry_selection",
        )
    }
    context = StockSignalContext(
        asset_id=asset_id,
        trade_date="20260710",
        name=name,
        industry=industry,
        market="主板",
        list_status="L",
        total_mv=1_200_000.0,
        avg_amount_20d=300_000.0,
        strong_industry_hit=strong_industry_hit,
        strong_concept_hit=bool(concepts),
        strong_industry_names=(industry,) if strong_industry_hit else (),
        strong_concept_names=concepts,
    )
    return SteadyUptrendMvpCandidate(
        asset_id=asset_id,
        signal_date="20260710",
        context=context,
        stages=stages,
        metrics={
            "close": 100.0 * (1 + deviation),
            "ma20": 100.0,
            "ma20_deviation_pct": deviation,
            "ma20_deviation_level": ma20_deviation_level(deviation),
        },
        matched_structures=("s3_c_steady_ma",),
    )


def _with_close(bar: KlineBar, close: float) -> KlineBar:
    return replace(
        bar,
        open=close,
        high=close + 0.2,
        low=close - 0.2,
        close=close,
    )


if __name__ == "__main__":
    unittest.main()
