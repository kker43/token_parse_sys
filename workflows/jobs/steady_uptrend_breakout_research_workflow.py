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
        ma30=float(payload["ma30"]),
        ma60=float(payload["ma60"]),
        ma120=float(payload["ma120"]),
        ma20_slope_20d=float(payload["ma20_slope_20d"]),
        amount_ratio_20d=float(payload["amount_ratio_20d"]),
        max_drawdown_60d=float(payload["max_drawdown_60d"]),
        max_drawdown_120d=float(payload["max_drawdown_120d"]),
        convergence_5_10_20_pct=float(payload["convergence_5_10_20_pct"]),
        close_to_high_60d_pct=float(payload.get("close_to_high_60d_pct", 0.0)),
        ma20_deviation_pct=float(payload.get("ma20_deviation_pct", 0.0)),
        ma30_deviation_pct=float(payload.get("ma30_deviation_pct", 0.0)),
        ma30_hold_ratio_30d=float(payload.get("ma30_hold_ratio_30d", 0.0)),
        ma30_hold_ratio_60d=float(payload.get("ma30_hold_ratio_60d", 0.0)),
        ma30_hold_ratio_90d=float(payload.get("ma30_hold_ratio_90d", 0.0)),
        ma30_hold_ratio_120d=float(payload.get("ma30_hold_ratio_120d", 0.0)),
        ma60_hold_ratio_120d=float(payload.get("ma60_hold_ratio_120d", 0.0)),
        return_20d=float(payload.get("return_20d", 0.0)),
        red_k_ratio_20d=float(payload["red_k_ratio_20d"]),
        green_k_ratio_20d=float(payload["green_k_ratio_20d"]),
        long_shadow_ratio_20d=float(payload["long_shadow_ratio_20d"]),
        large_bearish_body_ratio_20d=float(payload.get("large_bearish_body_ratio_20d", 0.0)),
        max_consecutive_green_k_20d=int(payload.get("max_consecutive_green_k_20d", 0)),
        single_bull_bar_return_share_20d=float(payload.get("single_bull_bar_return_share_20d", 0.0)),
        impulse_consolidation_days=int(payload.get("impulse_consolidation_days", 0)),
        ma5_10_20_30_convergence_pct=float(payload.get("ma5_10_20_30_convergence_pct", 0.0)),
        avg_amount_20d=float(payload.get("avg_amount_20d", 0.0)),
        close_new_high_60d_flag=bool(payload["close_new_high_60d_flag"]),
        daily_quality_pass=bool(payload["daily_quality_pass"]),
        trend_stability_pass=bool(payload.get("trend_stability_pass", True)),
        weak_shape_pass=bool(payload.get("weak_shape_pass", True)),
        market_cap_liquidity_pass=bool(payload.get("market_cap_liquidity_pass", True)),
        turnover_quality_pass=bool(payload.get("turnover_quality_pass", True)),
        context_strength_pass=bool(payload.get("context_strength_pass", True)),
        steady_uptrend=bool(payload["steady_uptrend"]),
        pre_breakout_watch=bool(payload.get("pre_breakout_watch", False)),
        breakout_watch=bool(payload["breakout_watch"]),
        setup_score=float(payload.get("setup_score", 0.0)),
        weekly_asof_trade_date=(
            str(payload["weekly_asof_trade_date"])
            if payload.get("weekly_asof_trade_date") is not None
            else None
        ),
        weekly_close=_optional_float(payload.get("weekly_close")),
        weekly_ma5=_optional_float(payload.get("weekly_ma5")),
        weekly_ma10=_optional_float(payload.get("weekly_ma10")),
        weekly_ma20=_optional_float(payload.get("weekly_ma20")),
        weekly_ma20_slope_4w=_optional_float(payload.get("weekly_ma20_slope_4w")),
        weekly_max_drawdown_26w=_optional_float(payload.get("weekly_max_drawdown_26w")),
        weekly_trend_pass=bool(payload.get("weekly_trend_pass", True)),
    )


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


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
