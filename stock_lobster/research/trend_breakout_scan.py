"""Deterministic scanner for steady uptrend breakout research samples."""

from __future__ import annotations

from bisect import bisect_right
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from stock_lobster.technical_indicators import moving_average_at, rolling_max_drawdown_at


@dataclass(frozen=True, slots=True)
class KlineBar:
    """Daily OHLCV bar used by research scanners."""

    asset_id: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    amount: float
    volume: float | None = None


@dataclass(frozen=True, slots=True)
class AdjFactor:
    """Daily adjustment factor for qfq/hfq price transformations."""

    asset_id: str
    trade_date: str
    adj_factor: float


@dataclass(frozen=True, slots=True)
class TrendBreakoutMetrics:
    """Window metrics for one stock/date."""

    asset_id: str
    trade_date: str
    close: float
    ma5: float
    ma10: float
    ma20: float
    ma30: float
    ma60: float
    ma120: float
    ma20_slope_20d: float
    amount_ratio_20d: float
    max_drawdown_60d: float
    max_drawdown_120d: float
    convergence_5_10_20_pct: float
    close_to_high_60d_pct: float
    ma20_deviation_pct: float
    ma30_deviation_pct: float
    ma30_hold_ratio_30d: float
    ma30_hold_ratio_60d: float
    ma30_hold_ratio_90d: float
    ma30_hold_ratio_120d: float
    ma60_hold_ratio_120d: float
    return_20d: float
    red_k_ratio_20d: float
    green_k_ratio_20d: float
    long_shadow_ratio_20d: float
    avg_amount_20d: float
    close_new_high_60d_flag: bool
    daily_quality_pass: bool
    trend_stability_pass: bool
    market_cap_liquidity_pass: bool
    turnover_quality_pass: bool
    context_strength_pass: bool
    steady_uptrend: bool
    pre_breakout_watch: bool
    breakout_watch: bool
    setup_score: float
    amount_ratio_prev_20d: float = 0.0
    large_bearish_body_ratio_20d: float = 0.0
    max_consecutive_green_k_20d: int = 0
    single_bull_bar_return_share_20d: float = 0.0
    impulse_consolidation_days: int = 0
    ma5_10_20_30_convergence_pct: float = 0.0
    weak_shape_pass: bool = True
    name: str = ""
    industry: str = ""
    market: str = ""
    list_status: str = ""
    total_mv: float | None = None
    turnover_rate: float | None = None
    max_turnover_rate_20d: float | None = None
    avg_turnover_rate_20d: float | None = None
    turnover_spike_ratio_20d: float | None = None
    strong_industry_hit: bool = False
    strong_concept_hit: bool = False
    strong_industry_names: tuple[str, ...] = ()
    strong_concept_names: tuple[str, ...] = ()
    quality_failure_reasons: tuple[str, ...] = ()
    weekly_asof_trade_date: str | None = None
    weekly_close: float | None = None
    weekly_ma5: float | None = None
    weekly_ma10: float | None = None
    weekly_ma20: float | None = None
    weekly_ma20_slope_4w: float | None = None
    weekly_max_drawdown_26w: float | None = None
    weekly_trend_pass: bool = True
    volume_ratio_5d_20d: float | None = None
    turnover_ratio_5d_20d: float | None = None
    adj_factor_changed_20d: bool = False
    post_impulse_followthrough_return: float | None = None
    volume_decay_after_impulse: float | None = None
    high_volume_bearish_close: bool = False
    price_volume_efficiency_5d: float | None = None

    def to_mapping(self) -> dict[str, object]:
        """Render this metrics object as a JSON-friendly mapping."""

        return {
            "asset_id": self.asset_id,
            "trade_date": self.trade_date,
            "name": self.name,
            "industry": self.industry,
            "market": self.market,
            "list_status": self.list_status,
            "close": self.close,
            "ma5": self.ma5,
            "ma10": self.ma10,
            "ma20": self.ma20,
            "ma30": self.ma30,
            "ma60": self.ma60,
            "ma120": self.ma120,
            "ma20_slope_20d": self.ma20_slope_20d,
            "amount_ratio_20d": self.amount_ratio_20d,
            "amount_ratio_prev_20d": self.amount_ratio_prev_20d,
            "volume_ratio_5d_20d": self.volume_ratio_5d_20d,
            "turnover_ratio_5d_20d": self.turnover_ratio_5d_20d,
            "adj_factor_changed_20d": self.adj_factor_changed_20d,
            "post_impulse_followthrough_return": self.post_impulse_followthrough_return,
            "volume_decay_after_impulse": self.volume_decay_after_impulse,
            "high_volume_bearish_close": self.high_volume_bearish_close,
            "price_volume_efficiency_5d": self.price_volume_efficiency_5d,
            "max_drawdown_60d": self.max_drawdown_60d,
            "max_drawdown_120d": self.max_drawdown_120d,
            "convergence_5_10_20_pct": self.convergence_5_10_20_pct,
            "close_to_high_60d_pct": self.close_to_high_60d_pct,
            "ma20_deviation_pct": self.ma20_deviation_pct,
            "ma30_deviation_pct": self.ma30_deviation_pct,
            "ma30_hold_ratio_30d": self.ma30_hold_ratio_30d,
            "ma30_hold_ratio_60d": self.ma30_hold_ratio_60d,
            "ma30_hold_ratio_90d": self.ma30_hold_ratio_90d,
            "ma30_hold_ratio_120d": self.ma30_hold_ratio_120d,
            "ma60_hold_ratio_120d": self.ma60_hold_ratio_120d,
            "return_20d": self.return_20d,
            "red_k_ratio_20d": self.red_k_ratio_20d,
            "green_k_ratio_20d": self.green_k_ratio_20d,
            "long_shadow_ratio_20d": self.long_shadow_ratio_20d,
            "large_bearish_body_ratio_20d": self.large_bearish_body_ratio_20d,
            "max_consecutive_green_k_20d": self.max_consecutive_green_k_20d,
            "single_bull_bar_return_share_20d": self.single_bull_bar_return_share_20d,
            "impulse_consolidation_days": self.impulse_consolidation_days,
            "ma5_10_20_30_convergence_pct": self.ma5_10_20_30_convergence_pct,
            "avg_amount_20d": self.avg_amount_20d,
            "total_mv": self.total_mv,
            "turnover_rate": self.turnover_rate,
            "max_turnover_rate_20d": self.max_turnover_rate_20d,
            "avg_turnover_rate_20d": self.avg_turnover_rate_20d,
            "turnover_spike_ratio_20d": self.turnover_spike_ratio_20d,
            "close_new_high_60d_flag": self.close_new_high_60d_flag,
            "daily_quality_pass": self.daily_quality_pass,
            "trend_stability_pass": self.trend_stability_pass,
            "weak_shape_pass": self.weak_shape_pass,
            "market_cap_liquidity_pass": self.market_cap_liquidity_pass,
            "turnover_quality_pass": self.turnover_quality_pass,
            "context_strength_pass": self.context_strength_pass,
            "strong_industry_hit": self.strong_industry_hit,
            "strong_concept_hit": self.strong_concept_hit,
            "strong_industry_names": list(self.strong_industry_names),
            "strong_concept_names": list(self.strong_concept_names),
            "quality_failure_reasons": list(self.quality_failure_reasons),
            "weekly_asof_trade_date": self.weekly_asof_trade_date,
            "weekly_close": self.weekly_close,
            "weekly_ma5": self.weekly_ma5,
            "weekly_ma10": self.weekly_ma10,
            "weekly_ma20": self.weekly_ma20,
            "weekly_ma20_slope_4w": self.weekly_ma20_slope_4w,
            "weekly_max_drawdown_26w": self.weekly_max_drawdown_26w,
            "weekly_trend_pass": self.weekly_trend_pass,
            "steady_uptrend": self.steady_uptrend,
            "pre_breakout_watch": self.pre_breakout_watch,
            "breakout_watch": self.breakout_watch,
            "setup_score": self.setup_score,
        }


