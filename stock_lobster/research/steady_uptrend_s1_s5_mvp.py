"""Deterministic S1-S5 MVP evaluation for mature steady uptrends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from stock_lobster.research.trend_breakout_scan import KlineBar, StockSignalContext


@dataclass(frozen=True, slots=True)
class SteadyUptrendMvpPolicy:
    """Approved thresholds for the first S1-S5 candidate version."""

    min_total_mv: float = 1_000_000.0
    min_avg_amount_20d: float = 200_000.0
    min_return_60d: float = 0.05
    min_ma60_hold_ratio_60d: float = 0.50
    max_abs_drawdown_60d: float = 0.50
    max_abs_weekly_drawdown_26w: float = 0.50
    min_close_to_high_60d_pct: float = -0.10
    min_upper_shadow_ratio: float = 0.60
    min_upper_shadow_days_20d: int = 5
    min_avg_total_shadow_share_60d: float = 0.56
    min_ma_alignment_transitions_60d: int = 5
    min_red_k_ratio_60d: float = 0.45
    min_extreme_bearish_drop: float = 0.07
    min_extreme_bearish_days_10d: int = 3


@dataclass(frozen=True, slots=True)
class StageDecision:
    """Pass/fail evidence for one business stage."""

    evaluated: bool
    passed: bool
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SteadyUptrendMvpCandidate:
    """Full deterministic decision for one stock and signal date."""

    asset_id: str
    signal_date: str
    context: StockSignalContext | None
    stages: Mapping[str, StageDecision]
    metrics: Mapping[str, float | int | bool | None] = field(default_factory=dict)
    matched_structures: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StructureRecallDecision:
    """White-box S3 branch matches and their computed evidence."""

    matched_structures: tuple[str, ...]
    metrics: Mapping[str, float | int | bool | None]


@dataclass(frozen=True, slots=True)
class StabilityRefinementDecision:
    """White-box S4 hard-risk blockers and computed evidence."""

    passed: bool
    blockers: tuple[str, ...]
    metrics: Mapping[str, float | int | bool | None]


_STAGE_NAMES = (
    "s1_quality_filter",
    "s2_mature_trend_filter",
    "s3_structure_recall",
    "s4_stability_refinement",
    "s5_entry_selection",
)


def evaluate_steady_uptrend_mvp(
    daily_bars: Iterable[KlineBar],
    weekly_bars: Iterable[KlineBar],
    context: StockSignalContext | None,
    *,
    signal_date: str,
    policy: SteadyUptrendMvpPolicy | None = None,
) -> SteadyUptrendMvpCandidate:
    """Evaluate the approved business stages without authoring market facts."""

    active_policy = policy or SteadyUptrendMvpPolicy()
    daily_input = tuple(daily_bars)
    weekly_input = tuple(weekly_bars)
    asset_id = context.asset_id if context is not None else _first_asset_id(daily_input)
    daily = _asof_asset_bars(daily_input, asset_id, signal_date)
    weekly = _asof_asset_bars(weekly_input, asset_id, signal_date)
    stages = {name: StageDecision(False, False) for name in _STAGE_NAMES}

    s1_blockers = _s1_blockers(daily, weekly, context, signal_date, active_policy)
    stages["s1_quality_filter"] = StageDecision(True, not s1_blockers, s1_blockers)
    if s1_blockers:
        return SteadyUptrendMvpCandidate(asset_id, signal_date, context, stages)

    metrics = _mature_trend_metrics(daily, weekly)
    s2_blockers = _s2_blockers(metrics, active_policy)
    stages["s2_mature_trend_filter"] = StageDecision(True, not s2_blockers, s2_blockers)
    if s2_blockers:
        return SteadyUptrendMvpCandidate(asset_id, signal_date, context, stages, metrics)

    structure = evaluate_structure_recall(
        daily,
        signal_date=signal_date,
        policy=active_policy,
    )
    metrics.update(structure.metrics)
    s3_blockers = () if structure.matched_structures else ("no_structure_recalled",)
    stages["s3_structure_recall"] = StageDecision(True, not s3_blockers, s3_blockers)
    if s3_blockers:
        return SteadyUptrendMvpCandidate(
            asset_id,
            signal_date,
            context,
            stages,
            metrics,
            structure.matched_structures,
        )

    stability = evaluate_stability_refinement(
        daily,
        signal_date=signal_date,
        policy=active_policy,
    )
    metrics.update(stability.metrics)
    stages["s4_stability_refinement"] = StageDecision(
        True,
        stability.passed,
        stability.blockers,
    )
    return SteadyUptrendMvpCandidate(
        asset_id,
        signal_date,
        context,
        stages,
        metrics,
        structure.matched_structures,
    )


def evaluate_stability_refinement(
    daily_bars: Iterable[KlineBar],
    *,
    signal_date: str,
    policy: SteadyUptrendMvpPolicy | None = None,
) -> StabilityRefinementDecision:
    """Evaluate S4 against complete trading days before the signal date."""

    active_policy = policy or SteadyUptrendMvpPolicy()
    materialized = tuple(daily_bars)
    asset_id = _first_asset_id(materialized)
    bars = _asof_asset_bars(materialized, asset_id, signal_date)
    if len(bars) < 81 or bars[-1].trade_date != signal_date:
        return StabilityRefinementDecision(
            False,
            ("stability_data_unavailable",),
            {"stability_data_available": False},
        )

    previous_20 = bars[-21:-1]
    previous_60 = bars[-61:-1]
    upper_shadow_days = sum(
        _upper_shadow_ratio(bar) >= active_policy.min_upper_shadow_ratio - 1e-12
        for bar in previous_20
    )
    avg_total_shadow_share = sum(_total_shadow_share(bar) for bar in previous_60) / 60

    closes = [bar.close for bar in bars]
    ma5 = _moving_average_series(closes, 5)
    ma10 = _moving_average_series(closes, 10)
    ma20 = _moving_average_series(closes, 20)
    start = len(bars) - 61
    states = [
        ma5[index] is not None
        and ma10[index] is not None
        and ma20[index] is not None
        and ma5[index] >= ma10[index] >= ma20[index]
        for index in range(start, len(bars) - 1)
    ]
    transitions = sum(left != right for left, right in zip(states, states[1:]))
    red_k_ratio = sum(bar.close >= bar.open for bar in previous_60) / 60

    extreme_bearish_days = 0
    for index in range(len(bars) - 11, len(bars) - 1):
        bar = bars[index]
        previous_close = bars[index - 1].close
        if (
            bar.close < bar.open
            and previous_close > 0
            and (previous_close - bar.close) / previous_close
            >= active_policy.min_extreme_bearish_drop - 1e-12
        ):
            extreme_bearish_days += 1

    blockers: list[str] = []
    if (
        upper_shadow_days >= active_policy.min_upper_shadow_days_20d
        and avg_total_shadow_share >= active_policy.min_avg_total_shadow_share_60d
        and transitions >= active_policy.min_ma_alignment_transitions_60d
    ):
        blockers.append("noisy_shadow_ma_flip_composite")
    if red_k_ratio < active_policy.min_red_k_ratio_60d:
        blockers.append("low_red_k_ratio_60d")
    if extreme_bearish_days >= active_policy.min_extreme_bearish_days_10d:
        blockers.append("frequent_extreme_bearish_days_10d")

    metrics: dict[str, float | int | bool | None] = {
        "stability_data_available": True,
        "upper_shadow_days_20d": upper_shadow_days,
        "avg_total_shadow_share_60d": avg_total_shadow_share,
        "ma_alignment_transitions_60d": transitions,
        "red_k_ratio_60d": red_k_ratio,
        "extreme_bearish_days_10d": extreme_bearish_days,
    }
    return StabilityRefinementDecision(not blockers, tuple(blockers), metrics)


def _upper_shadow_ratio(bar: KlineBar) -> float:
    denominator = bar.high - min(bar.open, bar.close)
    if denominator <= 0:
        return 0.0
    return (bar.high - max(bar.open, bar.close)) / denominator


def _total_shadow_share(bar: KlineBar) -> float:
    price_range = bar.high - bar.low
    if price_range <= 0:
        return 0.0
    return (price_range - abs(bar.close - bar.open)) / price_range


def evaluate_structure_recall(
    daily_bars: Iterable[KlineBar],
    *,
    signal_date: str,
    policy: SteadyUptrendMvpPolicy | None = None,
) -> StructureRecallDecision:
    """Evaluate the three approved S3 recall branches for one stock/date."""

    active_policy = policy or SteadyUptrendMvpPolicy()
    materialized = tuple(daily_bars)
    asset_id = _first_asset_id(materialized)
    bars = _asof_asset_bars(materialized, asset_id, signal_date)
    if len(bars) < 81 or bars[-1].trade_date != signal_date:
        return StructureRecallDecision((), {"structure_data_available": False})

    closes = [bar.close for bar in bars]
    ma5 = _moving_average_series(closes, 5)
    ma10 = _moving_average_series(closes, 10)
    ma20 = _moving_average_series(closes, 20)
    ma30 = _moving_average_series(closes, 30)
    ma60 = _moving_average_series(closes, 60)
    high_close_60d = max(closes[-60:])
    close_to_high = closes[-1] / high_close_60d - 1
    matched: list[str] = []
    if close_to_high >= active_policy.min_close_to_high_60d_pct - 1e-12:
        matched.append("s3_a_high_position")

    b_pass, b_metrics = _evaluate_pullback_recovery(
        closes,
        ma5,
        ma10,
        ma20,
        ma30,
        ma60,
    )
    if b_pass:
        matched.append("s3_b_pullback_recovery")

    previous_5d_return = closes[-6] / closes[-11] - 1
    recent_5d_return = closes[-1] / closes[-6] - 1
    wide_swing_rebound = previous_5d_return <= -0.05 and recent_5d_return >= 0.20
    alignment_states = [
        ma5[index] is not None
        and ma10[index] is not None
        and ma20[index] is not None
        and ma5[index] >= ma10[index] >= ma20[index]
        for index in range(len(closes) - 10, len(closes))
    ]
    close_range_10d = max(closes[-10:]) / min(closes[-10:]) - 1
    max_drawdown_10d = _max_drawdown(closes[-10:])
    c_pass = (
        ma5[-1] is not None
        and ma10[-1] is not None
        and ma20[-1] is not None
        and ma60[-1] is not None
        and ma5[-1] >= ma10[-1] >= ma20[-1] > ma60[-1]
        and ma10[-1] > ma10[-11]  # type: ignore[operator]
        and ma20[-1] > ma20[-21]  # type: ignore[operator]
        and closes[-1] / closes[-21] - 1 > 0
        and close_range_10d <= 0.15
        and abs(max_drawdown_10d) <= 0.10
        and sum(alignment_states) >= 7
        and not wide_swing_rebound
    )
    if c_pass:
        matched.append("s3_c_steady_ma")

    metrics: dict[str, float | int | bool | None] = {
        "structure_data_available": True,
        "high_close_60d": high_close_60d,
        "close_to_high_60d_pct": close_to_high,
        "previous_5d_return": previous_5d_return,
        "recent_5d_return": recent_5d_return,
        "wide_swing_rebound": wide_swing_rebound,
        "close_range_10d": close_range_10d,
        "max_drawdown_10d": max_drawdown_10d,
        "ma_alignment_days_10d": sum(alignment_states),
    }
    metrics.update(b_metrics)
    return StructureRecallDecision(tuple(matched), metrics)


def _evaluate_pullback_recovery(
    closes: list[float],
    ma5: list[float | None],
    ma10: list[float | None],
    ma20: list[float | None],
    ma30: list[float | None],
    ma60: list[float | None],
) -> tuple[bool, dict[str, float | int | bool | None]]:
    start = len(closes) - 21
    end = len(closes) - 1
    running_peak = max(closes[max(0, start - 20) : start])
    drawdowns: list[tuple[int, float]] = []
    for index in range(start, end):
        running_peak = max(running_peak, closes[index])
        drawdowns.append((index, closes[index] / running_peak - 1))

    episodes: list[list[tuple[int, float]]] = []
    current: list[tuple[int, float]] = []
    for item in drawdowns:
        if item[1] <= -0.05:
            current.append(item)
        elif current:
            episodes.append(current)
            current = []
    if current:
        episodes.append(current)
    if not episodes:
        return False, {
            "pullback_depth": None,
            "pullback_trough_index": None,
            "pullback_support_pass": False,
            "effective_ma60_breakdown": False,
            "recovery_from_trough": None,
        }

    episode = episodes[-1]
    trough_index, pullback_depth = min(episode, key=lambda item: item[1])
    trough_close = closes[trough_index]
    trough_ma20 = ma20[trough_index]
    trough_ma30 = ma30[trough_index]
    near_ma20 = trough_ma20 is not None and abs(trough_close / trough_ma20 - 1) <= 0.03
    near_ma30 = trough_ma30 is not None and abs(trough_close / trough_ma30 - 1) <= 0.03
    above_ma20 = (
        trough_ma20 is not None and 0 <= trough_close / trough_ma20 - 1 <= 0.15
    )
    support_pass = near_ma20 or near_ma30 or above_ma20

    effective_breakdown = False
    consecutive_below_ma60 = 0
    for index in range(trough_index, len(closes)):
        current_ma60 = ma60[index]
        if current_ma60 is None:
            effective_breakdown = True
            break
        if closes[index] < 0.97 * current_ma60:
            effective_breakdown = True
            break
        if closes[index] < current_ma60:
            consecutive_below_ma60 += 1
            if consecutive_below_ma60 >= 2:
                effective_breakdown = True
                break
        else:
            consecutive_below_ma60 = 0

    recovery = closes[-1] / trough_close - 1
    current_pass = (
        ma20[-1] is not None
        and ma5[-1] is not None
        and ma10[-1] is not None
        and closes[-1] > ma20[-1]
        and ma5[-1] > ma10[-1]
        and closes[-1] / closes[-6] - 1 > 0
        and recovery >= 0.03
    )
    passed = (
        -0.20 <= pullback_depth <= -0.05
        and support_pass
        and not effective_breakdown
        and current_pass
    )
    return passed, {
        "pullback_depth": pullback_depth,
        "pullback_trough_index": trough_index,
        "pullback_support_pass": support_pass,
        "effective_ma60_breakdown": effective_breakdown,
        "recovery_from_trough": recovery,
    }


def _first_asset_id(bars: Iterable[KlineBar]) -> str:
    materialized = tuple(bars)
    return materialized[0].asset_id if materialized else ""


def _asof_asset_bars(
    bars: Iterable[KlineBar],
    asset_id: str,
    signal_date: str,
) -> tuple[KlineBar, ...]:
    return tuple(
        sorted(
            (
                bar
                for bar in bars
                if bar.asset_id == asset_id and bar.trade_date <= signal_date
            ),
            key=lambda item: item.trade_date,
        )
    )


def _s1_blockers(
    daily: tuple[KlineBar, ...],
    weekly: tuple[KlineBar, ...],
    context: StockSignalContext | None,
    signal_date: str,
    policy: SteadyUptrendMvpPolicy,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if (
        context is None
        or context.trade_date != signal_date
        or len(daily) < 120
        or len(weekly) < 64
        or daily[-1].trade_date != signal_date
        or any(not _valid_bar(bar) for bar in daily[-120:])
        or any(not _valid_bar(bar) for bar in weekly[-64:])
    ):
        blockers.append("data_quality_unavailable")
    if context is None or context.list_status.upper() != "L":
        blockers.append("not_normal_listing")
    if context is None or _is_st_name(context.name):
        blockers.append("st_stock")
    if context is None or context.total_mv is None or context.total_mv < policy.min_total_mv:
        blockers.append("market_cap_below_minimum")
    if (
        context is None
        or context.avg_amount_20d is None
        or context.avg_amount_20d < policy.min_avg_amount_20d
    ):
        blockers.append("avg_amount_20d_below_minimum")
    return tuple(blockers)


def _valid_bar(bar: KlineBar) -> bool:
    return (
        bar.open > 0
        and bar.high > 0
        and bar.low > 0
        and bar.close > 0
        and bar.high >= max(bar.open, bar.close, bar.low)
        and bar.low <= min(bar.open, bar.close, bar.high)
    )


def _is_st_name(name: str) -> bool:
    normalized = name.strip().upper()
    return normalized.startswith("ST") or normalized.startswith("*ST")


def _mature_trend_metrics(
    daily: tuple[KlineBar, ...],
    weekly: tuple[KlineBar, ...],
) -> dict[str, float | int | bool | None]:
    daily_closes = [bar.close for bar in daily]
    weekly_closes = [bar.close for bar in weekly]
    daily_ma20 = _moving_average_series(daily_closes, 20)
    daily_ma60 = _moving_average_series(daily_closes, 60)
    weekly_ma10 = _moving_average_series(weekly_closes, 10)
    weekly_ma20 = _moving_average_series(weekly_closes, 20)
    weekly_ma30 = _moving_average_series(weekly_closes, 30)
    weekly_ma60 = _moving_average_series(weekly_closes, 60)

    ma60_hold_count = sum(
        close > ma
        for close, ma in zip(daily_closes[-60:], daily_ma60[-60:])
        if ma is not None
    )
    return {
        "close": daily_closes[-1],
        "ma20": daily_ma20[-1],
        "ma60": daily_ma60[-1],
        "return_60d": daily_closes[-1] / daily_closes[-61] - 1,
        "ma60_hold_days_60d": ma60_hold_count,
        "ma60_hold_ratio_60d": ma60_hold_count / 60,
        "ma60_slope_20d": daily_ma60[-1] / daily_ma60[-21] - 1,  # type: ignore[operator]
        "max_drawdown_60d": _max_drawdown(daily_closes[-60:]),
        "weekly_close": weekly_closes[-1],
        "weekly_ma10": weekly_ma10[-1],
        "weekly_ma20": weekly_ma20[-1],
        "weekly_ma30": weekly_ma30[-1],
        "weekly_ma60": weekly_ma60[-1],
        "weekly_ma20_slope_4w": weekly_ma20[-1] / weekly_ma20[-5] - 1,  # type: ignore[operator]
        "weekly_max_drawdown_26w": _max_drawdown(weekly_closes[-26:]),
    }


def _s2_blockers(
    metrics: Mapping[str, float | int | bool | None],
    policy: SteadyUptrendMvpPolicy,
) -> tuple[str, ...]:
    close = float(metrics["close"] or 0)
    ma20 = float(metrics["ma20"] or 0)
    ma60 = float(metrics["ma60"] or 0)
    daily_pass = (
        close > ma20 > ma60
        and float(metrics["return_60d"] or 0) >= policy.min_return_60d
        and float(metrics["ma60_hold_ratio_60d"] or 0) >= policy.min_ma60_hold_ratio_60d
        and float(metrics["ma60_slope_20d"] or 0) > 0
        and abs(float(metrics["max_drawdown_60d"] or 0)) <= policy.max_abs_drawdown_60d
    )
    weekly_close = float(metrics["weekly_close"] or 0)
    weekly_ma10 = float(metrics["weekly_ma10"] or 0)
    weekly_ma20 = float(metrics["weekly_ma20"] or 0)
    weekly_ma30 = float(metrics["weekly_ma30"] or 0)
    weekly_ma60 = float(metrics["weekly_ma60"] or 0)
    weekly_pass = (
        weekly_close > weekly_ma20
        and weekly_ma10 > weekly_ma20
        and float(metrics["weekly_ma20_slope_4w"] or 0) > 0
        and weekly_ma10 > weekly_ma30 > weekly_ma60
        and abs(float(metrics["weekly_max_drawdown_26w"] or 0))
        <= policy.max_abs_weekly_drawdown_26w
    )
    blockers: list[str] = []
    if not daily_pass:
        blockers.append("daily_mature_trend_failed")
    if not weekly_pass:
        blockers.append("weekly_mature_trend_failed")
    return tuple(blockers)


def _moving_average_series(values: list[float], window: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    rolling_sum = 0.0
    for index, value in enumerate(values):
        rolling_sum += value
        if index >= window:
            rolling_sum -= values[index - window]
        if index >= window - 1:
            result[index] = rolling_sum / window
    return result


def _max_drawdown(values: list[float]) -> float:
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1)
    return max_drawdown
