"""Deterministic scanner for steady uptrend breakout research samples."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


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


@dataclass(frozen=True, slots=True)
class TrendBreakoutMetrics:
    """Window metrics for one stock/date."""

    asset_id: str
    trade_date: str
    close: float
    ma5: float
    ma10: float
    ma20: float
    ma60: float
    ma120: float
    ma20_slope_20d: float
    amount_ratio_20d: float
    max_drawdown_60d: float
    convergence_5_10_20_pct: float
    close_new_high_60d_flag: bool
    steady_uptrend: bool
    breakout_watch: bool

    def to_mapping(self) -> dict[str, object]:
        """Render this metrics object as a JSON-friendly mapping."""

        return {
            "asset_id": self.asset_id,
            "trade_date": self.trade_date,
            "close": self.close,
            "ma5": self.ma5,
            "ma10": self.ma10,
            "ma20": self.ma20,
            "ma60": self.ma60,
            "ma120": self.ma120,
            "ma20_slope_20d": self.ma20_slope_20d,
            "amount_ratio_20d": self.amount_ratio_20d,
            "max_drawdown_60d": self.max_drawdown_60d,
            "convergence_5_10_20_pct": self.convergence_5_10_20_pct,
            "close_new_high_60d_flag": self.close_new_high_60d_flag,
            "steady_uptrend": self.steady_uptrend,
            "breakout_watch": self.breakout_watch,
        }


@dataclass(frozen=True, slots=True)
class TrendBreakoutScanPolicy:
    """Thresholds for the steady uptrend breakout candidate scanner."""

    min_amount_ratio_20d: float = 1.5
    max_abs_drawdown_60d: float = 0.40
    max_convergence_5_10_20_pct: float | None = None
    start_date: str | None = None


def read_kline_tsv(path: str | Path) -> tuple[KlineBar, ...]:
    """Read mysql `-B -N` style kline output."""

    bars: list[KlineBar] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        asset_id, trade_date, open_value, high, low, close, amount = line.split("\t")
        bars.append(
            KlineBar(
                asset_id=asset_id,
                trade_date=trade_date,
                open=float(open_value),
                high=float(high),
                low=float(low),
                close=float(close),
                amount=float(amount),
            )
        )
    return tuple(bars)


def scan_trend_breakouts(
    bars: Iterable[KlineBar],
    policy: TrendBreakoutScanPolicy | None = None,
) -> tuple[TrendBreakoutMetrics, ...]:
    """Scan kline bars and return deterministic trend-breakout metrics."""

    active_policy = policy or TrendBreakoutScanPolicy()
    by_asset: dict[str, list[KlineBar]] = defaultdict(list)
    for bar in bars:
        by_asset[bar.asset_id].append(bar)

    results: list[TrendBreakoutMetrics] = []
    for asset_id in sorted(by_asset):
        asset_bars = sorted(by_asset[asset_id], key=lambda bar: bar.trade_date)
        closes = [bar.close for bar in asset_bars]
        amounts = [bar.amount for bar in asset_bars]
        for index, bar in enumerate(asset_bars):
            if active_policy.start_date is not None and bar.trade_date < active_policy.start_date:
                continue
            metrics = _metrics_for_index(
                bars=asset_bars,
                closes=closes,
                amounts=amounts,
                index=index,
                policy=active_policy,
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
                "breakout_watch_count": 0,
                "first_breakout_watch_date": None,
                "latest_breakout_watch_date": None,
            },
        )
        if item.steady_uptrend:
            stock_summary["steady_uptrend_count"] = int(stock_summary["steady_uptrend_count"]) + 1
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
    index: int,
    policy: TrendBreakoutScanPolicy,
) -> TrendBreakoutMetrics | None:
    ma5 = _ma(closes, 5, index)
    ma10 = _ma(closes, 10, index)
    ma20 = _ma(closes, 20, index)
    ma60 = _ma(closes, 60, index)
    ma120 = _ma(closes, 120, index)
    if None in (ma5, ma10, ma20, ma60, ma120):
        return None
    previous_ma20 = _ma(closes, 20, index - 20) if index >= 20 else None
    max_drawdown_60d = _max_drawdown(closes, index, 60)
    if previous_ma20 is None or max_drawdown_60d is None:
        return None

    bar = bars[index]
    amount_average_20d = _ma(amounts, 20, index)
    if amount_average_20d is None or amount_average_20d == 0:
        return None

    ma20_slope_20d = ma20 / previous_ma20 - 1
    amount_ratio_20d = bar.amount / amount_average_20d
    convergence_5_10_20_pct = (max(ma5, ma10, ma20) - min(ma5, ma10, ma20)) / bar.close
    close_new_high_60d_flag = bar.close >= max(closes[index - 59 : index + 1])
    steady_uptrend = (
        bar.close > ma20
        and bar.close > ma60
        and ma20 > ma60
        and ma60 > ma120
        and ma20_slope_20d > 0
        and abs(max_drawdown_60d) <= policy.max_abs_drawdown_60d
    )
    convergence_ok = (
        policy.max_convergence_5_10_20_pct is None
        or convergence_5_10_20_pct <= policy.max_convergence_5_10_20_pct
    )
    breakout_watch = (
        steady_uptrend
        and close_new_high_60d_flag
        and amount_ratio_20d >= policy.min_amount_ratio_20d
        and convergence_ok
    )

    return TrendBreakoutMetrics(
        asset_id=bar.asset_id,
        trade_date=bar.trade_date,
        close=bar.close,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        ma60=ma60,
        ma120=ma120,
        ma20_slope_20d=ma20_slope_20d,
        amount_ratio_20d=amount_ratio_20d,
        max_drawdown_60d=max_drawdown_60d,
        convergence_5_10_20_pct=convergence_5_10_20_pct,
        close_new_high_60d_flag=close_new_high_60d_flag,
        steady_uptrend=steady_uptrend,
        breakout_watch=breakout_watch,
    )


def _ma(values: list[float], window: int, index: int) -> float | None:
    if index < 0 or index + 1 < window:
        return None
    return sum(values[index - window + 1 : index + 1]) / window


def _max_drawdown(values: list[float], index: int, window: int) -> float | None:
    if index + 1 < window:
        return None
    current_peak = values[index - window + 1]
    worst = 0.0
    for value in values[index - window + 1 : index + 1]:
        current_peak = max(current_peak, value)
        worst = min(worst, value / current_peak - 1)
    return worst