@dataclass(frozen=True, slots=True)
class TrendBreakoutScanPolicy:
    """Thresholds for the steady uptrend breakout candidate scanner."""

    min_volume_ratio_5d_20d: float = 1.2
    max_abs_drawdown_60d: float = 0.40
    max_abs_drawdown_120d: float = 0.55
    min_red_k_ratio_20d: float = 0.45
    max_long_shadow_ratio_20d: float = 0.65
    require_close_above_ma30: bool = True
    require_weekly_uptrend: bool = False
    max_abs_weekly_drawdown_26w: float = 0.55
    max_weekly_ma20_deviation_pct: float | None = None
    min_close_to_high_60d_pct: float = -0.08
    max_close_to_high_60d_pct: float = -0.002
    max_ma20_deviation_pct: float = 0.35
    max_ma30_deviation_pct: float = 0.35
    min_sustained_ma30_hold_ratio_90d: float = 0.75
    min_recent_ma30_hold_ratio_30d: float = 0.75
    min_recent_ma30_hold_ratio_60d: float = 0.55
    min_base_breakout_ma30_hold_ratio_60d: float = 0.50
    min_base_breakout_return_20d: float = 0.20
    require_pre_breakout_sustained_ma30: bool = True
    require_normal_listing: bool = False
    min_total_mv: float | None = None
    min_avg_amount_20d: float | None = None
    max_turnover_rate_20d: float | None = None
    max_turnover_spike_ratio_20d: float | None = None
    require_context_strength: bool = False
    max_convergence_5_10_20_pct: float | None = None
    enable_weak_shape_filter: bool = False
    min_large_bearish_body_pct: float = 0.025
    max_large_bearish_body_ratio_20d: float | None = None
    max_consecutive_green_k_20d: int | None = None
    max_single_bull_bar_return_share_20d: float | None = None
    min_impulse_consolidation_days: int | None = None
    min_ma5_10_20_30_convergence_pct: float | None = None
    start_date: str | None = None


@dataclass(frozen=True, slots=True)
class StockSignalContext:
    """External stock/date context consumed by the research scanner."""

    asset_id: str
    trade_date: str
    name: str = ""
    industry: str = ""
    market: str = ""
    list_status: str = ""
    total_mv: float | None = None
    turnover_rate: float | None = None
    max_turnover_rate_20d: float | None = None
    avg_turnover_rate_20d: float | None = None
    avg_amount_20d: float | None = None
    strong_industry_hit: bool = False
    strong_concept_hit: bool = False
    strong_industry_names: tuple[str, ...] = ()
    strong_concept_names: tuple[str, ...] = ()
    volume_ratio_5d_20d: float | None = None
    max_volume_ratio_5d_20d: float | None = None
    turnover_ratio_5d_20d: float | None = None
    adj_factor_changed_20d: bool = False


@dataclass(frozen=True, slots=True)
class WeeklyTrendContext:
    """Weekly trend context aligned to one daily signal date."""

    asof_trade_date: str
    close: float
    ma5: float
    ma10: float
    ma20: float
    ma20_slope_4w: float
    max_drawdown_26w: float
    trend_pass: bool


def read_kline_tsv(path: str | Path) -> tuple[KlineBar, ...]:
    """Read mysql `-B -N` style kline output."""

    bars: list[KlineBar] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        values = line.split("\t")
        if len(values) not in {7, 8}:
            raise ValueError(f"kline TSV row must have 7 or 8 columns, got {len(values)}")
        asset_id, trade_date, open_value, high, low, close, amount = values[:7]
        volume = values[7] if len(values) == 8 else None
        bars.append(
            KlineBar(
                asset_id=asset_id,
                trade_date=trade_date,
                open=float(open_value),
                high=float(high),
                low=float(low),
                close=float(close),
                amount=float(amount),
                volume=_optional_float(volume),
            )
        )
    return tuple(bars)


