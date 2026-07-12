"""Candidate-pool equal-weight benchmark calculation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean, median
from typing import Iterable

from stock_lobster.l6_backtest_engine.event_backtest import (
    BacktestEvent,
    EventBacktestPolicy,
    EventTradeResult,
    PriceBar,
    run_event_backtest,
)


@dataclass(frozen=True, slots=True)
class CandidatePoolSignalDateReturn:
    """Equal-weight benchmark return for one signal date."""

    signal_date: str
    candidate_count: int
    evaluated_candidate_count: int
    skipped_candidate_count: int
    equal_weight_return: float
    equal_weight_drawdown: float

    def to_mapping(self) -> dict[str, object]:
        """Render this signal-date return as a JSON-friendly mapping."""

        return {
            "signal_date": self.signal_date,
            "candidate_count": self.candidate_count,
            "evaluated_candidate_count": self.evaluated_candidate_count,
            "skipped_candidate_count": self.skipped_candidate_count,
            "equal_weight_return": self.equal_weight_return,
            "equal_weight_drawdown": self.equal_weight_drawdown,
        }


@dataclass(frozen=True, slots=True)
class CandidatePoolBenchmarkResult:
    """Candidate-pool equal-weight benchmark result."""

    benchmark_id: str
    holding_horizon: int
    benchmark_period: tuple[str, str]
    signal_date_returns: tuple[CandidatePoolSignalDateReturn, ...]
    return_metrics: dict[str, float]
    drawdown_metrics: dict[str, float]
    signal_date_count: int
    candidate_count: int
    evaluated_candidate_count: int
    skipped_events: tuple[str, ...] = field(default_factory=tuple)

    def to_mapping(self) -> dict[str, object]:
        """Render this benchmark result as a JSON-friendly mapping."""

        return {
            "benchmark_id": self.benchmark_id,
            "holding_horizon": self.holding_horizon,
            "benchmark_period": list(self.benchmark_period),
            "signal_date_returns": [item.to_mapping() for item in self.signal_date_returns],
            "return_metrics": dict(self.return_metrics),
            "drawdown_metrics": dict(self.drawdown_metrics),
            "signal_date_count": self.signal_date_count,
            "candidate_count": self.candidate_count,
            "evaluated_candidate_count": self.evaluated_candidate_count,
            "skipped_events": list(self.skipped_events),
        }


def run_candidate_pool_equal_weight_benchmark(
    bars: Iterable[PriceBar],
    candidate_events: Iterable[BacktestEvent],
    policy: EventBacktestPolicy,
    benchmark_id: str = "candidate_pool_equal_weight_v1",
) -> CandidatePoolBenchmarkResult:
    """Run a candidate-pool equal-weight benchmark.

    Each signal date is treated as one equal-weight candidate-pool portfolio.
    The aggregate return is the mean of signal-date portfolio returns.
    """

    events = tuple(candidate_events)
    event_signal_dates = {event.event_id: event.signal_date for event in events}
    expected_counts = _count_events_by_signal_date(events)
    report = run_event_backtest(bars=bars, events=events, policy=policy)
    trades_by_signal_date = _trades_by_signal_date(report.trades)
    skipped_counts = _skipped_counts_by_signal_date(report.skipped_events, event_signal_dates)

    signal_date_returns: list[CandidatePoolSignalDateReturn] = []
    for signal_date in sorted(expected_counts):
        trades = trades_by_signal_date.get(signal_date, ())
        returns = [trade.holding_return for trade in trades]
        drawdowns = [trade.max_drawdown for trade in trades]
        signal_date_returns.append(
            CandidatePoolSignalDateReturn(
                signal_date=signal_date,
                candidate_count=expected_counts[signal_date],
                evaluated_candidate_count=len(trades),
                skipped_candidate_count=skipped_counts.get(signal_date, 0),
                equal_weight_return=mean(returns) if returns else 0.0,
                equal_weight_drawdown=mean(drawdowns) if drawdowns else 0.0,
            )
        )

    return _build_benchmark_result(
        benchmark_id=benchmark_id,
        holding_horizon=policy.holding_horizon,
        signal_date_returns=tuple(signal_date_returns),
        skipped_events=report.skipped_events,
    )


def _count_events_by_signal_date(events: tuple[BacktestEvent, ...]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for event in events:
        counts[event.signal_date] += 1
    return dict(counts)


def _trades_by_signal_date(
    trades: tuple[EventTradeResult, ...],
) -> dict[str, tuple[EventTradeResult, ...]]:
    grouped: dict[str, list[EventTradeResult]] = defaultdict(list)
    for trade in trades:
        grouped[trade.signal_date].append(trade)
    return {signal_date: tuple(items) for signal_date, items in grouped.items()}


def _skipped_counts_by_signal_date(
    skipped_events: tuple[str, ...],
    event_signal_dates: dict[str, str],
) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for skipped in skipped_events:
        event_id = skipped.split(":", 1)[0]
        signal_date = event_signal_dates.get(event_id)
        if signal_date is not None:
            counts[signal_date] += 1
    return dict(counts)


def _build_benchmark_result(
    benchmark_id: str,
    holding_horizon: int,
    signal_date_returns: tuple[CandidatePoolSignalDateReturn, ...],
    skipped_events: tuple[str, ...],
) -> CandidatePoolBenchmarkResult:
    returns = [item.equal_weight_return for item in signal_date_returns if item.evaluated_candidate_count > 0]
    drawdowns = [item.equal_weight_drawdown for item in signal_date_returns if item.evaluated_candidate_count > 0]
    signal_date_count = len(returns)
    evaluated_candidate_count = sum(item.evaluated_candidate_count for item in signal_date_returns)
    candidate_count = sum(item.candidate_count for item in signal_date_returns)
    if returns:
        average_return = mean(returns)
        median_return = median(returns)
        annual_return = average_return * 252 / holding_horizon
        best_return = max(returns)
        worst_return = min(returns)
    else:
        average_return = 0.0
        median_return = 0.0
        annual_return = 0.0
        best_return = 0.0
        worst_return = 0.0
    benchmark_period = _benchmark_period(signal_date_returns)
    return CandidatePoolBenchmarkResult(
        benchmark_id=benchmark_id,
        holding_horizon=holding_horizon,
        benchmark_period=benchmark_period,
        signal_date_returns=signal_date_returns,
        return_metrics={
            "annual_return": annual_return,
            "avg_signal_date_return": average_return,
            "median_signal_date_return": median_return,
            "best_signal_date_return": best_return,
            "worst_signal_date_return": worst_return,
        },
        drawdown_metrics={
            "max_signal_date_drawdown": min(drawdowns) if drawdowns else 0.0,
            "avg_signal_date_drawdown": mean(drawdowns) if drawdowns else 0.0,
        },
        signal_date_count=signal_date_count,
        candidate_count=candidate_count,
        evaluated_candidate_count=evaluated_candidate_count,
        skipped_events=skipped_events,
    )


def _benchmark_period(
    signal_date_returns: tuple[CandidatePoolSignalDateReturn, ...],
) -> tuple[str, str]:
    dates = [item.signal_date for item in signal_date_returns]
    if not dates:
        return ("", "")
    return (min(dates), max(dates))
