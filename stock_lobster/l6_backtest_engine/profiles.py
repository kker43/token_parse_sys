"""Backtest evaluation profiles."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvaluationProfile:
    """Configurable backtest profile tied to a strategy version."""

    profile_id: str
    benchmark: str
    holding_horizons: tuple[int, ...]
    selection_frequency: str
