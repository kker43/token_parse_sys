"""Backtest evidence builders for strategy lifecycle reviews."""

from __future__ import annotations

from dataclasses import dataclass, field

from stock_lobster.l6_backtest_engine.profiles import BacktestAcceptancePolicy, EvaluationProfile
from stock_lobster.l6_backtest_engine.result import BacktestResult


@dataclass(frozen=True, slots=True)
class BacktestGateReview:
    """Deterministic result of applying an acceptance gate to a backtest."""

    holding_horizon: int
    passed: bool
    failed_conditions: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_mapping(self) -> dict[str, object]:
        """Render this review as a JSON-friendly mapping."""

        return {
            "holding_horizon": self.holding_horizon,
            "passed": self.passed,
            "failed_conditions": list(self.failed_conditions),
            "warnings": list(self.warnings),
        }


def review_backtest_result(
    result: BacktestResult,
    acceptance_policy: BacktestAcceptancePolicy,
    relative_metrics: Mapping[str, float] | None = None,
) -> BacktestGateReview:
    """Review one L6 backtest result against an acceptance policy."""

    failed_conditions: list[str] = []
    warnings: list[str] = []

    if result.sample_size < acceptance_policy.min_sample_size:
        failed_conditions.append(
            f"sample_size {result.sample_size} < {acceptance_policy.min_sample_size}"
        )
    if acceptance_policy.min_win_rate is not None and result.win_rate < acceptance_policy.min_win_rate:
        failed_conditions.append(
            f"win_rate {result.win_rate:.4f} < {acceptance_policy.min_win_rate:.4f}"
        )
    if acceptance_policy.min_avg_return is not None:
        avg_return = float(result.return_metrics.get("avg_return", 0.0))
        if avg_return < acceptance_policy.min_avg_return:
            failed_conditions.append(f"avg_return {avg_return:.4f} < {acceptance_policy.min_avg_return:.4f}")
    if acceptance_policy.min_median_return is not None:
        median_return = float(result.return_metrics.get("median_return", 0.0))
        if median_return < acceptance_policy.min_median_return:
            failed_conditions.append(
                f"median_return {median_return:.4f} < {acceptance_policy.min_median_return:.4f}"
            )
    if acceptance_policy.min_return_metric is not None:
        return_value = float(result.return_metrics.get(acceptance_policy.return_metric_name, 0.0))
        if return_value < acceptance_policy.min_return_metric:
            failed_conditions.append(
                f"{acceptance_policy.return_metric_name} {return_value:.4f} < "
                f"{acceptance_policy.min_return_metric:.4f}"
            )
    if acceptance_policy.max_abs_drawdown is not None:
        drawdown_value = float(result.drawdown_metrics.get(acceptance_policy.drawdown_metric_name, 0.0))
        if abs(drawdown_value) > acceptance_policy.max_abs_drawdown:
            failed_conditions.append(
                f"abs({acceptance_policy.drawdown_metric_name}) {abs(drawdown_value):.4f} > "
                f"{acceptance_policy.max_abs_drawdown:.4f}"
            )
    if acceptance_policy.min_excess_avg_return is not None:
        if relative_metrics is None:
            failed_conditions.append("excess_avg_return is missing")
        elif relative_metrics.get("excess_avg_return", 0.0) < acceptance_policy.min_excess_avg_return:
            failed_conditions.append(
                f"excess_avg_return {relative_metrics.get('excess_avg_return', 0.0):.4f} < "
                f"{acceptance_policy.min_excess_avg_return:.4f}"
            )
    if acceptance_policy.min_excess_annual_return is not None:
        if relative_metrics is None:
            failed_conditions.append("excess_annual_return is missing")
        elif relative_metrics.get("excess_annual_return", 0.0) < acceptance_policy.min_excess_annual_return:
            failed_conditions.append(
                f"excess_annual_return {relative_metrics.get('excess_annual_return', 0.0):.4f} < "
                f"{acceptance_policy.min_excess_annual_return:.4f}"
            )
    if acceptance_policy.min_tracking_days:
        warnings.append(f"tracking days gate requires observation history: {acceptance_policy.min_tracking_days}")
    if acceptance_policy.min_dry_run_success_days:
        warnings.append(f"dry-run success days gate requires run history: {acceptance_policy.min_dry_run_success_days}")
    if acceptance_policy.require_failure_cases_reviewed:
        warnings.append("failure case review requires human-reviewed ReviewFinding records")
    if acceptance_policy.require_user_approval:
        warnings.append("user approval is required before lifecycle promotion")

    if not result.failure_cases:
        warnings.append("failure cases are not recorded")

    return BacktestGateReview(
        holding_horizon=result.holding_horizon,
        passed=not failed_conditions,
        failed_conditions=tuple(failed_conditions),
        warnings=tuple(warnings),
    )


def build_promotion_evidence_mapping(
    result: BacktestResult,
    profile: EvaluationProfile,
    target_status: str,
    owner: str,
    description: str,
    positive_sample_count: int = 0,
    negative_sample_count: int = 0,
    dependency_count: int = 0,
    dependent_workflows: tuple[str, ...] = (),
    threshold_stability: str = "unknown",
    calculation_cost: str = "unknown",
    quality_monitoring_ready: bool = False,
    missing_data_policy_ready: bool = False,
    no_future_data_check_ready: bool = False,
) -> dict[str, object]:
    """Build a production-promotion evidence payload from one L6 result."""

    return {
        "schema_version": 1,
        "artifact_id": result.strategy_id,
        "artifact_type": "strategy",
        "current_status": "draft",
        "target_status": target_status,
        "owner": owner,
        "description": description,
        "evaluation_profile_id": profile.profile_id,
        "primary_benchmark": profile.benchmark,
        "comparison_benchmarks": list(profile.comparison_benchmarks),
        "benchmark_definition": (
            profile.benchmark_definition.to_mapping()
            if profile.benchmark_definition is not None
            else None
        ),
        "backtest_benchmark": result.benchmark,
        "evaluated_holding_horizon": result.holding_horizon,
        "dependency_count": dependency_count,
        "dependent_workflows": list(dependent_workflows),
        "positive_sample_count": positive_sample_count,
        "negative_sample_count": negative_sample_count,
        "backtest_sample_size": result.sample_size,
        "backtest_win_rate": result.win_rate,
        "backtest_annual_return": float(result.return_metrics.get("annual_return", 0.0)),
        "backtest_max_drawdown": float(result.drawdown_metrics.get("max_drawdown", 0.0)),
        "threshold_stability": threshold_stability,
        "calculation_cost": calculation_cost,
        "quality_monitoring_ready": quality_monitoring_ready,
        "missing_data_policy_ready": missing_data_policy_ready,
        "no_future_data_check_ready": no_future_data_check_ready,
        "failure_case_count": len(result.failure_cases),
        "notes": (
            "This evidence is generated from an L6 BacktestResult and is only a review input; "
            "it does not approve the strategy or enter observation automatically."
        ),
    }
