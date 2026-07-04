"""Job for running the full research workflow over breakout scanner candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.research import run_steady_uptrend_breakout_case
from stock_lobster.l6_backtest_engine import BacktestResult
from stock_lobster.research.trend_breakout_scan import TrendBreakoutMetrics
from workflows.jobs.support import write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build parser for the full research workflow job."""

    parser = argparse.ArgumentParser(prog="steady_uptrend_breakout_research_workflow")
    parser.add_argument("--scan-result-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--event-backtest-path")
    parser.add_argument("--holding-horizon", type=int, default=20)
    parser.add_argument("--max-cases", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the full research workflow on scanner candidates."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    payload = json.loads(Path(args.scan_result_path).read_text(encoding="utf-8"))
    candidates = payload.get("breakout_candidates", ())
    if args.max_cases is not None:
        candidates = candidates[: args.max_cases]
    backtest_result = (
        _backtest_result_from_event_report(args.event_backtest_path, args.holding_horizon)
        if args.event_backtest_path
        else None
    )

    cases = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("each breakout candidate must be a JSON object")
        result = run_steady_uptrend_breakout_case(
            _metrics_from_mapping(candidate),
            backtest_result=backtest_result,
        )
        cases.append(_result_to_mapping(result))

    output_payload = {
        "schema_version": 1,
        "workflow": "steady_uptrend_breakout_research_workflow",
        "source_scan_result_path": args.scan_result_path,
        "event_backtest_path": args.event_backtest_path,
        "holding_horizon": args.holding_horizon,
        "case_count": len(cases),
        "cases": cases,
    }
    write_json_payload(args.output_path, output_payload)
    print(json.dumps({"output_path": args.output_path, "case_count": len(cases)}, indent=2))
    return 0


def _metrics_from_mapping(payload: Mapping[str, object]) -> TrendBreakoutMetrics:
    return TrendBreakoutMetrics(
        asset_id=str(payload["asset_id"]),
        trade_date=str(payload["trade_date"]),
        close=float(payload["close"]),
        ma5=float(payload["ma5"]),
        ma10=float(payload["ma10"]),
        ma20=float(payload["ma20"]),
        ma60=float(payload["ma60"]),
        ma120=float(payload["ma120"]),
        ma20_slope_20d=float(payload["ma20_slope_20d"]),
        amount_ratio_20d=float(payload["amount_ratio_20d"]),
        max_drawdown_60d=float(payload["max_drawdown_60d"]),
        convergence_5_10_20_pct=float(payload["convergence_5_10_20_pct"]),
        close_new_high_60d_flag=bool(payload["close_new_high_60d_flag"]),
        steady_uptrend=bool(payload["steady_uptrend"]),
        breakout_watch=bool(payload["breakout_watch"]),
    )


def _backtest_result_from_event_report(path: str, holding_horizon: int) -> BacktestResult:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    reports = payload.get("reports", ())
    for report in reports:
        if not isinstance(report, Mapping):
            continue
        result_payload = report.get("result")
        if not isinstance(result_payload, Mapping):
            continue
        if int(result_payload["holding_horizon"]) != holding_horizon:
            continue
        return BacktestResult(
            strategy_id=str(result_payload["strategy_id"]),
            strategy_version=str(result_payload["strategy_version"]),
            backtest_period=(
                str(result_payload["backtest_period"][0]),
                str(result_payload["backtest_period"][1]),
            ),
            benchmark=str(result_payload["benchmark"]),
            holding_horizon=int(result_payload["holding_horizon"]),
            return_metrics={
                str(key): float(value)
                for key, value in dict(result_payload["return_metrics"]).items()
            },
            drawdown_metrics={
                str(key): float(value)
                for key, value in dict(result_payload["drawdown_metrics"]).items()
            },
            win_rate=float(result_payload["win_rate"]),
            sample_size=int(result_payload["sample_size"]),
            failure_cases=tuple(str(item) for item in result_payload.get("failure_cases", ())),
        )
    raise ValueError(f"holding horizon {holding_horizon} not found in {path}")


def _result_to_mapping(result) -> dict[str, object]:
    return {
        "case_id": result.pattern_case.case_id,
        "stock_code": result.pattern_case.stock_code,
        "case_date": result.pattern_case.case_date,
        "primitive_assessments": [
            {
                "primitive_id": item.primitive_id,
                "version": item.version,
                "value": item.value,
            }
            for item in result.primitive_assessments
        ],
        "label_assessments": [
            {
                "label_id": item.label_id,
                "version": item.version,
                "matched": item.matched,
            }
            for item in result.label_assessments
        ],
        "experience_build_plan": {
            "has_gaps": result.experience_build_plan.has_gaps,
            "primitive_requirement_count": len(result.experience_build_plan.primitive_requirements),
            "label_requirement_count": len(result.experience_build_plan.label_requirements),
            "threshold_questions": list(result.experience_build_plan.threshold_questions),
        },
        "strategy": {
            "strategy_id": result.strategy.strategy_id,
            "version": result.strategy.version,
            "status": result.strategy.status,
            "label_fields": list(result.strategy.label_fields),
        },
        "backtest_decision": {
            "passed": result.backtest_decision.passed,
            "status": result.backtest_decision.status,
            "reasons": list(result.backtest_decision.reasons),
            "failed_conditions": list(result.backtest_decision.failed_conditions),
        },
        "next_actions": list(result.next_actions),
    }


if __name__ == "__main__":
    raise SystemExit(main())
