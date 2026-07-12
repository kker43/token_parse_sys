"""Ordered structural recall and signal-stage research decisions."""

from __future__ import annotations

from dataclasses import dataclass

from stock_lobster.research.trend_breakout_scan import TrendBreakoutMetrics
from stock_lobster.research.trend_recall_subpools import (
    TrendRecallSubpoolPolicy,
    classify_recall_subpools,
    matched_subpool_ids,
)


@dataclass(frozen=True, slots=True)
class LayeredRecallDecision:
    """Structural recall result produced before signal-stage filters."""

    metric: TrendBreakoutMetrics
    matched_subpools: tuple[str, ...]
    recall_candidate: bool


def build_layered_recall_decision(
    metric: TrendBreakoutMetrics,
    *,
    policy: TrendRecallSubpoolPolicy | None = None,
) -> LayeredRecallDecision:
    """Build the union decision for the five structural recall subpools."""

    matches = classify_recall_subpools(metric, policy=policy)
    matched = matched_subpool_ids(matches)
    return LayeredRecallDecision(
        metric=metric,
        matched_subpools=matched,
        recall_candidate=bool(matched),
    )
