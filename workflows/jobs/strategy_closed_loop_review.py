"""Build a strategy closed-loop review package from L6 backtest output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.l6_backtest_engine import (
    BacktestResult,
    build_promotion_evidence_mapping,
    load_evaluation_profile,
    review_backtest_result,
)
from stock_lobster.observation import build_pending_test_tracking_record
from workflows.jobs.support import write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build parser for the closed-loop review job."""

    parser = argparse.ArgumentParser(prog="strategy_closed_loop_review")
    parser.add_argument("--evaluation-profile-path", required=True)
    parser.add_argument("--backtest-report-path", required=True)
    parser.add_argument("--benchmark-report-path")
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--target-status", default="test_tracking")
    parser.add_argument("--owner", default="stock_lobster")
    parser.add_argument("--description", default="Strategy closed-loop review evidence.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Build one closed-loop review package."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    profile = load_evaluation_profile(args.evaluation_profile_path)
    backtest_payload = _read_json_object(args.backtest_report_path)
    results = _read_backtest_results(backtest_payload)
    result_by_horizon = {result.holding_horizon: result for result in results}
    primary_horizon = profile.primary_holding_horizon
    if primary_horizon is None:
        primary_horizon = profile.holding_horizons[0]
    primary_result = result_by_horizon.get(primary_horizon)
    if primary_result is None:
        raise ValueError(f"missing backtest result for primary horizon: {primary_horizon}")
    benchmark_results: tuple[dict[str, object], ...] = ()
    primary_benchmark_result: dict[str, object] | None = None
    relative_metrics: dict[str, float] | None = None
    if args.benchmark_report_path:
        benchmark_payload = _read_json_object(args.benchmark_report_path)
        benchmark_results = _read_benchmark_results(benchmark_payload)
        primary_benchmark_result = _benchmark_result_for_horizon(benchmark_results, primary_horizon)
        if primary_benchmark_result is None:
            raise ValueError(f"missing benchmark result for primary horizon: {primary_horizon}")
        relative_metrics = _relative_metrics(primary_result, primary_benchmark_result)

    acceptance_policy = profile.acceptance_policy_for(args.target_status)
    reviews = tuple(
        review_backtest_result(
            result=result,
            acceptance_policy=acceptance_policy,
            relative_metrics=relative_metrics if result.holding_horizon == primary_horizon else None,
        )
        for result in sorted(results, key=lambda item: item.holding_horizon)
    )
    primary_review = next(review for review in reviews if review.holding_horizon == primary_horizon)
    evidence_id = f"{primary_result.strategy_id}.{primary_result.strategy_version}.{profile.profile_id}"
    evidence = build_promotion_evidence_mapping(
        result=primary_result,
        profile=profile,
        target_status=args.target_status,
        owner=args.owner,
        description=args.description,
        positive_sample_count=primary_result.sample_size,
        negative_sample_count=len(primary_result.failure_cases),
        dependency_count=1,
        dependent_workflows=("steady_uptrend_breakout_event_backtest",),
        threshold_stability="unknown",
        calculation_cost="low",
        no_future_data_check_ready=True,
    )
    if relative_metrics is not None:
        evidence["benchmark_relative_metrics"] = relative_metrics
    blockers = tuple(primary_review.failed_conditions)
    observation_record = build_pending_test_tracking_record(
        profile=profile,
        source_evidence_id=evidence_id,
        promotion_blockers=blockers,
    )
    recommendation = (
        "ready_for_user_review_to_enter_test_tracking"
        if primary_review.passed
        else "keep_current_status_and_expand_samples"
    )
    payload = {
        "schema_version": 1,
        "job_name": "strategy_closed_loop_review",
        "evaluation_profile": profile.to_mapping(),
        "source_backtest_report_path": args.backtest_report_path,
        "source_benchmark_report_path": args.benchmark_report_path,
        "primary_holding_horizon": primary_horizon,
        "target_status": args.target_status,
        "acceptance_policy": acceptance_policy.to_mapping(),
        "primary_benchmark_result": primary_benchmark_result,
        "benchmark_relative_metrics": relative_metrics,
        "benchmark_results": list(benchmark_results),
        "gate_reviews": [review.to_mapping() for review in reviews],
        "primary_gate_passed": primary_review.passed,
        "recommendation": recommendation,
        "promotion_evidence": evidence,
        "proposed_observation_record": observation_record.to_mapping(),
    }
    write_json_payload(args.output_path, payload)
    print(
        json.dumps(
            {
                "output_path": args.output_path,
                "primary_gate_passed": primary_review.passed,
                "recommendation": recommendation,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if primary_review.passed else 1


def _read_json_object(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return dict(payload)


def _read_backtest_results(payload: Mapping[str, object]) -> tuple[BacktestResult, ...]:
    raw_reports = payload.get("reports", ())
    results: list[BacktestResult] = []
    for raw_report in raw_reports:
        if not isinstance(raw_report, Mapping):
            raise ValueError("each report must be a JSON object")
        raw_result = raw_report.get("result")
        if not isinstance(raw_result, Mapping):
            raise ValueError("each report must contain a result object")
        results.append(_result_from_mapping(raw_result))
    if not results:
        raise ValueError("backtest report payload must contain at least one report")
    return tuple(results)


def _read_benchmark_results(payload: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    raw_results = payload.get("benchmark_results")
    if raw_results is None:
        raw_results = payload.get("reports", ())
    results: list[dict[str, object]] = []
    for raw_result in raw_results:
        if not isinstance(raw_result, Mapping):
            raise ValueError("each benchmark result must be a JSON object")
        results.append(dict(raw_result))
    if not results:
        raise ValueError("benchmark report payload must contain at least one benchmark result")
    return tuple(results)


def _benchmark_result_for_horizon(
    benchmark_results: tuple[dict[str, object], ...],
    holding_horizon: int,
) -> dict[str, object] | None:
    for result in benchmark_results:
        if int(result["holding_horizon"]) == holding_horizon:
            return result
    return None


def _relative_metrics(
    strategy_result: BacktestResult,
    benchmark_result: Mapping[str, object],
) -> dict[str, float]:
    raw_benchmark_returns = benchmark_result.get("return_metrics", {})
    raw_benchmark_drawdowns = benchmark_result.get("drawdown_metrics", {})
    if not isinstance(raw_benchmark_returns, Mapping):
        raise ValueError("benchmark return_metrics must be a JSON object")
    if not isinstance(raw_benchmark_drawdowns, Mapping):
        raise ValueError("benchmark drawdown_metrics must be a JSON object")
    strategy_avg_return = float(strategy_result.return_metrics.get("avg_return", 0.0))
    strategy_annual_return = float(strategy_result.return_metrics.get("annual_return", 0.0))
    benchmark_avg_return = float(raw_benchmark_returns.get("avg_signal_date_return", 0.0))
    benchmark_annual_return = float(raw_benchmark_returns.get("annual_return", 0.0))
    strategy_max_drawdown = float(strategy_result.drawdown_metrics.get("max_drawdown", 0.0))
    benchmark_max_drawdown = float(raw_benchmark_drawdowns.get("max_signal_date_drawdown", 0.0))
    return {
        "excess_avg_return": strategy_avg_return - benchmark_avg_return,
        "excess_annual_return": strategy_annual_return - benchmark_annual_return,
        "drawdown_gap": strategy_max_drawdown - benchmark_max_drawdown,
    }


def _result_from_mapping(payload: Mapping[str, object]) -> BacktestResult:
    raw_period = payload.get("backtest_period", ("", ""))
    period_items = tuple(str(item) for item in raw_period)
    if len(period_items) != 2:
        raise ValueError("backtest_period must contain start and end")
    raw_return_metrics = payload.get("return_metrics", {})
    raw_drawdown_metrics = payload.get("drawdown_metrics", {})
    if not isinstance(raw_return_metrics, Mapping):
        raise ValueError("return_metrics must be a JSON object")
    if not isinstance(raw_drawdown_metrics, Mapping):
        raise ValueError("drawdown_metrics must be a JSON object")
    return BacktestResult(
        strategy_id=str(payload["strategy_id"]),
        strategy_version=str(payload["strategy_version"]),
        backtest_period=(period_items[0], period_items[1]),
        benchmark=str(payload["benchmark"]),
        holding_horizon=int(payload["holding_horizon"]),
        return_metrics={str(key): float(value) for key, value in raw_return_metrics.items()},
        drawdown_metrics={str(key): float(value) for key, value in raw_drawdown_metrics.items()},
        win_rate=float(payload["win_rate"]),
        sample_size=int(payload["sample_size"]),
        failure_cases=tuple(str(item) for item in payload.get("failure_cases", ())),
    )


if __name__ == "__main__":
    raise SystemExit(main())
