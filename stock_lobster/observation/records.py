"""Observation records for strategy test tracking."""

from __future__ import annotations

from dataclasses import dataclass, field

from stock_lobster.l6_backtest_engine.profiles import EvaluationProfile

OBSERVATION_STATUSES = {
    "pending_approval",
    "test_tracking",
    "active_production",
    "paused",
    "retired",
}


@dataclass(frozen=True, slots=True)
class ObservationRecord:
    """Versioned record describing one strategy observation lifecycle entry."""

    observation_id: str
    strategy_id: str
    strategy_version: str
    lifecycle_status: str
    approval_status: str
    source_evidence_id: str
    evaluation_profile_id: str
    benchmark: str
    review_frequency: str
    review_horizons: tuple[int, ...]
    comparison_benchmarks: tuple[str, ...] = field(default_factory=tuple)
    promotion_blockers: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""

    def __post_init__(self) -> None:
        if self.lifecycle_status not in OBSERVATION_STATUSES:
            raise ValueError(f"unsupported observation lifecycle_status: {self.lifecycle_status}")
        if self.lifecycle_status != "pending_approval" and self.approval_status != "approved":
            raise ValueError("non-pending observation records require approved approval_status")

    def to_mapping(self) -> dict[str, object]:
        """Render this record as a JSON-friendly mapping."""

        return {
            "observation_id": self.observation_id,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "lifecycle_status": self.lifecycle_status,
            "approval_status": self.approval_status,
            "source_evidence_id": self.source_evidence_id,
            "evaluation_profile_id": self.evaluation_profile_id,
            "benchmark": self.benchmark,
            "comparison_benchmarks": list(self.comparison_benchmarks),
            "review_frequency": self.review_frequency,
            "review_horizons": list(self.review_horizons),
            "promotion_blockers": list(self.promotion_blockers),
            "notes": self.notes,
        }


def build_pending_test_tracking_record(
    profile: EvaluationProfile,
    source_evidence_id: str,
    promotion_blockers: tuple[str, ...] = (),
) -> ObservationRecord:
    """Build a proposed observation record without granting approval."""

    strategy_id = profile.strategy_id or "unknown_strategy"
    strategy_version = profile.strategy_version or "unknown_version"
    return ObservationRecord(
        observation_id=f"observation.{strategy_id}.{strategy_version}.test_tracking",
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        lifecycle_status="pending_approval",
        approval_status="pending_user_approval",
        source_evidence_id=source_evidence_id,
        evaluation_profile_id=profile.profile_id,
        benchmark=profile.benchmark,
        comparison_benchmarks=profile.comparison_benchmarks,
        review_frequency=profile.selection_frequency,
        review_horizons=profile.holding_horizons,
        promotion_blockers=promotion_blockers,
        notes="Pending user approval; this record is a proposal and has not entered observation.",
    )
