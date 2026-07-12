"""Backtest evaluation profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class BacktestAcceptancePolicy:
    """Acceptance gates for one backtest profile."""

    min_sample_size: int = 0
    min_win_rate: float | None = None
    min_avg_return: float | None = None
    min_median_return: float | None = None
    min_excess_avg_return: float | None = None
    min_excess_annual_return: float | None = None
    return_metric_name: str = "annual_return"
    min_return_metric: float | None = None
    drawdown_metric_name: str = "max_drawdown"
    max_abs_drawdown: float | None = None
    min_tracking_days: int = 0
    min_dry_run_success_days: int = 0
    require_failure_cases_reviewed: bool = False
    require_user_approval: bool = True

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "BacktestAcceptancePolicy":
        """Build an acceptance policy from a JSON-friendly mapping."""

        return cls(
            min_sample_size=int(payload.get("min_sample_size", 0)),
            min_win_rate=_optional_float(payload.get("min_win_rate")),
            min_avg_return=_optional_float(payload.get("min_avg_return")),
            min_median_return=_optional_float(payload.get("min_median_return")),
            min_excess_avg_return=_optional_float(payload.get("min_excess_avg_return")),
            min_excess_annual_return=_optional_float(payload.get("min_excess_annual_return")),
            return_metric_name=str(payload.get("return_metric_name", "annual_return")),
            min_return_metric=_optional_float(payload.get("min_return_metric")),
            drawdown_metric_name=str(payload.get("drawdown_metric_name", "max_drawdown")),
            max_abs_drawdown=_optional_float(payload.get("max_abs_drawdown")),
            min_tracking_days=int(payload.get("min_tracking_days", 0)),
            min_dry_run_success_days=int(payload.get("min_dry_run_success_days", 0)),
            require_failure_cases_reviewed=bool(payload.get("require_failure_cases_reviewed", False)),
            require_user_approval=bool(payload.get("require_user_approval", True)),
        )

    def to_mapping(self) -> dict[str, object]:
        """Render this policy as a JSON-friendly mapping."""

        return {
            "min_sample_size": self.min_sample_size,
            "min_win_rate": self.min_win_rate,
            "min_avg_return": self.min_avg_return,
            "min_median_return": self.min_median_return,
            "min_excess_avg_return": self.min_excess_avg_return,
            "min_excess_annual_return": self.min_excess_annual_return,
            "return_metric_name": self.return_metric_name,
            "min_return_metric": self.min_return_metric,
            "drawdown_metric_name": self.drawdown_metric_name,
            "max_abs_drawdown": self.max_abs_drawdown,
            "min_tracking_days": self.min_tracking_days,
            "min_dry_run_success_days": self.min_dry_run_success_days,
            "require_failure_cases_reviewed": self.require_failure_cases_reviewed,
            "require_user_approval": self.require_user_approval,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkDefinition:
    """Deterministic benchmark calculation policy for one evaluation profile."""

    benchmark_id: str
    universe: str
    weighting: str
    rebalance: str
    entry_rule: str
    exit_rule: str
    missing_price_policy: str
    suspended_or_untradable_entry_policy: str
    limit_up_entry_policy: str
    notes: str = ""

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "BenchmarkDefinition":
        """Build a benchmark definition from a JSON-friendly mapping."""

        return cls(
            benchmark_id=str(payload["benchmark_id"]),
            universe=str(payload["universe"]),
            weighting=str(payload["weighting"]),
            rebalance=str(payload["rebalance"]),
            entry_rule=str(payload["entry_rule"]),
            exit_rule=str(payload["exit_rule"]),
            missing_price_policy=str(payload["missing_price_policy"]),
            suspended_or_untradable_entry_policy=str(payload["suspended_or_untradable_entry_policy"]),
            limit_up_entry_policy=str(payload["limit_up_entry_policy"]),
            notes=str(payload.get("notes", "")),
        )

    def to_mapping(self) -> dict[str, object]:
        """Render this definition as a JSON-friendly mapping."""

        return {
            "benchmark_id": self.benchmark_id,
            "universe": self.universe,
            "weighting": self.weighting,
            "rebalance": self.rebalance,
            "entry_rule": self.entry_rule,
            "exit_rule": self.exit_rule,
            "missing_price_policy": self.missing_price_policy,
            "suspended_or_untradable_entry_policy": self.suspended_or_untradable_entry_policy,
            "limit_up_entry_policy": self.limit_up_entry_policy,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class EvaluationProfile:
    """Configurable backtest profile tied to a strategy version."""

    profile_id: str
    benchmark: str
    holding_horizons: tuple[int, ...]
    selection_frequency: str
    comparison_benchmarks: tuple[str, ...] = ()
    benchmark_definition: BenchmarkDefinition | None = None
    strategy_id: str = ""
    strategy_version: str = ""
    primary_holding_horizon: int | None = None
    entry_offset: int = 1
    entry_price_field: str = "open"
    exit_price_field: str = "close"
    acceptance_policy: BacktestAcceptancePolicy = field(default_factory=BacktestAcceptancePolicy)
    lifecycle_gates: Mapping[str, BacktestAcceptancePolicy] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "EvaluationProfile":
        """Build an evaluation profile from a JSON-friendly mapping."""

        raw_horizons = payload.get("holding_horizons", ())
        holding_horizons = tuple(int(item) for item in raw_horizons)
        if not holding_horizons:
            raise ValueError("holding_horizons must not be empty")
        raw_primary_horizon = payload.get("primary_holding_horizon")
        primary_holding_horizon = int(raw_primary_horizon) if raw_primary_horizon is not None else holding_horizons[0]
        if primary_holding_horizon not in holding_horizons:
            raise ValueError("primary_holding_horizon must be included in holding_horizons")
        raw_policy = payload.get("acceptance_policy", {})
        if not isinstance(raw_policy, Mapping):
            raise ValueError("acceptance_policy must be a JSON object")
        raw_lifecycle_gates = payload.get("lifecycle_gates", {})
        if not isinstance(raw_lifecycle_gates, Mapping):
            raise ValueError("lifecycle_gates must be a JSON object")
        raw_benchmark_definition = payload.get("benchmark_definition")
        if raw_benchmark_definition is not None and not isinstance(raw_benchmark_definition, Mapping):
            raise ValueError("benchmark_definition must be a JSON object")
        return cls(
            profile_id=str(payload["profile_id"]),
            benchmark=str(payload["benchmark"]),
            holding_horizons=holding_horizons,
            selection_frequency=str(payload["selection_frequency"]),
            comparison_benchmarks=tuple(str(item) for item in payload.get("comparison_benchmarks", ())),
            benchmark_definition=(
                BenchmarkDefinition.from_mapping(raw_benchmark_definition)
                if raw_benchmark_definition is not None
                else None
            ),
            strategy_id=str(payload.get("strategy_id", "")),
            strategy_version=str(payload.get("strategy_version", "")),
            primary_holding_horizon=primary_holding_horizon,
            entry_offset=int(payload.get("entry_offset", 1)),
            entry_price_field=str(payload.get("entry_price_field", "open")),
            exit_price_field=str(payload.get("exit_price_field", "close")),
            acceptance_policy=BacktestAcceptancePolicy.from_mapping(raw_policy),
            lifecycle_gates={
                str(status): BacktestAcceptancePolicy.from_mapping(values)
                for status, values in raw_lifecycle_gates.items()
                if isinstance(values, Mapping)
            },
        )

    def acceptance_policy_for(self, target_status: str) -> BacktestAcceptancePolicy:
        """Return the lifecycle gate for a target status, falling back to the default policy."""

        return self.lifecycle_gates.get(target_status, self.acceptance_policy)

    def to_mapping(self) -> dict[str, object]:
        """Render this profile as a JSON-friendly mapping."""

        return {
            "profile_id": self.profile_id,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "benchmark": self.benchmark,
            "comparison_benchmarks": list(self.comparison_benchmarks),
            "benchmark_definition": (
                self.benchmark_definition.to_mapping()
                if self.benchmark_definition is not None
                else None
            ),
            "holding_horizons": list(self.holding_horizons),
            "primary_holding_horizon": self.primary_holding_horizon,
            "selection_frequency": self.selection_frequency,
            "entry_offset": self.entry_offset,
            "entry_price_field": self.entry_price_field,
            "exit_price_field": self.exit_price_field,
            "acceptance_policy": self.acceptance_policy.to_mapping(),
            "lifecycle_gates": {
                status: policy.to_mapping()
                for status, policy in self.lifecycle_gates.items()
            },
        }


def load_evaluation_profile(path: str | Path) -> EvaluationProfile:
    """Load one evaluation profile JSON file."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return EvaluationProfile.from_mapping(payload)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