def adjust_bars_to_qfq_asof(
    bars: Iterable[KlineBar],
    factors: Iterable[AdjFactor],
    *,
    anchor_trade_date: str,
) -> tuple[KlineBar, ...]:
    """Return bars with OHLC adjusted to the anchor date's qfq price basis."""

    factor_by_key = {(factor.asset_id, factor.trade_date): factor.adj_factor for factor in factors}
    anchor_by_asset = {
        factor.asset_id: factor.adj_factor for factor in factors if factor.trade_date == anchor_trade_date
    }
    adjusted: list[KlineBar] = []
    missing: list[str] = []
    for bar in bars:
        bar_factor = factor_by_key.get((bar.asset_id, bar.trade_date))
        anchor_factor = anchor_by_asset.get(bar.asset_id)
        if bar_factor is None or anchor_factor in (None, 0):
            missing.append(f"{bar.asset_id}.{bar.trade_date}")
            continue
        ratio = bar_factor / anchor_factor
        adjusted.append(
            KlineBar(
                asset_id=bar.asset_id,
                trade_date=bar.trade_date,
                open=bar.open * ratio,
                high=bar.high * ratio,
                low=bar.low * ratio,
                close=bar.close * ratio,
                amount=bar.amount,
                volume=bar.volume,
            )
        )
    if missing:
        preview = ", ".join(missing[:5])
        raise ValueError(f"missing adj_factor for qfq_asof adjustment: {preview}")
    return tuple(adjusted)


def read_stock_signal_context_tsv(path: str | Path) -> tuple[StockSignalContext, ...]:
    """Read optional stock/date context exported from the factual data layer."""

    rows = Path(path).read_text(encoding="utf-8").splitlines()
    if not rows:
        return ()
    default_columns = (
        "asset_id",
        "trade_date",
        "name",
        "industry",
        "market",
        "list_status",
        "total_mv",
        "turnover_rate",
        "max_turnover_rate_20d",
        "avg_turnover_rate_20d",
        "avg_amount_20d",
        "strong_industry_hit",
        "strong_concept_hit",
        "strong_industry_names",
        "strong_concept_names",
        "volume_ratio_5d_20d",
        "max_volume_ratio_5d_20d",
        "turnover_ratio_5d_20d",
        "adj_factor_changed_20d",
    )
    has_header = rows[0].split("\t")[0] in {"asset_id", "ts_code"}
    if has_header:
        reader = csv.DictReader(rows, delimiter="\t")
    else:
        reader = csv.DictReader(rows, delimiter="\t", fieldnames=default_columns)

    contexts: list[StockSignalContext] = []
    for row in reader:
        asset_id = row.get("asset_id") or row.get("ts_code") or ""
        trade_date = row.get("trade_date") or ""
        if not asset_id or not trade_date:
            continue
        contexts.append(
            StockSignalContext(
                asset_id=asset_id,
                trade_date=trade_date,
                name=row.get("name", "") or "",
                industry=row.get("industry", "") or "",
                market=row.get("market", "") or "",
                list_status=row.get("list_status", "") or "",
                total_mv=_optional_float(row.get("total_mv")),
                turnover_rate=_optional_float(row.get("turnover_rate")),
                max_turnover_rate_20d=_optional_float(row.get("max_turnover_rate_20d")),
                avg_turnover_rate_20d=_optional_float(row.get("avg_turnover_rate_20d")),
                avg_amount_20d=_optional_float(row.get("avg_amount_20d")),
                strong_industry_hit=_truthy(row.get("strong_industry_hit")),
                strong_concept_hit=_truthy(row.get("strong_concept_hit")),
                strong_industry_names=_split_names(row.get("strong_industry_names")),
                strong_concept_names=_split_names(row.get("strong_concept_names")),
                volume_ratio_5d_20d=_optional_float(row.get("volume_ratio_5d_20d")),
                max_volume_ratio_5d_20d=_optional_float(row.get("max_volume_ratio_5d_20d")),
                turnover_ratio_5d_20d=_optional_float(row.get("turnover_ratio_5d_20d")),
                adj_factor_changed_20d=_truthy(row.get("adj_factor_changed_20d")),
            )
        )
    return tuple(contexts)


def scan_trend_breakouts(
    bars: Iterable[KlineBar],
    policy: TrendBreakoutScanPolicy | None = None,
    weekly_bars: Iterable[KlineBar] | None = None,
    stock_contexts: Iterable[StockSignalContext] | Mapping[tuple[str, str], StockSignalContext] | None = None,
) -> tuple[TrendBreakoutMetrics, ...]:
    """Scan kline bars and return deterministic trend-breakout metrics."""

    active_policy = policy or TrendBreakoutScanPolicy()
    weekly_contexts = _build_weekly_contexts(weekly_bars or (), active_policy)
    stock_context_map = _context_mapping(stock_contexts)
    by_asset: dict[str, list[KlineBar]] = defaultdict(list)
    for bar in bars:
        by_asset[bar.asset_id].append(bar)

    results: list[TrendBreakoutMetrics] = []
    for asset_id in sorted(by_asset):
        asset_bars = sorted(by_asset[asset_id], key=lambda bar: bar.trade_date)
        closes = [bar.close for bar in asset_bars]
        amounts = [bar.amount for bar in asset_bars]
        moving_averages = {
            5: _moving_average_series(closes, 5),
            10: _moving_average_series(closes, 10),
            20: _moving_average_series(closes, 20),
            30: _moving_average_series(closes, 30),
            60: _moving_average_series(closes, 60),
            120: _moving_average_series(closes, 120),
        }
        average_amount_20d = _moving_average_series(amounts, 20)
        for index, bar in enumerate(asset_bars):
            if active_policy.start_date is not None and bar.trade_date < active_policy.start_date:
                continue
            metrics = _metrics_for_index(
                bars=asset_bars,
                closes=closes,
                amounts=amounts,
                moving_averages=moving_averages,
                average_amount_20d=average_amount_20d,
                index=index,
                policy=active_policy,
                weekly_contexts=weekly_contexts.get(asset_id, ()),
                stock_context=stock_context_map.get((bar.asset_id, bar.trade_date)),
            )
            if metrics is not None:
                results.append(metrics)
    return tuple(results)


