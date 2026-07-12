"""Deterministic S1-S5 MVP evaluation for mature steady uptrends."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter, defaultdict
from datetime import datetime, timedelta
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
    min_close_to_prior_high_20d_pct: float = -0.05


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
    metrics: Mapping[str, float | int | bool | str | None] = field(default_factory=dict)
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
    if not stability.passed:
        return SteadyUptrendMvpCandidate(
            asset_id,
            signal_date,
            context,
            stages,
            metrics,
            structure.matched_structures,
        )

    s5_blockers: list[str] = []
    if context is None or not (context.strong_industry_hit or context.strong_concept_hit):
        s5_blockers.append("context_strength_unavailable")
    close = float(metrics["close"] or 0)
    ma5 = float(metrics["ma5"] or 0)
    if ma5 <= 0:
        s5_blockers.append("ma5_entry_unavailable")
    elif close <= ma5:
        s5_blockers.append("close_not_above_ma5")
    prior_high_close_20d = float(metrics["prior_high_close_20d"] or 0)
    if prior_high_close_20d <= 0:
        s5_blockers.append("prior_high_close_20d_unavailable")
    elif (
        float(metrics["close_to_prior_high_20d_pct"] or 0)
        < active_policy.min_close_to_prior_high_20d_pct - 1e-12
    ):
        s5_blockers.append("close_too_far_below_prior_high_20d")
    ma20 = float(metrics["ma20"] or 0)
    if ma20 <= 0:
        s5_blockers.append("ma20_deviation_unavailable")
    else:
        deviation = close / ma20 - 1
        metrics["ma20_deviation_pct"] = deviation
        metrics["ma20_deviation_level"] = ma20_deviation_level(deviation)
    stages["s5_entry_selection"] = StageDecision(
        True,
        not s5_blockers,
        tuple(s5_blockers),
    )
    return SteadyUptrendMvpCandidate(
        asset_id,
        signal_date,
        context,
        stages,
        metrics,
        structure.matched_structures,
    )


def ma20_deviation_level(deviation_pct: float) -> str:
    """Map MA20 deviation to the approved non-filtering alert level."""

    if deviation_pct >= 0.50:
        return "50"
    if deviation_pct >= 0.40:
        return "40"
    if deviation_pct >= 0.30:
        return "30"
    if deviation_pct >= 0.20:
        return "20"
    return "normal"


def build_steady_uptrend_mvp_report(
    evaluations: Iterable[SteadyUptrendMvpCandidate],
    *,
    strategy_id: str,
    run_id: str,
    signal_date: str,
    data_dependency_versions: Mapping[str, str],
) -> dict[str, object]:
    """Build deterministic audit output and an industry-grouped Markdown view."""

    items = tuple(sorted(evaluations, key=lambda item: item.asset_id))
    stage_counts = {
        stage: {
            "input": sum(item.stages[stage].evaluated for item in items),
            "passed": sum(item.stages[stage].passed for item in items),
            "rejected": sum(
                item.stages[stage].evaluated and not item.stages[stage].passed
                for item in items
            ),
        }
        for stage in _STAGE_NAMES
    }
    blocker_counts: Counter[str] = Counter()
    evaluation_rows: list[dict[str, object]] = []
    final_rows: list[dict[str, object]] = []
    for item in items:
        blockers = tuple(
            blocker
            for stage in _STAGE_NAMES
            for blocker in item.stages[stage].blockers
        )
        blocker_counts.update(blockers)
        first_blocking_stage = next(
            (
                stage
                for stage in _STAGE_NAMES
                if item.stages[stage].evaluated and not item.stages[stage].passed
            ),
            None,
        )
        row = _candidate_mapping(item, blockers, first_blocking_stage)
        evaluation_rows.append(row)
        if item.stages["s5_entry_selection"].passed:
            final_rows.append(row)

    by_industry: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in final_rows:
        by_industry[str(row["industry"] or "未分类")].append(row)
    industry_groups: list[dict[str, object]] = []
    for industry, stocks in by_industry.items():
        stocks.sort(
            key=lambda row: (
                not bool(row["strong_industry_hit"]),
                float(row["ma20_deviation_pct"]),
                str(row["asset_id"]),
            )
        )
        industry_groups.append(
            {
                "industry": industry,
                "strong_industry_candidate_count": sum(
                    bool(stock["strong_industry_hit"]) for stock in stocks
                ),
                "candidate_count": len(stocks),
                "stocks": stocks,
            }
        )
    industry_groups.sort(
        key=lambda group: (
            -int(group["strong_industry_candidate_count"]),
            -int(group["candidate_count"]),
            str(group["industry"]),
        )
    )
    ordered_final_rows = [
        stock
        for group in industry_groups
        for stock in group["stocks"]  # type: ignore[union-attr]
    ]
    markdown = _render_industry_markdown(industry_groups)
    return {
        "strategy_id": strategy_id,
        "run_id": run_id,
        "signal_date": signal_date,
        "data_dependency_versions": dict(sorted(data_dependency_versions.items())),
        "stage_counts": stage_counts,
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "evaluations": evaluation_rows,
        "candidates": ordered_final_rows,
        "industry_groups": industry_groups,
        "markdown": markdown,
    }


def _candidate_mapping(
    item: SteadyUptrendMvpCandidate,
    blockers: tuple[str, ...],
    first_blocking_stage: str | None,
) -> dict[str, object]:
    context = item.context
    return {
        "trade_date": item.signal_date,
        "asset_id": item.asset_id,
        "name": context.name if context else "",
        "industry": context.industry if context else "",
        "matched_structures": list(item.matched_structures),
        "strong_industry_hit": context.strong_industry_hit if context else False,
        "strong_industry_names": list(context.strong_industry_names) if context else [],
        "strong_concept_hit": context.strong_concept_hit if context else False,
        "strong_concept_names": list(context.strong_concept_names) if context else [],
        "close": item.metrics.get("close"),
        "ma5": item.metrics.get("ma5"),
        "prior_high_close_20d": item.metrics.get("prior_high_close_20d"),
        "close_to_prior_high_20d_pct": item.metrics.get(
            "close_to_prior_high_20d_pct"
        ),
        "return_3d": item.metrics.get("return_3d"),
        "ma20": item.metrics.get("ma20"),
        "ma20_deviation_pct": item.metrics.get("ma20_deviation_pct"),
        "ma20_deviation_level": item.metrics.get("ma20_deviation_level"),
        "s1_pass": item.stages["s1_quality_filter"].passed,
        "s2_pass": item.stages["s2_mature_trend_filter"].passed,
        "s3_pass": item.stages["s3_structure_recall"].passed,
        "s4_pass": item.stages["s4_stability_refinement"].passed,
        "s5_pass": item.stages["s5_entry_selection"].passed,
        "first_blocking_stage": first_blocking_stage,
        "blockers": list(blockers),
        "metrics": dict(item.metrics),
    }


def _render_industry_markdown(industry_groups: list[dict[str, object]]) -> str:
    lines: list[str] = []
    for group in industry_groups:
        lines.append(f"{group['industry']}：")
        for stock in group["stocks"]:  # type: ignore[union-attr]
            deviation = float(stock["ma20_deviation_pct"])
            level = str(stock["ma20_deviation_level"])
            level_text = "正常" if level == "normal" else f"{level} 级"
            concepts = tuple(stock["strong_concept_names"])
            suffix = f"；概念：{'、'.join(concepts)}" if concepts else ""
            lines.append(
                f"{stock['name']}（偏离 {deviation * 100:.1f}%，{level_text}{suffix}）"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + ("\n" if lines else "")


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
    duplicate_daily = _has_duplicate_trade_dates(daily)
    duplicate_weekly = _has_duplicate_trade_dates(weekly)
    if duplicate_daily:
        blockers.append("duplicate_daily_trade_date")
    if duplicate_weekly:
        blockers.append("duplicate_weekly_trade_date")
    if weekly and not _weekly_asof_matches(weekly[-1].trade_date, signal_date):
        blockers.append("weekly_asof_mismatch")
    if (
        context is None
        or context.trade_date != signal_date
        or len(daily) < 120
        or len(weekly) < 64
        or daily[-1].trade_date != signal_date
        or any(not _valid_bar(bar) for bar in daily[-120:])
        or any(not _valid_bar(bar) for bar in weekly[-64:])
        or duplicate_daily
        or duplicate_weekly
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


def _has_duplicate_trade_dates(bars: tuple[KlineBar, ...]) -> bool:
    trade_dates = [bar.trade_date for bar in bars]
    return len(trade_dates) != len(set(trade_dates))


def _weekly_asof_matches(weekly_trade_date: str, signal_date: str) -> bool:
    try:
        signal = datetime.strptime(signal_date, "%Y%m%d").date()
        weekly = datetime.strptime(weekly_trade_date, "%Y%m%d").date()
    except ValueError:
        return False
    if signal.weekday() == 4:
        return weekly == signal
    expected_previous_week = (signal - timedelta(days=7)).isocalendar()[:2]
    return weekly.isocalendar()[:2] == expected_previous_week


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
    daily_ma5 = _moving_average_series(daily_closes, 5)
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
    prior_high_close_20d = max(daily_closes[-21:-1])
    return {
        "close": daily_closes[-1],
        "ma5": daily_ma5[-1],
        "prior_high_close_20d": prior_high_close_20d,
        "close_to_prior_high_20d_pct": (
            daily_closes[-1] / prior_high_close_20d - 1
        ),
        "return_3d": daily_closes[-1] / daily_closes[-4] - 1,
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
