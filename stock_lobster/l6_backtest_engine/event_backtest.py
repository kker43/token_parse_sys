"""Event-driven holding-period backtest engine."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean, median
from typing import Iterable

from stock_lobster.l6_backtest_engine.metrics import win_rate
from stock_lobster.l6_backtest_engine.result import BacktestResult


@dataclass(frozen=True, slots=True)
class PriceBar:
    """Daily OHLC price bar for L6 backtests."""

    asset_id: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True, slots=True)
class BacktestEvent:
    """One strategy event to be evaluated by L6."""

    asset_id: str
    signal_date: str
    event_id: str


@dataclass(frozen=True, slots=True)
class EventBacktestPolicy:
    """Execution and holding assumptions for event backtests."""

    strategy_id: str
    strategy_version: str
    holding_horizon: int
    benchmark: str = "000300.SH"
    entry_offset: int = 1
    entry_price_field: str = "open"
    exit_price_field: str = "close"
    annual_trading_days: int = 252


@dataclass(frozen=True, slots=True)
class EventTradeResult:
    """One evaluated event trade."""

    event_id: str
    asset_id: str
    signal_date: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    holding_return: float
    max_drawdown: float

    def to_mapping(self) -> dict[str, object]:
        """Render this trade as a JSON-friendly mapping."""

        return {
            "event_id": self.event_id,
            "asset_id": self.asset_id,
            "signal_date": self.signal_date,
            "entry_date": self.entry_date,
            "exit_date": self.exit_date,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "holding_return": self.holding_return,
            "max_drawdown": self.max_drawdown,
        }


@dataclass(frozen=True, slots=True)
class EventBacktestReport:
    """Backtest result plus evaluated trade details."""

    result: BacktestResult
    trades: tuple[EventTradeResult, ...]
    skipped_events: tuple[str, ...] = field(default_factory=tuple)

    def to_mapping(self) -> dict[str, object]:
        """Render this report as a JSON-friendly mapping."""

        return {
            "result": {
                "strategy_id": self.result.strategy_id,
                "strategy_version": self.result.strategy_version,
                "backtest_period": list(self.result.backtest_period),
                "benchmark": self.result.benchmark,
                "holding_horizon": self.result.holding_horizon,
                "return_metrics": dict(self.result.return_metrics),
                "drawdown_metrics": dict(self.result.drawdown_metrics),
                "win_rate": self.result.win_rate,
                "sample_size": self.result.sample_size,
                "failure_cases": list(self.result.failure_cases),
            },
            "trades": [trade.to_mapping() for trade in self.trades],
            "skipped_events": list(self.skipped_events),
        }


def run_event_backtest(
    bars: Iterable[PriceBar],
    events: Iterable[BacktestEvent],
    policy: EventBacktestPolicy,
) -> EventBacktestReport:
    """Run an event-driven holding-period backtest."""

    bars_by_asset = _bars_by_asset(bars)
    trades: list[EventTradeResult] = []
    skipped_events: list[str] = []

    for event in sorted(events, key=lambda item: (item.asset_id, item.signal_date, item.event_id)):
        asset_bars = bars_by_asset.get(event.asset_id)
        if not asset_bars:
            skipped_events.append(f"{event.event_id}: missing bars")
            continue
        signal_index = _find_bar_index(asset_bars, event.signal_date)
        if signal_index is None:
            skipped_events.append(f"{event.event_id}: missing signal date")
            continue
        entry_index = signal_index + policy.entry_offset
        exit_index = entry_index + policy.holding_horizon - 1
        if entry_index >= len(asset_bars) or exit_index >= len(asset_bars):
            skipped_events.append(f"{event.event_id}: insufficient future bars")
            continue
        entry_bar = asset_bars[entry_index]
        exit_bar = asset_bars[exit_index]
        entry_price = _price_field(entry_bar, policy.entry_price_field)
        exit_price = _price_field(exit_bar, policy.exit_price_field)
        if entry_price <= 0:
            skipped_events.append(f"{event.event_id}: non-positive entry price")
            continue
        holding_window = asset_bars[entry_index : exit_index + 1]
        trades.append(
            EventTradeResult(
                event_id=event.event_id,
                asset_id=event.asset_id,
                signal_date=event.signal_date,
                entry_date=entry_bar.trade_date,
                exit_date=exit_bar.trade_date,
                entry_price=entry_price,
                exit_price=exit_price,
                holding_return=exit_price / entry_price - 1,
                max_drawdown=_max_drawdown_from_entry(entry_price, holding_window),
            )
        )

    result = _build_result(policy=policy, trades=tuple(trades), skipped_events=tuple(skipped_events))
    return EventBacktestReport(result=result, trades=tuple(trades), skipped_events=tuple(skipped_events))


def _bars_by_asset(bars: Iterable[PriceBar]) -> dict[str, list[PriceBar]]:
    grouped: dict[str, list[PriceBar]] = defaultdict(list)
    for bar in bars:
        grouped[bar.asset_id].append(bar)
    return {asset_id: sorted(items, key=lambda item: item.trade_date) for asset_id, items in grouped.items()}


def _find_bar_index(bars: list[PriceBar], trade_date: str) -> int | None:
    for index, bar in enumerate(bars):
        if bar.trade_date == trade_date:
            return index
    return None


def _price_field(bar: PriceBar, field_name: str) -> float:
    if field_name == "open":
        return bar.open
    if field_name == "high":
        return bar.high
    if field_name == "low":
        return bar.low
    if field_name == "close":
        return bar.close
    raise ValueError(f"unsupported price field: {field_name}")


def _max_drawdown_from_entry(entry_price: float, bars: list[PriceBar]) -> float:
    worst = 0.0
    peak = entry_price
    for bar in bars:
        peak = max(peak, bar.high)
        worst = min(worst, bar.low / peak - 1)
    return worst


def _build_result(
    policy: EventBacktestPolicy,
    trades: tuple[EventTradeResult, ...],
    skipped_events: tuple[str, ...],
) -> BacktestResult:
    returns = [trade.holding_return for trade in trades]
    drawdowns = [trade.max_drawdown for trade in trades]
    wins = sum(1 for item in returns if item > 0)
    sample_size = len(trades)
    if returns:
        average_return = mean(returns)
        median_return = median(returns)
        annualized_return = average_return * policy.annual_trading_days / policy.holding_horizon
        best_return = max(returns)
        worst_return = min(returns)
    else:
        average_return = 0.0
        median_return = 0.0
        annualized_return = 0.0
        best_return = 0.0
        worst_return = 0.0
    max_drawdown = min(drawdowns) if drawdowns else 0.0
    average_drawdown = mean(drawdowns) if drawdowns else 0.0
    period = _backtest_period(trades)
    return BacktestResult(
        strategy_id=policy.strategy_id,
        strategy_version=policy.strategy_version,
        backtest_period=period,
        benchmark=policy.benchmark,
        holding_horizon=policy.holding_horizon,
        return_metrics={
            "annual_return": annualized_return,
            "avg_return": average_return,
            "median_return": median_return,
            "best_return": best_return,
            "worst_return": worst_return,
        },
        drawdown_metrics={
            "max_drawdown": max_drawdown,
            "avg_trade_drawdown": average_drawdown,
        },
        win_rate=win_rate(wins=wins, sample_size=sample_size),
        sample_size=sample_size,
        failure_cases=skipped_events,
    )


def _backtest_period(trades: tuple[EventTradeResult, ...]) -> tuple[str, str]:
    if not trades:
        return ("", "")
    dates = [trade.signal_date for trade in trades]
    return (min(dates), max(dates))