def summarize_breakout_scan(
    metrics: Iterable[TrendBreakoutMetrics],
) -> dict[str, object]:
    """Summarize scanner output by stock."""

    summary: dict[str, dict[str, object]] = {}
    for item in metrics:
        stock_summary = summary.setdefault(
            item.asset_id,
            {
                "steady_uptrend_count": 0,
                "pre_breakout_watch_count": 0,
                "breakout_watch_count": 0,
                "first_breakout_watch_date": None,
                "latest_breakout_watch_date": None,
            },
        )
        if item.steady_uptrend:
            stock_summary["steady_uptrend_count"] = int(stock_summary["steady_uptrend_count"]) + 1
        if item.pre_breakout_watch:
            stock_summary["pre_breakout_watch_count"] = int(stock_summary["pre_breakout_watch_count"]) + 1
        if item.breakout_watch:
            stock_summary["breakout_watch_count"] = int(stock_summary["breakout_watch_count"]) + 1
            if stock_summary["first_breakout_watch_date"] is None:
                stock_summary["first_breakout_watch_date"] = item.trade_date
            stock_summary["latest_breakout_watch_date"] = item.trade_date
    return summary


def _metrics_for_index(
    bars: list[KlineBar],
    closes: list[float],
    amounts: list[float],
    moving_averages: Mapping[int, list[float | None]],
    average_amount_20d: list[float | None],
    index: int,
    policy: TrendBreakoutScanPolicy,
    weekly_contexts: tuple[WeeklyTrendContext, ...],
    stock_context: StockSignalContext | None,
) -> TrendBreakoutMetrics | None:
    ma5 = moving_averages[5][index]
    ma10 = moving_averages[10][index]
    ma20 = moving_averages[20][index]
    ma30 = moving_averages[30][index]
    ma60 = moving_averages[60][index]
    ma120 = moving_averages[120][index]
    if None in (ma5, ma10, ma20, ma30, ma60, ma120):
        return None
    previous_ma20 = moving_averages[20][index - 20] if index >= 20 else None
    max_drawdown_60d = _max_drawdown(closes, index, 60)
    max_drawdown_120d = _max_drawdown(closes, index, 120)
    if previous_ma20 is None or max_drawdown_60d is None or max_drawdown_120d is None:
        return None

    bar = bars[index]
    amount_average_20d = average_amount_20d[index]
    if amount_average_20d is None or amount_average_20d == 0:
        return None

    ma20_slope_20d = ma20 / previous_ma20 - 1
    amount_ratio_20d = bar.amount / amount_average_20d
    previous_amount_average_20d = sum(amounts[index - 20 : index]) / 20
    if previous_amount_average_20d == 0:
        return None
    amount_ratio_prev_20d = bar.amount / previous_amount_average_20d
    convergence_5_10_20_pct = (max(ma5, ma10, ma20) - min(ma5, ma10, ma20)) / bar.close
    high_60d = max(closes[index - 59 : index + 1])
    close_to_high_60d_pct = bar.close / high_60d - 1
    ma20_deviation_pct = bar.close / ma20 - 1
    ma30_deviation_pct = bar.close / ma30 - 1
    ma30_hold_ratio_30d = _close_above_ma_ratio(closes, moving_averages[30], index, 30)
    ma30_hold_ratio_60d = _close_above_ma_ratio(closes, moving_averages[30], index, 60)
    ma30_hold_ratio_90d = _close_above_ma_ratio(closes, moving_averages[30], index, 90)
    ma30_hold_ratio_120d = _close_above_ma_ratio(closes, moving_averages[30], index, 120)
    ma60_hold_ratio_120d = _close_above_ma_ratio(closes, moving_averages[60], index, 120)
    return_20d = bar.close / closes[index - 20] - 1
    red_k_ratio_20d = _red_k_ratio(bars, index, 20)
    green_k_ratio_20d = 1 - red_k_ratio_20d
    long_shadow_ratio_20d = _long_shadow_ratio(bars, index, 20)
    large_bearish_body_ratio_20d = _large_bearish_body_ratio(
        bars=bars,
        index=index,
        window=20,
        min_body_pct=policy.min_large_bearish_body_pct,
    )
    max_consecutive_green_k_20d = _max_consecutive_green_k(bars, index, 20)
    single_bull_bar_return_share_20d = _single_bull_bar_return_share(closes, index, 20)
    impulse_consolidation_days = _impulse_consolidation_days(closes, index, 20)
    ma5_10_20_30_convergence_pct = (max(ma5, ma10, ma20, ma30) - min(ma5, ma10, ma20, ma30)) / bar.close
    close_new_high_60d_flag = bar.close >= high_60d
    weekly_context = _weekly_context_asof(weekly_contexts, bar.trade_date)
    weekly_trend_pass = _weekly_trend_pass(weekly_context, policy)
    trend_stability_pass = _trend_stability_pass(
        close_new_high_60d_flag=close_new_high_60d_flag,
        ma30_deviation_pct=ma30_deviation_pct,
        ma30_hold_ratio_30d=ma30_hold_ratio_30d,
        ma30_hold_ratio_60d=ma30_hold_ratio_60d,
        ma30_hold_ratio_90d=ma30_hold_ratio_90d,
        return_20d=return_20d,
        policy=policy,
    )
    pre_breakout_sustained_pass = (
        not policy.require_pre_breakout_sustained_ma30
        or ma30_hold_ratio_90d >= policy.min_sustained_ma30_hold_ratio_90d
    )
    market_cap_liquidity_pass = _market_cap_liquidity_pass(
        context=stock_context,
        amount_average_20d=amount_average_20d,
        policy=policy,
    )
    turnover_quality_pass = _turnover_quality_pass(stock_context, policy)
    context_strength_pass = _context_strength_pass(stock_context, policy)
    weak_shape_failure_reasons = _weak_shape_failure_reasons(
        large_bearish_body_ratio_20d=large_bearish_body_ratio_20d,
        max_consecutive_green_k_20d=max_consecutive_green_k_20d,
        single_bull_bar_return_share_20d=single_bull_bar_return_share_20d,
        impulse_consolidation_days=impulse_consolidation_days,
        ma5_10_20_30_convergence_pct=ma5_10_20_30_convergence_pct,
        policy=policy,
    )
    weak_shape_pass = not policy.enable_weak_shape_filter or not weak_shape_failure_reasons
    quality_failure_reasons = _quality_failure_reasons(
        context=stock_context,
        amount_average_20d=amount_average_20d,
        trend_stability_pass=trend_stability_pass,
        pre_breakout_sustained_pass=pre_breakout_sustained_pass,
        weak_shape_failure_reasons=weak_shape_failure_reasons if policy.enable_weak_shape_filter else (),
        market_cap_liquidity_pass=market_cap_liquidity_pass,
        turnover_quality_pass=turnover_quality_pass,
        context_strength_pass=context_strength_pass,
        policy=policy,
    )
    close_above_ma30 = (not policy.require_close_above_ma30) or bar.close > ma30
    daily_quality_pass = (
        close_above_ma30
        and red_k_ratio_20d >= policy.min_red_k_ratio_20d
        and abs(max_drawdown_120d) <= policy.max_abs_drawdown_120d
        and long_shadow_ratio_20d <= policy.max_long_shadow_ratio_20d
        and trend_stability_pass
        and weak_shape_pass
        and market_cap_liquidity_pass
        and turnover_quality_pass
        and context_strength_pass
    )
    steady_uptrend = (
        bar.close > ma20
        and bar.close > ma60
        and ma20 > ma60
        and ma60 > ma120
        and ma20_slope_20d > 0
        and abs(max_drawdown_60d) <= policy.max_abs_drawdown_60d
        and daily_quality_pass
        and weekly_trend_pass
    )
    convergence_ok = (
        policy.max_convergence_5_10_20_pct is None
        or convergence_5_10_20_pct <= policy.max_convergence_5_10_20_pct
    )
    volume_ratio_5d_20d = stock_context.volume_ratio_5d_20d if stock_context else None
    turnover_ratio_5d_20d = stock_context.turnover_ratio_5d_20d if stock_context else None
    adj_factor_changed_20d = stock_context.adj_factor_changed_20d if stock_context else False
    effective_activity_ratio = (
        turnover_ratio_5d_20d if adj_factor_changed_20d else volume_ratio_5d_20d
    )
    (
        post_impulse_followthrough_return,
        volume_decay_after_impulse,
    ) = _post_impulse_activity(bars, closes, index, 5)
    high_volume_bearish_close = _high_volume_bearish_close(bars, index, 20)
    price_volume_efficiency_5d = _price_volume_efficiency(
        closes,
        index,
        effective_activity_ratio,
    )
    volume_ratio_pass = (
        volume_ratio_5d_20d is not None
        and volume_ratio_5d_20d >= policy.min_volume_ratio_5d_20d
    )
    breakout_watch = (
        steady_uptrend
        and close_new_high_60d_flag
        and volume_ratio_pass
        and convergence_ok
    )
    pre_breakout_watch = (
        steady_uptrend
        and not close_new_high_60d_flag
        and pre_breakout_sustained_pass
        and policy.min_close_to_high_60d_pct <= close_to_high_60d_pct <= policy.max_close_to_high_60d_pct
        and volume_ratio_pass
        and ma20_deviation_pct <= policy.max_ma20_deviation_pct
        and ma30_deviation_pct <= policy.max_ma30_deviation_pct
    )
    setup_score = _setup_score(
        red_k_ratio_20d=red_k_ratio_20d,
        long_shadow_ratio_20d=long_shadow_ratio_20d,
        max_drawdown_60d=max_drawdown_60d,
        amount_ratio_20d=amount_ratio_20d,
        close_to_high_60d_pct=close_to_high_60d_pct,
        ma20_deviation_pct=ma20_deviation_pct,
        breakout_watch=breakout_watch,
        pre_breakout_watch=pre_breakout_watch,
    )

    return TrendBreakoutMetrics(
        asset_id=bar.asset_id,
        trade_date=bar.trade_date,
        close=bar.close,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        ma30=ma30,
        ma60=ma60,
        ma120=ma120,
        ma20_slope_20d=ma20_slope_20d,
        amount_ratio_20d=amount_ratio_20d,
        amount_ratio_prev_20d=amount_ratio_prev_20d,
        max_drawdown_60d=max_drawdown_60d,
        max_drawdown_120d=max_drawdown_120d,
        convergence_5_10_20_pct=convergence_5_10_20_pct,
        close_to_high_60d_pct=close_to_high_60d_pct,
        ma20_deviation_pct=ma20_deviation_pct,
        ma30_deviation_pct=ma30_deviation_pct,
        ma30_hold_ratio_30d=ma30_hold_ratio_30d,
        ma30_hold_ratio_60d=ma30_hold_ratio_60d,
        ma30_hold_ratio_90d=ma30_hold_ratio_90d,
        ma30_hold_ratio_120d=ma30_hold_ratio_120d,
        ma60_hold_ratio_120d=ma60_hold_ratio_120d,
        return_20d=return_20d,
        red_k_ratio_20d=red_k_ratio_20d,
        green_k_ratio_20d=green_k_ratio_20d,
        long_shadow_ratio_20d=long_shadow_ratio_20d,
        large_bearish_body_ratio_20d=large_bearish_body_ratio_20d,
        max_consecutive_green_k_20d=max_consecutive_green_k_20d,
        single_bull_bar_return_share_20d=single_bull_bar_return_share_20d,
        impulse_consolidation_days=impulse_consolidation_days,
        ma5_10_20_30_convergence_pct=ma5_10_20_30_convergence_pct,
        avg_amount_20d=amount_average_20d,
        close_new_high_60d_flag=close_new_high_60d_flag,
        daily_quality_pass=daily_quality_pass,
        trend_stability_pass=trend_stability_pass,
        weak_shape_pass=weak_shape_pass,
        market_cap_liquidity_pass=market_cap_liquidity_pass,
        turnover_quality_pass=turnover_quality_pass,
        context_strength_pass=context_strength_pass,
        weekly_asof_trade_date=weekly_context.asof_trade_date if weekly_context else None,
        weekly_close=weekly_context.close if weekly_context else None,
        weekly_ma5=weekly_context.ma5 if weekly_context else None,
        weekly_ma10=weekly_context.ma10 if weekly_context else None,
        weekly_ma20=weekly_context.ma20 if weekly_context else None,
        weekly_ma20_slope_4w=weekly_context.ma20_slope_4w if weekly_context else None,
        weekly_max_drawdown_26w=weekly_context.max_drawdown_26w if weekly_context else None,
        weekly_trend_pass=weekly_trend_pass,
        volume_ratio_5d_20d=volume_ratio_5d_20d,
        turnover_ratio_5d_20d=turnover_ratio_5d_20d,
        adj_factor_changed_20d=adj_factor_changed_20d,
        post_impulse_followthrough_return=post_impulse_followthrough_return,
        volume_decay_after_impulse=volume_decay_after_impulse,
        high_volume_bearish_close=high_volume_bearish_close,
        price_volume_efficiency_5d=price_volume_efficiency_5d,
        steady_uptrend=steady_uptrend,
        pre_breakout_watch=pre_breakout_watch,
        breakout_watch=breakout_watch,
        setup_score=setup_score,
        name=stock_context.name if stock_context else "",
        industry=stock_context.industry if stock_context else "",
        market=stock_context.market if stock_context else "",
        list_status=stock_context.list_status if stock_context else "",
        total_mv=stock_context.total_mv if stock_context else None,
        turnover_rate=stock_context.turnover_rate if stock_context else None,
        max_turnover_rate_20d=stock_context.max_turnover_rate_20d if stock_context else None,
        avg_turnover_rate_20d=stock_context.avg_turnover_rate_20d if stock_context else None,
        turnover_spike_ratio_20d=_turnover_spike_ratio(stock_context),
        strong_industry_hit=stock_context.strong_industry_hit if stock_context else False,
        strong_concept_hit=stock_context.strong_concept_hit if stock_context else False,
        strong_industry_names=stock_context.strong_industry_names if stock_context else (),
        strong_concept_names=stock_context.strong_concept_names if stock_context else (),
        quality_failure_reasons=quality_failure_reasons,
    )


