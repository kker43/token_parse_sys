"""Backtest metric helpers."""

from __future__ import annotations


def win_rate(wins: int, sample_size: int) -> float:
    """Compute a guarded win rate."""

    if sample_size <= 0:
        return 0.0
    return wins / sample_size
