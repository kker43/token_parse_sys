"""Production-promotion review for research-derived artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class PromotionThresholds:
    """Thresholds for one target promotion status."""

    min_positive_sample_count: int = 0
    min_negative_sample_count: int = 0
    min_backtest_sample_size: int = 0
    min_backtest_win_rate: float | None = None
    min_backtest_annual_return: float | None = None
    max_abs_backtest_drawdown: float | None = None
    min_dependency_count: int = 0
    require_quality_monitoring_ready: bool = False
    require_missing_data_policy_ready: bool = False
    require_no_future_data_check_ready: bool = False


@dataclass(frozen=True, slots=True)
class PromotionPolicy:
    """Production-promotion policy."""

    policy_id: str
    thresholds: Mapping[str, PromotionThresholds]


@dataclass(frozen=True, slots=True)
class PromotionEvidence:
    """Evidence for one artifact promotion review."""

    artifact_id: str
    artifact_type: str
    current_status: str
    target_status: str
    owner: str
    description: str
    dependency_count: int = 0
    dependent_workflows: tuple[str, ...] = field(default_factory=tuple)
    positive_sample_count: int = 0
    negative_sample_count: int = 0
    backtest_sample_size: int = 0
    backtest_win_rate: float = 0.0
    backtest_annual_return: float = 0.0
    backtest_max_drawdown: float = 0.0
    threshold_stability: str = "unknown"
    calculation_cost: str = "unknown"
    quality_monitoring_ready: bool = False
    missing_data_policy_ready: bool = False
    no_future_data_check_ready: bool = False
    failure_case_count: int = 0
    notes: str = ""


@dataclass(frozen=True, slots=True)
class PromotionReviewResult:
    """Deterministic production-promotion review result."""

    artifact_id: str
    target_status: str
    recommendation: str
    passed: bool
    failed_conditions: tuple[str, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_mapping(self) -> dict[str, object]:
        """Render this result as a JSON-friendly mapping."""

        return {
            "artifact_id": self.artifact_id,
            "target_status": self.target_status,
            "recommendation": self.recommendation,
            "passed": self.passed,
            "failed_conditions": list(self.failed_conditions),
            "warnings": list(self.warnings),
        }


def load_promotion_policy(path: str | Path) -> PromotionPolicy:
    """Load a promotion policy JSON file."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    thresholds = {
        str(status): PromotionThresholds(**dict(values))
        for status, values in dict(payload.get("thresholds", {})).items()
    }
    return PromotionPolicy(policy_id=str(payload["policy_id"]), thresholds=thresholds)


def load_promotion_evidence(path: str | Path) -> PromotionEvidence:
    """Load a promotion evidence JSON file."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PromotionEvidence(
        artifact_id=str(payload["artifact_id"]),
        artifact_type=str(payload["artifact_type"]),
        current_status=str(payload["current_status"]),
        target_status=str(payload["target_status"]),
        owner=str(payload["owner"]),
        description=str(payload["description"]),
        dependency_count=int(payload.get("dependency_count", 0)),
        dependent_workflows=tuple(str(item) for item in payload.get("dependent_workflows", ())),
        positive_sample_count=int(payload.get("positive_sample_count", 0)),
        negative_sample_count=int(payload.get("negative_sample_count", 0)),
        backtest_sample_size=int(payload.get("backtest_sample_size", 0)),
        backtest_win_rate=float(payload.get("backtest_win_rate", 0.0)),
        backtest_annual_return=float(payload.get("backtest_annual_return", 0.0)),
        backtest_max_drawdown=float(payload.get("backtest_max_drawdown", 0.0)),
        threshold_stability=str(payload.get("threshold_stability", "unknown")),
        calculation_cost=str(payload.get("calculation_cost", "unknown")),
        quality_monitoring_ready=bool(payload.get("quality_monitoring_ready", False)),
        missing_data_policy_ready=bool(payload.get("missing_data_policy_ready", False)),
        no_future_data_check_ready=bool(payload.get("no_future_data_check_ready", False)),
        failure_case_count=int(payload.get("failure_case_count", 0)),
        notes=str(payload.get("notes", "")),
    )


def review_promotion(
    evidence: PromotionEvidence,
    policy: PromotionPolicy,
) -> PromotionReviewResult:
    """Review whether an artifact should be promoted."""

    thresholds = policy.thresholds.get(evidence.target_status)
    if thresholds is None:
        raise ValueError(f"unknown target_status: {evidence.target_status}")

    failed_conditions: list[str] = []
    warnings: list[str] = []
    _check_minimum(failed_conditions, "positive_sample_count", evidence.positive_sample_count, thresholds.min_positive_sample_count)
    _check_minimum(failed_conditions, "negative_sample_count", evidence.negative_sample_count, thresholds.min_negative_sample_count)
    _check_minimum(failed_conditions, "backtest_sample_size", evidence.backtest_sample_size, thresholds.min_backtest_sample_size)
    _check_minimum(failed_conditions, "dependency_count", evidence.dependency_count, thresholds.min_dependency_count)

    if thresholds.min_backtest_win_rate is not None:
        _check_minimum(failed_conditions, "backtest_win_rate", evidence.backtest_win_rate, thresholds.min_backtest_win_rate)
    if thresholds.min_backtest_annual_return is not None:
        _check_minimum(
            failed_conditions,
            "backtest_annual_return",
            evidence.backtest_annual_return,
            thresholds.min_backtest_annual_return,
        )
    if thresholds.max_abs_backtest_drawdown is not None and abs(evidence.backtest_max_drawdown) > thresholds.max_abs_backtest_drawdown:
        failed_conditions.append(
            f"abs(backtest_max_drawdown) {abs(evidence.backtest_max_drawdown):.4f} > "
            f"{thresholds.max_abs_backtest_drawdown:.4f}"
        )
    if thresholds.require_quality_monitoring_ready and not evidence.quality_monitoring_ready:
        failed_conditions.append("quality_monitoring_ready is false")
    if thresholds.require_missing_data_policy_ready and not evidence.missing_data_policy_ready:
        failed_conditions.append("missing_data_policy_ready is false")
    if thresholds.require_no_future_data_check_ready and not evidence.no_future_data_check_ready:
        failed_conditions.append("no_future_data_check_ready is false")

    if evidence.threshold_stability == "unknown":
        warnings.append("threshold stability is unknown")
    if evidence.failure_case_count == 0 and evidence.target_status != "candidate":
        warnings.append("failure cases are not recorded")

    passed = not failed_conditions
    return PromotionReviewResult(
        artifact_id=evidence.artifact_id,
        target_status=evidence.target_status,
        recommendation=_recommendation(evidence.target_status, passed),
        passed=passed,
        failed_conditions=tuple(failed_conditions),
        warnings=tuple(warnings),
    )


def _check_minimum(
    failed_conditions: list[str],
    field_name: str,
    value: int | float,
    minimum: int | float,
) -> None:
    if value < minimum:
        failed_conditions.append(f"{field_name} {value} < {minimum}")


def _recommendation(target_status: str, passed: bool) -> str:
    if passed:
        if target_status == "candidate":
            return "promote_to_candidate"
        if target_status == "production_candidate":
            return "promote_to_production_candidate"
        if target_status == "approved_production":
            return "approve_production"
        return f"promote_to_{target_status}"
    if target_status == "candidate":
        return "keep_research_only"
    return "keep_current_status"
