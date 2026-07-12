"""Short-horizon trade-management backtests."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from statistics import mean, median
from typing import Iterable

from stock_lobster.l6_backtest_engine.event_backtest import BacktestEvent, PriceBar
from stock_lobster.l6_backtest_engine.metrics import win_rate
from stock_lobster.l6_backtest_engine.result import BacktestResult


@dataclass(frozen=True, slots=True)
class TradeManagementPolicy:
    """Execution, entry filter, and exit assumptions for short trades."""

    strategy_id: str
    strategy_version: str
    max_holding_days: int
    benchmark: str = "000300.SH"
    entry_offset: int = 1
    max_entry_gap_up_pct: float | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    annual_trading_days: int = 252

    def to_mapping(self) -> dict[str, object]:
        """Render this policy as a JSON-friendly mapping."""

        return {
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "max_holding_days": self.max_holding_days,
            "benchmark": self.benchmark,
            "entry_offset": self.entry_offset,
            "max_entry_gap_up_pct": self.max_entry_gap_up_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "annual_trading_days": self.annual_trading_days,
        }


@dataclass(frozen=True, slots=True)
class ManagedTradeResult:
    """One evaluated short trade with an explicit exit reason."""

    event_id: str
    asset_id: str
    signal_date: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    holding_return: float
    max_drawdown: float
    exit_reason: str
    holding_days: int
    entry_gap_up: float

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
            "exit_reason": self.exit_reason,
            "holding_days": self.holding_days,
            "entry_gap_up": self.entry_gap_up,
        }


@dataclass(frozen=True, slots=True)
class TradeManagementReport:
    """Backtest result plus managed trade details."""

    policy: TradeManagementPolicy
    result: BacktestResult
    trades: tuple[ManagedTradeResult, ...]
    skipped_events: tuple[str, ...] = field(default_factory=tuple)

    def to_mapping(self) -> dict[str, object]:
        """Render this report as a JSON-friendly mapping."""

        return {
            "policy": self.policy.to_mapping(),
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
            "exit_reason_counts": dict(Counter(trade.exit_reason for trade in self.trades)),
            "trades": [trade.to_mapping() for trade in self.trades],
            "skipped_events": list(self.skipped_events),
        }


def run_trade_management_backtest(
    *,
    bars: Iterable[PriceBar],
    events: Iterable[BacktestEvent],
    policy: TradeManagementPolicy,
) -> TradeManagementReport:
    """Run short-horizon trade management backtests for strategy events."""

    bars_by_asset = _bars_by_asset(bars)
    trades: list[ManagedTradeResult] = []
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
        max_exit_index = entry_index + policy.max_holding_days - 1
        if entry_index >= len(asset_bars) or max_exit_index >= len(asset_bars):
            skipped_events.append(f"{event.event_id}: insufficient future bars")
            continue

        signal_bar = asset_bars[signal_index]
        entry_bar = asset_bars[entry_index]
        entry_price = entry_bar.open
        if entry_price <= 0:
            skipped_events.append(f"{event.event_id}: non-positive entry price")
            continue
        if signal_bar.close <= 0:
            skipped_events.append(f"{event.event_id}: non-positive signal close")
            continue
        entry_gap_up = entry_price / signal_bar.close - 1
        if policy.max_entry_gap_up_pct is not None and entry_gap_up > policy.max_entry_gap_up_pct:
            skipped_events.append(
                f"{event.event_id}: entry_gap_up {entry_gap_up:.4f} > {policy.max_entry_gap_up_pct:.4f}"
            )
            continue

        exit_index, exit_price, exit_reason = _managed_exit(
            bars=asset_bars[entry_index : max_exit_index + 1],
            entry_price=entry_price,
            policy=policy,
        )
        exit_bar = asset_bars[entry_index + exit_index]
        holding_window = asset_bars[entry_index : entry_index + exit_index + 1]
        trades.append(
            ManagedTradeResult(
                event_id=event.event_id,
                asset_id=event.asset_id,
                signal_date=event.signal_date,
                entry_date=entry_bar.trade_date,
                exit_date=exit_bar.trade_date,
                entry_price=entry_price,
                exit_price=exit_price,
                holding_return=exit_price / entry_price - 1,
                max_drawdown=_max_drawdown_from_entry(entry_price, holding_window),
                exit_reason=exit_reason,
                holding_days=exit_index + 1,
                entry_gap_up=entry_gap_up,
            )
        )

    result = _build_result(policy=policy, trades=tuple(trades), skipped_events=tuple(skipped_events))
    return TradeManagementReport(
        policy=policy,
        result=result,
        trades=tuple(trades),
        skipped_events=tuple(skipped_events),
    )


def _managed_exit(
    *,
    bars: list[PriceBar],
    entry_price: float,
    policy: TradeManagementPolicy,
) -> tuple[int, float, str]:
    stop_price = entry_price * (1 + policy.stop_loss_pct) if policy.stop_loss_pct is not None else None
    take_price = entry_price * (1 + policy.take_profit_pct) if policy.take_profit_pct is not None else None
    for index, bar in enumerate(bars):
        if stop_price is not None and bar.low <= stop_price:
            return (index, stop_price, "stop_loss")
        if take_price is not None and bar.high >= take_price:
            return (index, take_price, "take_profit")
    last_bar = bars[-1]
    return (len(bars) - 1, last_bar.close, "time_exit")


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


def _max_drawdown_from_entry(entry_price: float, bars: list[PriceBar]) -> float:
    worst = 0.0
    peak = entry_price
    for bar in bars:
        peak = max(peak, bar.high)
        worst = min(worst, bar.low / peak - 1)
    return worst


def _build_result(
    *,
    policy: TradeManagementPolicy,
    trades: tuple[ManagedTradeResult, ...],
    skipped_events: tuple[str, ...],
) -> BacktestResult:
    returns = [trade.holding_return for trade in trades]
    drawdowns = [trade.max_drawdown for trade in trades]
    wins = sum(1 for item in returns if item > 0)
    sample_size = len(trades)
    if returns:
        average_return = mean(returns)
        median_return = median(returns)
        annualized_return = average_return * policy.annual_trading_days / policy.max_holding_days
        best_return = max(returns)
        worst_return = min(returns)
    else:
        average_return = 0.0
        median_return = 0.0
        annualized_return = 0.0
        best_return = 0.0
        worst_return = 0.0
    return BacktestResult(
        strategy_id=policy.strategy_id,
        strategy_version=policy.strategy_version,
        backtest_period=_backtest_period(trades),
        benchmark=policy.benchmark,
        holding_horizon=policy.max_holding_days,
        return_metrics={
            "annual_return": annualized_return,
            "avg_return": average_return,
            "median_return": median_return,
            "best_return": best_return,
            "worst_return": worst_return,
        },
        drawdown_metrics={
            "max_drawdown": min(drawdowns) if drawdowns else 0.0,
            "avg_trade_drawdown": mean(drawdowns) if drawdowns else 0.0,
        },
        win_rate=win_rate(wins=wins, sample_size=sample_size),
        sample_size=sample_size,
        failure_cases=skipped_events,
    )


def _backtest_period(trades: tuple[ManagedTradeResult, ...]) -> tuple[str, str]:
    if not trades:
        return ("", "")
    dates = [trade.signal_date for trade in trades]
    return (min(dates), max(dates))
