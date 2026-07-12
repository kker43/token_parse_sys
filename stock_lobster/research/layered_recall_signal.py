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


@dataclass(frozen=True, slots=True)
class SignalStateAssessment:
    """Signal-stage state evaluated after structural recall."""

    recall_candidate: bool
    waiting_reasons: tuple[str, ...]
    hard_risk_reasons: tuple[str, ...]
    confirmation_reasons: tuple[str, ...]
    effective_activity_ratio: float | None
    signal_eligible: bool


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


def assess_signal_state(decision: LayeredRecallDecision) -> SignalStateAssessment:
    """Classify waiting, risk, and confirmation states after recall."""

    metric = decision.metric
    waiting_reasons: list[str] = []
    hard_risk_reasons: list[str] = []
    confirmation_reasons: list[str] = []

    if metric.return_20d > 0.30 and metric.impulse_consolidation_days < 5:
        waiting_reasons.append("acceleration_needs_consolidation")
    if (
        metric.return_20d > 0.60
        and metric.ma5_10_20_30_convergence_pct > 0.18
    ):
        waiting_reasons.append("overextended_wide_ma_needs_rest")
    if (
        metric.post_impulse_followthrough_return is not None
        and metric.post_impulse_followthrough_return <= 0
    ):
        waiting_reasons.append("post_impulse_no_followthrough")
    if metric.high_volume_bearish_close:
        waiting_reasons.append("high_volume_bearish_close")

    if (
        metric.long_shadow_ratio_20d >= 0.55
        and metric.large_bearish_body_ratio_20d >= 0.30
        and metric.ma30_hold_ratio_30d < 0.90
        and metric.ma30_deviation_pct >= 0.10
    ):
        hard_risk_reasons.append("noisy_ma30_breakdown_rebound")

    if metric.large_bearish_body_ratio_20d > 0.30:
        confirmation_reasons.append("bearish_cluster_score_penalty")

    effective_activity_ratio = (
        metric.turnover_ratio_5d_20d
        if metric.adj_factor_changed_20d
        else metric.volume_ratio_5d_20d
    )
    if effective_activity_ratio is None:
        confirmation_reasons.append("insufficient_volume_confirmation")

    signal_eligible = (
        decision.recall_candidate
        and not waiting_reasons
        and not hard_risk_reasons
        and effective_activity_ratio is not None
    )
    return SignalStateAssessment(
        recall_candidate=decision.recall_candidate,
        waiting_reasons=tuple(waiting_reasons),
        hard_risk_reasons=tuple(hard_risk_reasons),
        confirmation_reasons=tuple(confirmation_reasons),
        effective_activity_ratio=effective_activity_ratio,
        signal_eligible=signal_eligible,
    )