def select_candidates(
    metrics: Iterable[TrendBreakoutMetrics],
    mode: str = "breakout",
    top_n_per_date: int | None = None,
) -> tuple[TrendBreakoutMetrics, ...]:
    """Select scan candidates by mode and optional daily Top N ranking."""

    if mode not in {"breakout", "pre_breakout", "all"}:
        raise ValueError(f"unsupported candidate mode: {mode}")
    if mode == "breakout":
        candidates = [item for item in metrics if item.breakout_watch]
    elif mode == "pre_breakout":
        candidates = [item for item in metrics if item.pre_breakout_watch]
    else:
        candidates = [item for item in metrics if item.breakout_watch or item.pre_breakout_watch]
    if top_n_per_date is None:
        candidates.sort(key=lambda item: (item.trade_date, item.asset_id))
        return tuple(candidates)
    candidates.sort(key=lambda item: (item.trade_date, -item.setup_score, item.asset_id))
    by_date: dict[str, list[TrendBreakoutMetrics]] = defaultdict(list)
    for candidate in candidates:
        by_date[candidate.trade_date].append(candidate)
    selected: list[TrendBreakoutMetrics] = []
    for trade_date in sorted(by_date):
        selected.extend(by_date[trade_date][:top_n_per_date])
    return tuple(selected)


