"""Research-only subtype recall after minimum quality and liquidity gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from stock_lobster.research.trend_breakout_scan import TrendBreakoutMetrics


@dataclass(frozen=True, slots=True)
class RecallSubpoolMatch:
    """One deterministic research subpool decision."""

    subpool_id: str
    matched: bool
    score_adjustment: float
    reasons: tuple[str, ...] = ()

    def to_mapping(self) -> dict[str, object]:
        return {
            "subpool_id": self.subpool_id,
            "matched": self.matched,
            "score_adjustment": self.score_adjustment,
            "reasons": list(self.reasons),
        }


def classify_recall_subpools(
    metric: TrendBreakoutMetrics,
) -> dict[str, RecallSubpoolMatch]:
    """Classify one metric after only the basic liquidity gate."""

    subpool_ids = (
        "long_base_breakout",
        "pullback_reacceleration",
        "ma10_ma20_walkup",
        "trend_following",
        "early_reversal",
    )
    if not metric.market_cap_liquidity_pass:
        return {
            subpool_id: RecallSubpoolMatch(
                subpool_id=subpool_id,
                matched=False,
                score_adjustment=0.0,
                reasons=("basic_liquidity_failed",),
            )
            for subpool_id in subpool_ids
        }

    volume_score = _volume_score(metric.amount_ratio_prev_20d)
    severe_shape_reasons = _severe_shape_reasons(metric)
    close_near_high = metric.close_new_high_60d_flag or metric.close_to_high_60d_pct >= -0.04
    results = {
        "long_base_breakout": _decision(
            "long_base_breakout",
            matched=(
                metric.close_new_high_60d_flag
                and metric.impulse_consolidation_days >= 5
                and metric.return_20d <= 0.25
            ),
            score=volume_score,
            failure_reason="long_base_structure_failed",
            severe_shape_reasons=severe_shape_reasons,
        ),
        "pullback_reacceleration": _decision(
            "pullback_reacceleration",
            matched=(
                close_near_high
                and metric.ma30_hold_ratio_30d >= 0.75
                and metric.ma30_hold_ratio_60d >= 0.55
            ),
            score=volume_score + 1.0,
            failure_reason="recent_ma30_support_failed",
            severe_shape_reasons=severe_shape_reasons,
        ),
        "ma10_ma20_walkup": _decision(
            "ma10_ma20_walkup",
            matched=(
                close_near_high
                and metric.ma5 >= metric.ma10 >= metric.ma20
                and metric.ma20_slope_20d > 0
                and metric.return_20d <= 0.25
                and metric.single_bull_bar_return_share_20d <= 0.35
            ),
            score=volume_score + 1.0,
            failure_reason="ma10_ma20_walkup_failed",
            severe_shape_reasons=severe_shape_reasons,
        ),
        "trend_following": _decision(
            "trend_following",
            matched=metric.steady_uptrend or metric.ma30_hold_ratio_90d >= 0.75,
            score=volume_score + (2.0 if metric.ma30_hold_ratio_90d >= 0.75 else 0.0),
            failure_reason="mature_trend_quality_failed",
            severe_shape_reasons=severe_shape_reasons,
        ),
        "early_reversal": _decision(
            "early_reversal",
            matched=(
                not metric.close_new_high_60d_flag
                and metric.ma20_slope_20d > 0
                and 0.08 <= metric.return_20d <= 0.25
                and metric.ma30_hold_ratio_30d >= 0.55
            ),
            score=volume_score,
            failure_reason="early_reversal_confirmation_failed",
            severe_shape_reasons=severe_shape_reasons,
        ),
    }
    return results


def matched_subpool_ids(matches: Mapping[str, RecallSubpoolMatch]) -> tuple[str, ...]:
    return tuple(subpool_id for subpool_id, match in matches.items() if match.matched)


def _decision(
    subpool_id: str,
    *,
    matched: bool,
    score: float,
    failure_reason: str,
    severe_shape_reasons: tuple[str, ...],
) -> RecallSubpoolMatch:
    reasons = severe_shape_reasons if severe_shape_reasons else (() if matched else (failure_reason,))
    return RecallSubpoolMatch(
        subpool_id=subpool_id,
        matched=matched and not severe_shape_reasons,
        score_adjustment=round(score, 4),
        reasons=reasons,
    )


def _volume_score(amount_ratio_prev_20d: float) -> float:
    if amount_ratio_prev_20d >= 1.5:
        return 2.0
    if amount_ratio_prev_20d >= 1.0:
        return 1.0
    return -1.0


def _severe_shape_reasons(metric: TrendBreakoutMetrics) -> tuple[str, ...]:
    reasons: list[str] = []
    if (
        metric.long_shadow_ratio_20d >= 0.55
        and metric.large_bearish_body_ratio_20d >= 0.30
        and metric.ma30_hold_ratio_30d < 0.90
        and metric.ma30_deviation_pct >= 0.10
    ):
        reasons.append("noisy_ma30_breakdown_rebound")
    if metric.large_bearish_body_ratio_20d > 0.30:
        reasons.append("large_bearish_pullback_cluster")
    if metric.single_bull_bar_return_share_20d > 0.50 and metric.impulse_consolidation_days < 5:
        reasons.append("steep_v_shape_without_base")
    if metric.return_20d > 0.30 and metric.impulse_consolidation_days < 5:
        reasons.append("acceleration_without_rest")
    return tuple(reasons)
