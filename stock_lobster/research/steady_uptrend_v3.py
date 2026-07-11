"""Research-only v3 filters for steady uptrend breakout candidates."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping

from stock_lobster.research.trend_breakout_scan import KlineBar, TrendBreakoutMetrics


@dataclass(frozen=True, slots=True)
class MarketTemperature:
    """Aggregate market context for one trade date."""

    trade_date: str
    sample_size: int
    breadth_ma20: float
    breadth_ma60: float
    avg_return_20d: float
    avg_amount_ratio: float

    def to_mapping(self) -> dict[str, object]:
        """Render this temperature snapshot as a JSON-friendly mapping."""

        return {
            "trade_date": self.trade_date,
            "sample_size": self.sample_size,
            "breadth_ma20": self.breadth_ma20,
            "breadth_ma60": self.breadth_ma60,
            "avg_return_20d": self.avg_return_20d,
            "avg_amount_ratio": self.avg_amount_ratio,
        }


@dataclass(frozen=True, slots=True)
class SteadyUptrendV3Policy:
    """Explicit thresholds for the research-only v3 candidate filter."""

    require_market_temperature: bool = True
    max_market_breadth_ma20: float | None = 0.55
    max_market_avg_return_20d: float | None = 0.03
    max_market_avg_amount_ratio: float | None = None
    min_market_temperature_sample_size: int = 100
    min_red_k_ratio_20d: float | None = None
    min_amount_ratio_20d: float | None = None
    max_amount_ratio_20d: float | None = None
    min_close_to_high_60d_pct: float = -0.06
    max_close_to_high_60d_pct: float = -0.02
    max_ma30_deviation_pct: float | None = None
    max_single_bull_bar_return_share_20d: float | None = None
    top_n_per_date: int | None = 20
    cooldown_trade_days: int = 10
    blocked_context_names: tuple[str, ...] = ()
    post_rank_no_refill_rejection_reasons: tuple[str, ...] = ()
    fading_concept_names: tuple[str, ...] = ("算力租赁", "数据中心", "储能", "华为概念")
    preferred_rotation_concept_names: tuple[str, ...] = ("PCB概念", "存储芯片", "先进封装", "光纤概念")
    ignored_context_names: tuple[str, ...] = (
        "中证500成份股",
        "上证180成份股",
        "上证380成份股",
        "上证50样本股",
    )

    def to_mapping(self) -> dict[str, object]:
        """Render this policy as a JSON-friendly mapping."""

        return {
            "require_market_temperature": self.require_market_temperature,
            "max_market_breadth_ma20": self.max_market_breadth_ma20,
            "max_market_avg_return_20d": self.max_market_avg_return_20d,
            "max_market_avg_amount_ratio": self.max_market_avg_amount_ratio,
            "min_market_temperature_sample_size": self.min_market_temperature_sample_size,
            "min_red_k_ratio_20d": self.min_red_k_ratio_20d,
            "min_amount_ratio_20d": self.min_amount_ratio_20d,
            "max_amount_ratio_20d": self.max_amount_ratio_20d,
            "min_close_to_high_60d_pct": self.min_close_to_high_60d_pct,
            "max_close_to_high_60d_pct": self.max_close_to_high_60d_pct,
            "max_ma30_deviation_pct": self.max_ma30_deviation_pct,
            "max_single_bull_bar_return_share_20d": self.max_single_bull_bar_return_share_20d,
            "top_n_per_date": self.top_n_per_date,
            "cooldown_trade_days": self.cooldown_trade_days,
            "blocked_context_names": list(self.blocked_context_names),
            "post_rank_no_refill_rejection_reasons": list(self.post_rank_no_refill_rejection_reasons),
            "fading_concept_names": list(self.fading_concept_names),
            "preferred_rotation_concept_names": list(self.preferred_rotation_concept_names),
            "ignored_context_names": list(self.ignored_context_names),
        }


def build_market_temperatures(
    bars: Iterable[KlineBar],
    *,
    start_date: str | None = None,
) -> dict[str, MarketTemperature]:
    """Build deterministic market-temperature snapshots from consumed kline bars."""

    by_asset: dict[str, list[KlineBar]] = defaultdict(list)
    for bar in bars:
        by_asset[bar.asset_id].append(bar)

    rows_by_date: dict[str, list[tuple[bool, bool, float, float]]] = defaultdict(list)
    for asset_bars in by_asset.values():
        sorted_bars = sorted(asset_bars, key=lambda item: item.trade_date)
        closes = [bar.close for bar in sorted_bars]
        amounts = [bar.amount for bar in sorted_bars]
        ma20_values = _moving_average_series(closes, 20)
        ma60_values = _moving_average_series(closes, 60)
        amount_ma20_values = _moving_average_series(amounts, 20)
        for index, bar in enumerate(sorted_bars):
            if start_date is not None and bar.trade_date < start_date:
                continue
            ma20 = ma20_values[index]
            ma60 = ma60_values[index]
            amount_ma20 = amount_ma20_values[index]
            if ma20 is None or ma60 is None or amount_ma20 is None or amount_ma20 == 0:
                continue
            if index < 20 or closes[index - 20] <= 0:
                continue
            return_20d = bar.close / closes[index - 20] - 1
            amount_ratio = bar.amount / amount_ma20
            rows_by_date[bar.trade_date].append(
                (
                    bar.close > ma20,
                    bar.close > ma60,
                    return_20d,
                    amount_ratio,
                )
            )

    temperatures: dict[str, MarketTemperature] = {}
    for trade_date in sorted(rows_by_date):
        rows = rows_by_date[trade_date]
        sample_size = len(rows)
        if sample_size == 0:
            continue
        temperatures[trade_date] = MarketTemperature(
            trade_date=trade_date,
            sample_size=sample_size,
            breadth_ma20=sum(1 for row in rows if row[0]) / sample_size,
            breadth_ma60=sum(1 for row in rows if row[1]) / sample_size,
            avg_return_20d=sum(row[2] for row in rows) / sample_size,
            avg_amount_ratio=sum(row[3] for row in rows) / sample_size,
        )
    return temperatures


def v3_rejection_reasons(
    metric: TrendBreakoutMetrics,
    *,
    market_temperature: MarketTemperature | None,
    policy: SteadyUptrendV3Policy,
) -> tuple[str, ...]:
    """Return explicit v3 rejection reasons for one candidate metric."""

    reasons: list[str] = []
    if not metric.daily_quality_pass:
        reasons.append("daily_quality_failed")
    if not metric.steady_uptrend:
        reasons.append("steady_uptrend_failed")
    if not metric.weak_shape_pass:
        reasons.append("weak_shape_failed")
    if not metric.context_strength_pass:
        reasons.append("context_strength_failed")

    reasons.extend(_market_temperature_reasons(market_temperature, policy))

    if policy.min_red_k_ratio_20d is not None and metric.red_k_ratio_20d < policy.min_red_k_ratio_20d:
        reasons.append("red_k_ratio_below_v3_threshold")
    if policy.min_amount_ratio_20d is not None and metric.amount_ratio_20d < policy.min_amount_ratio_20d:
        reasons.append("amount_ratio_below_v3_threshold")
    if policy.max_amount_ratio_20d is not None and metric.amount_ratio_20d >= policy.max_amount_ratio_20d:
        reasons.append("amount_ratio_overheated")
    if policy.max_ma30_deviation_pct is not None and metric.ma30_deviation_pct > policy.max_ma30_deviation_pct:
        reasons.append("ma30_deviation_overheated")
    if (
        policy.max_single_bull_bar_return_share_20d is not None
        and metric.single_bull_bar_return_share_20d > policy.max_single_bull_bar_return_share_20d
    ):
        reasons.append("single_bull_bar_dominance_failed")
    if metric.pre_breakout_watch and not metric.breakout_watch:
        if metric.close_to_high_60d_pct < policy.min_close_to_high_60d_pct:
            reasons.append("pre_breakout_too_far_from_high")
        if metric.close_to_high_60d_pct > policy.max_close_to_high_60d_pct:
            reasons.append("pre_breakout_too_close_to_high")

    context_names = _context_names(metric, policy)
    blocked_names = set(policy.blocked_context_names)
    if any(name in blocked_names for name in context_names):
        reasons.append("blocked_risk_context")
    fading_names = set(policy.fading_concept_names)
    preferred_names = set(policy.preferred_rotation_concept_names)
    has_fading = any(name in fading_names for name in context_names)
    has_preferred = any(name in preferred_names for name in context_names)
    if has_fading and not has_preferred:
        reasons.append("fading_context_without_preferred_rotation")
    return tuple(dict.fromkeys(reasons))


def v3_score(
    metric: TrendBreakoutMetrics,
    *,
    market_temperature: MarketTemperature | None,
    policy: SteadyUptrendV3Policy,
) -> float:
    """Score candidates after hard v3 eligibility checks."""

    score = float(metric.setup_score)
    context_names = _context_names(metric, policy)
    if any(name in policy.preferred_rotation_concept_names for name in context_names):
        score += 10.0
    if any(name in policy.fading_concept_names for name in context_names):
        score -= 6.0
    score -= max(metric.amount_ratio_20d - 1.6, 0.0) * 3.0
    score -= max(metric.ma30_deviation_pct - 0.18, 0.0) * 25.0
    score -= max(metric.single_bull_bar_return_share_20d - 0.18, 0.0) * 40.0
    if market_temperature is not None:
        score -= max(market_temperature.breadth_ma20 - 0.35, 0.0) * 10.0
        score -= max(market_temperature.avg_return_20d - 0.015, 0.0) * 80.0
    return round(score, 6)


def select_v3_observation_candidates(
    metrics: Iterable[TrendBreakoutMetrics],
    *,
    market_temperatures: Mapping[str, MarketTemperature],
    policy: SteadyUptrendV3Policy,
    trade_date_order: Iterable[str] | None = None,
) -> tuple[TrendBreakoutMetrics, ...]:
    """Select pre-breakout observation candidates using v3 research rules."""

    candidates = (
        item
        for item in metrics
        if item.pre_breakout_watch
        and not _pre_rank_rejection_reasons(
            item,
            market_temperature=market_temperatures.get(item.trade_date),
            policy=policy,
        )
    )
    return _rank_with_limits(
        candidates,
        market_temperatures=market_temperatures,
        policy=policy,
        trade_date_order=trade_date_order,
    )


def select_v3_signal_candidates(
    metrics: Iterable[TrendBreakoutMetrics],
    *,
    market_temperatures: Mapping[str, MarketTemperature],
    policy: SteadyUptrendV3Policy,
    trade_date_order: Iterable[str] | None = None,
) -> tuple[TrendBreakoutMetrics, ...]:
    """Select breakout signal candidates using v3 research rules."""

    candidates = (
        item
        for item in metrics
        if item.breakout_watch
        and not _pre_rank_rejection_reasons(
            item,
            market_temperature=market_temperatures.get(item.trade_date),
            policy=policy,
        )
    )
    return _rank_with_limits(
        candidates,
        market_temperatures=market_temperatures,
        policy=policy,
        trade_date_order=trade_date_order,
    )


def summarize_v3_rejections(
    metrics: Iterable[TrendBreakoutMetrics],
    *,
    market_temperatures: Mapping[str, MarketTemperature],
    policy: SteadyUptrendV3Policy,
) -> dict[str, int]:
    """Summarize rejection reason counts for refined base candidates."""

    counts: dict[str, int] = defaultdict(int)
    for metric in metrics:
        if not (metric.pre_breakout_watch or metric.breakout_watch):
            continue
        for reason in v3_rejection_reasons(
            metric,
            market_temperature=market_temperatures.get(metric.trade_date),
            policy=policy,
        ):
            counts[reason] += 1
    return dict(sorted(counts.items()))


def _market_temperature_reasons(
    market_temperature: MarketTemperature | None,
    policy: SteadyUptrendV3Policy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if market_temperature is None:
        if policy.require_market_temperature:
            return ("market_temperature_missing",)
        return ()
    overheated = False
    if market_temperature.sample_size < policy.min_market_temperature_sample_size:
        reasons.append("market_temperature_sample_too_small")
    if (
        policy.max_market_breadth_ma20 is not None
        and market_temperature.breadth_ma20 > policy.max_market_breadth_ma20
    ):
        reasons.append("market_breadth_ma20_overheated")
        overheated = True
    if (
        policy.max_market_avg_return_20d is not None
        and market_temperature.avg_return_20d > policy.max_market_avg_return_20d
    ):
        reasons.append("market_avg_return_20d_overheated")
        overheated = True
    if (
        policy.max_market_avg_amount_ratio is not None
        and market_temperature.avg_amount_ratio > policy.max_market_avg_amount_ratio
    ):
        reasons.append("market_amount_ratio_overheated")
        overheated = True
    if overheated:
        reasons.insert(0, "market_temperature_overheated")
    return tuple(reasons)


def _rank_with_limits(
    candidates: Iterable[TrendBreakoutMetrics],
    *,
    market_temperatures: Mapping[str, MarketTemperature],
    policy: SteadyUptrendV3Policy,
    trade_date_order: Iterable[str] | None,
) -> tuple[TrendBreakoutMetrics, ...]:
    by_date: dict[str, list[TrendBreakoutMetrics]] = defaultdict(list)
    for candidate in candidates:
        by_date[candidate.trade_date].append(candidate)

    date_order = _date_order(by_date.keys(), trade_date_order)
    date_index = {trade_date: index for index, trade_date in enumerate(date_order)}
    selected: list[TrendBreakoutMetrics] = []
    last_selected_index_by_asset: dict[str, int] = {}
    for trade_date in date_order:
        date_candidates = sorted(
            by_date.get(trade_date, ()),
            key=lambda item: (
                -v3_score(
                    item,
                    market_temperature=market_temperatures.get(item.trade_date),
                    policy=policy,
                ),
                -item.setup_score,
                item.asset_id,
            ),
        )
        considered_on_date = 0
        for candidate in date_candidates:
            current_index = date_index[candidate.trade_date]
            last_index = last_selected_index_by_asset.get(candidate.asset_id)
            if (
                last_index is not None
                and policy.cooldown_trade_days > 0
                and current_index - last_index <= policy.cooldown_trade_days
            ):
                continue
            considered_on_date += 1
            if _has_post_rank_no_refill_rejection(
                candidate,
                market_temperature=market_temperatures.get(candidate.trade_date),
                policy=policy,
            ):
                if policy.top_n_per_date is not None and considered_on_date >= policy.top_n_per_date:
                    break
                continue
            selected.append(candidate)
            last_selected_index_by_asset[candidate.asset_id] = current_index
            if policy.top_n_per_date is not None and considered_on_date >= policy.top_n_per_date:
                break
    return tuple(selected)


def _pre_rank_rejection_reasons(
    metric: TrendBreakoutMetrics,
    *,
    market_temperature: MarketTemperature | None,
    policy: SteadyUptrendV3Policy,
) -> tuple[str, ...]:
    post_rank_reasons = set(policy.post_rank_no_refill_rejection_reasons)
    return tuple(
        reason
        for reason in v3_rejection_reasons(
            metric,
            market_temperature=market_temperature,
            policy=policy,
        )
        if reason not in post_rank_reasons
    )


def _has_post_rank_no_refill_rejection(
    metric: TrendBreakoutMetrics,
    *,
    market_temperature: MarketTemperature | None,
    policy: SteadyUptrendV3Policy,
) -> bool:
    post_rank_reasons = set(policy.post_rank_no_refill_rejection_reasons)
    if not post_rank_reasons:
        return False
    return any(
        reason in post_rank_reasons
        for reason in v3_rejection_reasons(
            metric,
            market_temperature=market_temperature,
            policy=policy,
        )
    )


def _date_order(
    candidate_dates: Iterable[str],
    trade_date_order: Iterable[str] | None,
) -> tuple[str, ...]:
    dates = set(candidate_dates)
    if trade_date_order is None:
        return tuple(sorted(dates))
    ordered = [trade_date for trade_date in trade_date_order if trade_date in dates]
    remaining = sorted(dates.difference(ordered))
    return tuple(ordered + remaining)


def _context_names(
    metric: TrendBreakoutMetrics,
    policy: SteadyUptrendV3Policy,
) -> tuple[str, ...]:
    ignored = set(policy.ignored_context_names)
    names = []
    for name in (*metric.strong_industry_names, *metric.strong_concept_names):
        normalized = name.strip()
        if normalized and normalized not in ignored:
            names.append(normalized)
    return tuple(dict.fromkeys(names))


def _moving_average_series(values: list[float], window: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    rolling_sum = 0.0
    for index, value in enumerate(values):
        rolling_sum += value
        if index >= window:
            rolling_sum -= values[index - window]
        if index + 1 >= window:
            result[index] = rolling_sum / window
    return result