def _build_weekly_contexts(
    bars: Iterable[KlineBar],
    policy: TrendBreakoutScanPolicy,
) -> dict[str, tuple[WeeklyTrendContext, ...]]:
    by_asset: dict[str, list[KlineBar]] = defaultdict(list)
    for bar in bars:
        by_asset[bar.asset_id].append(bar)

    contexts_by_asset: dict[str, tuple[WeeklyTrendContext, ...]] = {}
    for asset_id, asset_bars in by_asset.items():
        sorted_bars = sorted(asset_bars, key=lambda bar: bar.trade_date)
        closes = [bar.close for bar in sorted_bars]
        contexts: list[WeeklyTrendContext] = []
        for index, bar in enumerate(sorted_bars):
            ma5 = _ma(closes, 5, index)
            ma10 = _ma(closes, 10, index)
            ma20 = _ma(closes, 20, index)
            previous_ma20 = _ma(closes, 20, index - 4) if index >= 4 else None
            max_drawdown_26w = _max_drawdown(closes, index, 26)
            if None in (ma5, ma10, ma20, previous_ma20, max_drawdown_26w):
                continue
            ma20_slope_4w = ma20 / previous_ma20 - 1
            ma20_deviation_ok = (
                policy.max_weekly_ma20_deviation_pct is None
                or bar.close / ma20 - 1 <= policy.max_weekly_ma20_deviation_pct
            )
            trend_pass = (
                bar.close > ma20
                and ma10 > ma20
                and ma20_slope_4w > 0
                and abs(max_drawdown_26w) <= policy.max_abs_weekly_drawdown_26w
                and ma20_deviation_ok
            )
            contexts.append(
                WeeklyTrendContext(
                    asof_trade_date=bar.trade_date,
                    close=bar.close,
                    ma5=ma5,
                    ma10=ma10,
                    ma20=ma20,
                    ma20_slope_4w=ma20_slope_4w,
                    max_drawdown_26w=max_drawdown_26w,
                    trend_pass=trend_pass,
                )
            )
        contexts_by_asset[asset_id] = tuple(contexts)
    return contexts_by_asset


def _weekly_context_asof(
    contexts: tuple[WeeklyTrendContext, ...],
    trade_date: str,
) -> WeeklyTrendContext | None:
    if not contexts:
        return None
    dates = [context.asof_trade_date for context in contexts]
    index = bisect_right(dates, trade_date) - 1
    if index < 0:
        return None
    return contexts[index]


def _weekly_trend_pass(
    context: WeeklyTrendContext | None,
    policy: TrendBreakoutScanPolicy,
) -> bool:
    if context is None:
        return not policy.require_weekly_uptrend
    return context.trend_pass


