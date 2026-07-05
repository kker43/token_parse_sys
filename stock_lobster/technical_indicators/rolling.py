"""Reusable rolling-window technical indicator calculations."""

from __future__ import annotations


def moving_average_at(values: list[float], window: int, index: int) -> float | None:
    """Return the rolling moving average ending at index."""

    if index < 0 or index + 1 < window:
        return None
    return sum(values[index - window + 1 : index + 1]) / window


def relative_slope_at(values: list[float], window: int, lookback: int, index: int) -> float | None:
    """Return current rolling average divided by lookback rolling average minus one."""

    current = moving_average_at(values, window, index)
    previous = moving_average_at(values, window, index - lookback)
    if current is None or previous is None or previous == 0:
        return None
    return current / previous - 1


def rolling_max_drawdown_at(values: list[float], window: int, index: int) -> float | None:
    """Return close-to-close max drawdown over a rolling window ending at index."""

    if index + 1 < window:
        return None
    current_peak = values[index - window + 1]
    worst = 0.0
    for value in values[index - window + 1 : index + 1]:
        current_peak = max(current_peak, value)
        if current_peak == 0:
            continue
        worst = min(worst, value / current_peak - 1)
    return worst
