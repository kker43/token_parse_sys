"""Ranking helpers for L5 signals."""

from __future__ import annotations

from stock_lobster.l5_signal_engine.engine import StrategySignal


def sort_signals(signals: list[StrategySignal]) -> list[StrategySignal]:
    """Sort signals by rank and score."""

    return sorted(signals, key=lambda signal: (signal.rank, -signal.ranking_score))