def _trend_stability_pass(
    *,
    close_new_high_60d_flag: bool,
    ma30_deviation_pct: float,
    ma30_hold_ratio_30d: float,
    ma30_hold_ratio_60d: float,
    ma30_hold_ratio_90d: float,
    return_20d: float,
    policy: TrendBreakoutScanPolicy,
) -> bool:
    if ma30_deviation_pct > policy.max_ma30_deviation_pct:
        return False
    sustained = ma30_hold_ratio_90d >= policy.min_sustained_ma30_hold_ratio_90d
    recent_repair = (
        ma30_hold_ratio_30d >= policy.min_recent_ma30_hold_ratio_30d
        and ma30_hold_ratio_60d >= policy.min_recent_ma30_hold_ratio_60d
    )
    base_breakout = (
        close_new_high_60d_flag
        and ma30_hold_ratio_60d >= policy.min_base_breakout_ma30_hold_ratio_60d
        and return_20d >= policy.min_base_breakout_return_20d
    )
    return sustained or recent_repair or base_breakout


def _market_cap_liquidity_pass(
    *,
    context: StockSignalContext | None,
    amount_average_20d: float,
    policy: TrendBreakoutScanPolicy,
) -> bool:
    if policy.require_normal_listing:
        if context is None:
            return False
        if context.list_status and context.list_status != "L":
            return False
        if "ST" in context.name.upper():
            return False
    if policy.min_total_mv is not None:
        if context is None or context.total_mv is None or context.total_mv < policy.min_total_mv:
            return False
    if policy.min_avg_amount_20d is not None and amount_average_20d < policy.min_avg_amount_20d:
        return False
    return True


def _turnover_quality_pass(context: StockSignalContext | None, policy: TrendBreakoutScanPolicy) -> bool:
    if policy.max_turnover_rate_20d is not None:
        if context is None or context.max_turnover_rate_20d is None:
            return False
        if context.max_turnover_rate_20d > policy.max_turnover_rate_20d:
            return False
    if policy.max_turnover_spike_ratio_20d is not None:
        spike_ratio = _turnover_spike_ratio(context)
        if spike_ratio is None or spike_ratio > policy.max_turnover_spike_ratio_20d:
            return False
    return True


def _context_strength_pass(context: StockSignalContext | None, policy: TrendBreakoutScanPolicy) -> bool:
    if not policy.require_context_strength:
        return True
    if context is None:
        return False
    return context.strong_industry_hit or context.strong_concept_hit


