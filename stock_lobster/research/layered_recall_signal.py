"""Ordered structural recall and signal-stage research decisions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping

from stock_lobster.research.steady_uptrend_v3 import MarketTemperature
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


@dataclass(frozen=True, slots=True)
class LayeredSignalPolicy:
    """Ranking and post-rank policy for the research-only signal stage."""

    volume_ratio_is_hard_gate: bool = False
    long_base_volume_bonus_threshold: float = 1.1
    weak_market_breadth_ma20_threshold: float = 0.35
    weak_market_top_n: int = 2
    normal_market_top_n: int = 3
    cooldown_trade_days: int = 10
    acceleration_min_return_20d: float = 0.30
    acceleration_min_consolidation_days: int = 5
    overextended_min_return_20d: float = 0.60
    overextended_min_convergence_pct: float = 0.18
    post_impulse_min_return: float = 0.04
    blocked_context_names: tuple[str, ...] = ()
    post_rank_no_refill_rejection_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LayeredCandidate:
    """One recalled metric with its signal-stage diagnostics."""

    decision: LayeredRecallDecision
    state: SignalStateAssessment
    score: float
    post_rank_rejection_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LayeredSelectionResult:
    """Auditable outputs for every ordered recall and signal stage."""

    minimum_quality_pool: tuple[TrendBreakoutMetrics, ...]
    basic_liquidity_pool: tuple[TrendBreakoutMetrics, ...]
    recall_candidates: tuple[LayeredCandidate, ...]
    waiting_candidates: tuple[LayeredCandidate, ...]
    hard_risk_rejected_candidates: tuple[LayeredCandidate, ...]
    signal_eligible_candidates: tuple[LayeredCandidate, ...]
    ranked_topn: tuple[LayeredCandidate, ...]
    final_signals: tuple[LayeredCandidate, ...]

    def stage_counts(self) -> dict[str, int]:
        return {
            "minimum_quality_pool": len(self.minimum_quality_pool),
            "basic_liquidity_pool": len(self.basic_liquidity_pool),
            "recall_union": len(self.recall_candidates),
            "waiting_pool": len(self.waiting_candidates),
            "hard_risk_rejected": len(self.hard_risk_rejected_candidates),
            "signal_eligible": len(self.signal_eligible_candidates),
            "ranked_topn": len(self.ranked_topn),
            "final_signal": len(self.final_signals),
        }


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


def assess_signal_state(
    decision: LayeredRecallDecision,
    *,
    policy: LayeredSignalPolicy | None = None,
) -> SignalStateAssessment:
    """Classify waiting, risk, and confirmation states after recall."""

    metric = decision.metric
    active_policy = policy or LayeredSignalPolicy()
    waiting_reasons: list[str] = []
    hard_risk_reasons: list[str] = []
    confirmation_reasons: list[str] = []

    if (
        metric.return_20d > active_policy.acceleration_min_return_20d
        and metric.impulse_consolidation_days
        < active_policy.acceleration_min_consolidation_days
    ):
        waiting_reasons.append("acceleration_needs_consolidation")
    if (
        metric.return_20d > active_policy.overextended_min_return_20d
        and metric.ma5_10_20_30_convergence_pct
        > active_policy.overextended_min_convergence_pct
    ):
        waiting_reasons.append("overextended_wide_ma_needs_rest")
    if (
        metric.recent_impulse_return is not None
        and metric.recent_impulse_return >= active_policy.post_impulse_min_return
        and metric.post_impulse_followthrough_return is not None
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


def select_layered_candidates(
    metrics: Iterable[TrendBreakoutMetrics],
    *,
    market_temperatures: Mapping[str, MarketTemperature],
    recall_policy: TrendRecallSubpoolPolicy | None = None,
    signal_policy: LayeredSignalPolicy | None = None,
    trade_date_order: Iterable[str] | None = None,
) -> LayeredSelectionResult:
    """Run minimum-quality, recall, signal-state, ranking, and no-refill stages."""

    active_signal_policy = signal_policy or LayeredSignalPolicy()
    minimum_quality_pool = tuple(sorted(metrics, key=lambda item: (item.trade_date, item.asset_id)))
    basic_liquidity_pool = tuple(
        metric for metric in minimum_quality_pool if metric.market_cap_liquidity_pass
    )
    recall_candidates: list[LayeredCandidate] = []
    for metric in basic_liquidity_pool:
        decision = build_layered_recall_decision(metric, policy=recall_policy)
        if not decision.recall_candidate:
            continue
        state = assess_signal_state(decision, policy=active_signal_policy)
        recall_candidates.append(
            LayeredCandidate(
                decision=decision,
                state=state,
                score=_layered_score(
                    decision,
                    state,
                    market_temperatures.get(metric.trade_date),
                    active_signal_policy,
                ),
            )
        )

    waiting_candidates = tuple(
        candidate for candidate in recall_candidates if candidate.state.waiting_reasons
    )
    hard_risk_rejected_candidates = tuple(
        candidate for candidate in recall_candidates if candidate.state.hard_risk_reasons
    )
    signal_eligible_candidates = tuple(
        candidate for candidate in recall_candidates if candidate.state.signal_eligible
    )
    ranked_topn = _rank_topn(
        signal_eligible_candidates,
        market_temperatures=market_temperatures,
        policy=active_signal_policy,
        trade_date_order=trade_date_order,
    )
    ranked_with_reasons = tuple(
        LayeredCandidate(
            decision=candidate.decision,
            state=candidate.state,
            score=candidate.score,
            post_rank_rejection_reasons=_post_rank_rejection_reasons(
                candidate,
                active_signal_policy,
            ),
        )
        for candidate in ranked_topn
    )
    final_signals = tuple(
        candidate
        for candidate in ranked_with_reasons
        if not candidate.post_rank_rejection_reasons
    )
    return LayeredSelectionResult(
        minimum_quality_pool=minimum_quality_pool,
        basic_liquidity_pool=basic_liquidity_pool,
        recall_candidates=tuple(recall_candidates),
        waiting_candidates=waiting_candidates,
        hard_risk_rejected_candidates=hard_risk_rejected_candidates,
        signal_eligible_candidates=signal_eligible_candidates,
        ranked_topn=ranked_with_reasons,
        final_signals=final_signals,
    )


def _layered_score(
    decision: LayeredRecallDecision,
    state: SignalStateAssessment,
    market_temperature: MarketTemperature | None,
    policy: LayeredSignalPolicy,
) -> float:
    metric = decision.metric
    score = float(metric.setup_score) + len(decision.matched_subpools) * 2.0
    if (
        "long_base_breakout" in decision.matched_subpools
        and state.effective_activity_ratio is not None
        and state.effective_activity_ratio >= policy.long_base_volume_bonus_threshold
    ):
        score += 3.0
    if "bearish_cluster_score_penalty" in state.confirmation_reasons:
        score -= 5.0
    if metric.price_volume_efficiency_5d is not None:
        score += max(min(metric.price_volume_efficiency_5d * 10.0, 5.0), -5.0)
    if market_temperature is not None:
        score -= max(market_temperature.breadth_ma20 - 0.35, 0.0) * 10.0
        score -= max(market_temperature.avg_return_20d - 0.015, 0.0) * 80.0
    return round(score, 6)


def _rank_topn(
    candidates: Iterable[LayeredCandidate],
    *,
    market_temperatures: Mapping[str, MarketTemperature],
    policy: LayeredSignalPolicy,
    trade_date_order: Iterable[str] | None,
) -> tuple[LayeredCandidate, ...]:
    by_date: dict[str, list[LayeredCandidate]] = defaultdict(list)
    for candidate in candidates:
        by_date[candidate.decision.metric.trade_date].append(candidate)
    dates = set(by_date)
    provided_date_order = tuple(trade_date_order or ())
    full_date_order = (
        tuple(sorted(dates))
        if not provided_date_order
        else provided_date_order + tuple(sorted(dates.difference(provided_date_order)))
    )
    ordered_dates = tuple(date for date in full_date_order if date in dates)
    date_index = {trade_date: index for index, trade_date in enumerate(full_date_order)}
    selected: list[LayeredCandidate] = []
    last_selected_by_asset: dict[str, int] = {}
    for trade_date in ordered_dates:
        temperature = market_temperatures.get(trade_date)
        top_n = (
            policy.weak_market_top_n
            if temperature is not None
            and temperature.breadth_ma20 < policy.weak_market_breadth_ma20_threshold
            else policy.normal_market_top_n
        )
        ranked = sorted(
            by_date[trade_date],
            key=lambda item: (-item.score, -item.decision.metric.setup_score, item.decision.metric.asset_id),
        )
        selected_on_date = 0
        for candidate in ranked:
            metric = candidate.decision.metric
            current_index = date_index[trade_date]
            last_index = last_selected_by_asset.get(metric.asset_id)
            if (
                last_index is not None
                and policy.cooldown_trade_days > 0
                and current_index - last_index <= policy.cooldown_trade_days
            ):
                continue
            selected.append(candidate)
            selected_on_date += 1
            last_selected_by_asset[metric.asset_id] = current_index
            if selected_on_date >= top_n:
                break
    return tuple(selected)


def _post_rank_rejection_reasons(
    candidate: LayeredCandidate,
    policy: LayeredSignalPolicy,
) -> tuple[str, ...]:
    metric = candidate.decision.metric
    available_reasons = set(candidate.state.confirmation_reasons)
    context_names = {*metric.strong_industry_names, *metric.strong_concept_names}
    if context_names.intersection(policy.blocked_context_names):
        available_reasons.add("blocked_risk_context")
    configured = set(policy.post_rank_no_refill_rejection_reasons)
    return tuple(sorted(available_reasons.intersection(configured)))
