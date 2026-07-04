"""Backtest engine boundary."""

from __future__ import annotations

from typing import Protocol

from stock_lobster.l6_backtest_engine.result import BacktestResult


class BacktestEngine(Protocol):
    """Protocol for formal L6 backtest execution."""

    def run(self) -> BacktestResult:
        """Run a backtest and return an L6 result."""