def _quality_failure_reasons(
    *,
    context: StockSignalContext | None,
    amount_average_20d: float,
    trend_stability_pass: bool,
    pre_breakout_sustained_pass: bool,
    weak_shape_failure_reasons: tuple[str, ...],
    market_cap_liquidity_pass: bool,
    turnover_quality_pass: bool,
    context_strength_pass: bool,
    policy: TrendBreakoutScanPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not trend_stability_pass:
        reasons.append("trend_stability_failed")
    if not pre_breakout_sustained_pass:
        reasons.append("pre_breakout_ma30_sustained_failed")
    reasons.extend(weak_shape_failure_reasons)
    if not market_cap_liquidity_pass:
        if policy.require_normal_listing and context is not None and "ST" in context.name.upper():
            reasons.append("st_or_abnormal_listing")
        elif policy.min_total_mv is not None and (context is None or context.total_mv is None or context.total_mv < policy.min_total_mv):
            reasons.append("total_mv_below_threshold")
        elif policy.min_avg_amount_20d is not None and amount_average_20d < policy.min_avg_amount_20d:
            reasons.append("avg_amount_20d_below_threshold")
        else:
            reasons.append("market_cap_liquidity_failed")
    if not turnover_quality_pass:
        reasons.append("turnover_quality_failed")
    if not context_strength_pass:
        reasons.append("industry_concept_strength_failed")
    return tuple(reasons)


def _turnover_spike_ratio(context: StockSignalContext | None) -> float | None:
    if context is None or context.turnover_rate is None or context.avg_turnover_rate_20d in (None, 0):
        return None
    return context.turnover_rate / context.avg_turnover_rate_20d


def _weak_shape_failure_reasons(
    *,
    large_bearish_body_ratio_20d: float,
    max_consecutive_green_k_20d: int,
    single_bull_bar_return_share_20d: float,
    impulse_consolidation_days: int,
    ma5_10_20_30_convergence_pct: float,
    policy: TrendBreakoutScanPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if (
        policy.max_large_bearish_body_ratio_20d is not None
        and large_bearish_body_ratio_20d > policy.max_large_bearish_body_ratio_20d
    ):
        reasons.append("large_bearish_body_ratio_failed")
    if (
        policy.max_consecutive_green_k_20d is not None
        and max_consecutive_green_k_20d > policy.max_consecutive_green_k_20d
    ):
        reasons.append("consecutive_green_k_failed")
    if (
        policy.max_single_bull_bar_return_share_20d is not None
        and single_bull_bar_return_share_20d > policy.max_single_bull_bar_return_share_20d
    ):
        reasons.append("single_bull_bar_dominance_failed")
    if (
        policy.min_impulse_consolidation_days is not None
        and impulse_consolidation_days < policy.min_impulse_consolidation_days
    ):
        reasons.append("impulse_consolidation_days_failed")
    if (
        policy.min_ma5_10_20_30_convergence_pct is not None
        and ma5_10_20_30_convergence_pct < policy.min_ma5_10_20_30_convergence_pct
    ):
        reasons.append("ma5_10_20_30_convergence_failed")
    return tuple(reasons)


def _setup_score(
    red_k_ratio_20d: float,
    long_shadow_ratio_20d: float,
    max_drawdown_60d: float,
    amount_ratio_20d: float,
    close_to_high_60d_pct: float,
    ma20_deviation_pct: float,
    breakout_watch: bool,
    pre_breakout_watch: bool,
) -> float:
    if not breakout_watch and not pre_breakout_watch:
        return 0.0
    red_score = min(max(red_k_ratio_20d, 0.0), 1.0) * 25
    shadow_score = (1 - min(max(long_shadow_ratio_20d, 0.0), 1.0)) * 20
    drawdown_score = (1 - min(abs(max_drawdown_60d) / 0.40, 1.0)) * 20
    volume_score = min(amount_ratio_20d / 2.5, 1.0) * 15
    high_distance_score = (1 - min(abs(close_to_high_60d_pct) / 0.08, 1.0)) * 15
    deviation_penalty = min(max(ma20_deviation_pct - 0.20, 0.0) / 0.30, 1.0) * 10
    mode_bonus = 5 if pre_breakout_watch else 2
    return round(red_score + shadow_score + drawdown_score + volume_score + high_distance_score + mode_bonus - deviation_penalty, 6)


def _ma(values: list[float], window: int, index: int) -> float | None:
    return moving_average_at(values, window, index)


def _max_drawdown(values: list[float], index: int, window: int) -> float | None:
    return rolling_max_drawdown_at(values, window, index)


def _red_k_ratio(bars: list[KlineBar], index: int, window: int) -> float:
    window_bars = bars[index - window + 1 : index + 1]
    red_count = sum(1 for bar in window_bars if bar.close >= bar.open)
    return red_count / len(window_bars)


def _long_shadow_ratio(bars: list[KlineBar], index: int, window: int) -> float:
    ratios: list[float] = []
    for bar in bars[index - window + 1 : index + 1]:
        candle_range = bar.high - bar.low
        if candle_range <= 0:
            ratios.append(0.0)
            continue
        body = abs(bar.close - bar.open)
        shadow = max(candle_range - body, 0.0)
        ratios.append(shadow / candle_range)
    return sum(ratios) / len(ratios)


def _large_bearish_body_ratio(
    *,
    bars: list[KlineBar],
    index: int,
    window: int,
    min_body_pct: float,
) -> float:
    window_bars = bars[index - window + 1 : index + 1]
    large_green_count = sum(
        1
        for bar in window_bars
        if bar.close < bar.open and bar.open > 0 and (bar.open - bar.close) / bar.open >= min_body_pct
    )
    return large_green_count / len(window_bars)


def _max_consecutive_green_k(bars: list[KlineBar], index: int, window: int) -> int:
    current = 0
    longest = 0
    for bar in bars[index - window + 1 : index + 1]:
        if bar.close < bar.open:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _single_bull_bar_return_share(closes: list[float], index: int, window: int) -> float:
    start = max(1, index - window + 1)
    positive_returns = [
        closes[current_index] / closes[current_index - 1] - 1
        for current_index in range(start, index + 1)
        if closes[current_index - 1] > 0 and closes[current_index] > closes[current_index - 1]
    ]
    total_positive_return = sum(positive_returns)
    if total_positive_return <= 0:
        return 0.0
    return max(positive_returns) / total_positive_return


def _impulse_consolidation_days(closes: list[float], index: int, window: int) -> int:
    start = max(1, index - window + 1)
    best_index = start
    best_return = float("-inf")
    for current_index in range(start, index + 1):
        if closes[current_index - 1] <= 0:
            continue
        current_return = closes[current_index] / closes[current_index - 1] - 1
        if current_return > best_return:
            best_return = current_return
            best_index = current_index
    return index - best_index


def _post_impulse_activity(
    bars: list[KlineBar],
    closes: list[float],
    index: int,
    window: int,
) -> tuple[float | None, float | None]:
    start = max(1, index - window + 1)
    impulse_index = max(
        range(start, index + 1),
        key=lambda current_index: closes[current_index] / closes[current_index - 1] - 1,
    )
    if impulse_index == index or closes[impulse_index] == 0:
        return None, None

    followthrough_return = closes[index] / closes[impulse_index] - 1
    impulse_volume = bars[impulse_index].volume
    followthrough_volumes = [
        bar.volume for bar in bars[impulse_index + 1 : index + 1]
    ]
    if (
        impulse_volume is None
        or impulse_volume <= 0
        or not followthrough_volumes
        or any(volume is None for volume in followthrough_volumes)
    ):
        return followthrough_return, None
    volume_decay = sum(float(volume) for volume in followthrough_volumes) / (
        len(followthrough_volumes) * impulse_volume
    )
    return followthrough_return, volume_decay


def _high_volume_bearish_close(
    bars: list[KlineBar],
    index: int,
    window: int,
) -> bool:
    window_bars = bars[index - window + 1 : index + 1]
    volumes = [bar.volume for bar in window_bars]
    if len(window_bars) < window or any(volume is None for volume in volumes):
        return False
    average_volume = sum(float(volume) for volume in volumes) / window
    current = bars[index]
    return (
        average_volume > 0
        and current.volume is not None
        and current.volume / average_volume >= 1.5
        and current.close < current.open
    )


def _price_volume_efficiency(
    closes: list[float],
    index: int,
    effective_activity_ratio: float | None,
) -> float | None:
    if index < 5 or closes[index - 5] == 0:
        return None
    if effective_activity_ratio is None or effective_activity_ratio <= 0:
        return None
    return (closes[index] / closes[index - 5] - 1) / effective_activity_ratio


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


def _close_above_ma_ratio(
    closes: list[float],
    ma_values: list[float | None],
    index: int,
    window: int,
) -> float:
    start = index - window + 1
    if start < 0:
        return 0.0
    valid = 0
    passed = 0
    for current_index in range(start, index + 1):
        ma_value = ma_values[current_index]
        if ma_value is None:
            continue
        valid += 1
        if closes[current_index] > ma_value:
            passed += 1
    if valid == 0:
        return 0.0
    return passed / valid


def _context_mapping(
    contexts: Iterable[StockSignalContext] | Mapping[tuple[str, str], StockSignalContext] | None,
) -> Mapping[tuple[str, str], StockSignalContext]:
    if contexts is None:
        return {}
    if isinstance(contexts, Mapping):
        return contexts
    return {(context.asset_id, context.trade_date): context for context in contexts}


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() == "NULL":
        return None
    return float(text)


def _truthy(value: object) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    if text in {"true", "yes", "y"}:
        return True
    try:
        return float(text) != 0
    except ValueError:
        return False


def _split_names(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    text = str(value).strip()
    if not text or text.upper() == "NULL":
        return ()
    return tuple(part.strip() for part in text.replace(";", ",").split(",") if part.strip())
