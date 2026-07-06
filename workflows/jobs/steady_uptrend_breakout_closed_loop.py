"""Closed-loop workflow for steady uptrend breakout research candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from collections.abc import Mapping
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.l6_backtest_engine import load_evaluation_profile
from workflows.jobs import candidate_pool_equal_weight_benchmark
from workflows.jobs import steady_uptrend_breakout_event_backtest
from workflows.jobs import steady_uptrend_breakout_research_scan
from workflows.jobs import strategy_closed_loop_review
from workflows.jobs.support import write_json_payload

STAGE_BENCHMARK_KEYS = ("quality_pool", "trend_pool", "refined_pool", "signal_pool")


def build_parser() -> argparse.ArgumentParser:
    """Build parser for the steady-uptrend closed-loop workflow."""

    parser = argparse.ArgumentParser(prog="steady_uptrend_breakout_closed_loop")
    parser.add_argument("--evaluation-profile-path", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--kline-tsv-path", required=True)
    parser.add_argument("--scan-result-path")
    parser.add_argument("--weekly-kline-tsv-path")
    parser.add_argument("--stock-context-tsv-path")
    parser.add_argument("--start-date")
    parser.add_argument("--candidate-mode", choices=("breakout", "pre_breakout", "all"), default="all")
    parser.add_argument("--top-n-per-date", type=int)
    parser.add_argument("--target-status", default="test_tracking")
    parser.add_argument("--owner", default="stock_lobster")
    parser.add_argument("--description", default="Steady uptrend breakout closed-loop review.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run scan, strategy backtest, candidate-pool benchmark, and closed-loop review."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    profile = load_evaluation_profile(args.evaluation_profile_path)

    scan_result_path = Path(args.scan_result_path) if args.scan_result_path else output_root / "scan_result.json"
    if args.scan_result_path is None:
        _run_scan(args=args, output_path=scan_result_path)

    backtest_path = output_root / "event_backtest.json"
    benchmark_path = output_root / "candidate_pool_benchmark.json"
    review_path = output_root / "closed_loop_review.json"
    _run_event_backtest(args=args, profile=profile, scan_result_path=scan_result_path, output_path=backtest_path)
    _run_candidate_pool_benchmark(
        args=args,
        profile=profile,
        scan_result_path=scan_result_path,
        output_path=benchmark_path,
        candidate_pool_key="candidate_pool",
    )
    stage_benchmark_paths = _run_stage_benchmarks(
        args=args,
        profile=profile,
        scan_result_path=scan_result_path,
        output_root=output_root,
    )
    review_exit_code = strategy_closed_loop_review.main(
        [
            "--evaluation-profile-path",
            args.evaluation_profile_path,
            "--backtest-report-path",
            str(backtest_path),
            "--benchmark-report-path",
            str(benchmark_path),
            "--output-path",
            str(review_path),
            "--target-status",
            args.target_status,
            "--owner",
            args.owner,
            "--description",
            args.description,
        ]
    )
    summary_payload = {
        "schema_version": 1,
        "job_name": "steady_uptrend_breakout_closed_loop",
        "review_exit_code": review_exit_code,
        "evaluation_profile_path": args.evaluation_profile_path,
        "source_scan_result_path": str(scan_result_path),
        "kline_tsv_path": args.kline_tsv_path,
        "output_paths": {
            "scan_result": str(scan_result_path),
            "event_backtest": str(backtest_path),
            "candidate_pool_benchmark": str(benchmark_path),
            "stage_benchmarks": stage_benchmark_paths,
            "closed_loop_review": str(review_path),
        },
        "notes": (
            "v1 uses scanner candidate_pool/refined_pool as the primary benchmark input, "
            "keeps breakout_candidates as the strategy event input, and emits stage benchmarks "
            "for quality_pool, trend_pool, refined_pool, and signal_pool when available."
        ),
    }
    summary_path = output_root / "closed_loop_summary.json"
    write_json_payload(summary_path, summary_payload)
    print(
        json.dumps(
            {
                "summary_path": str(summary_path),
                "closed_loop_review_path": str(review_path),
                "review_exit_code": review_exit_code,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return review_exit_code


def _run_scan(args: argparse.Namespace, output_path: Path) -> None:
    scan_args = [
        "--kline-tsv-path",
        args.kline_tsv_path,
        "--output-path",
        str(output_path),
        "--candidate-mode",
        args.candidate_mode,
    ]
    if args.weekly_kline_tsv_path:
        scan_args.extend(["--weekly-kline-tsv-path", args.weekly_kline_tsv_path])
    if args.stock_context_tsv_path:
        scan_args.extend(["--stock-context-tsv-path", args.stock_context_tsv_path])
    if args.start_date:
        scan_args.extend(["--start-date", args.start_date])
    if args.top_n_per_date is not None:
        scan_args.extend(["--top-n-per-date", str(args.top_n_per_date)])
    exit_code = steady_uptrend_breakout_research_scan.main(scan_args)
    if exit_code != 0:
        raise RuntimeError(f"steady_uptrend_breakout_research_scan failed with exit code {exit_code}")


def _run_event_backtest(
    args: argparse.Namespace,
    profile: object,
    scan_result_path: Path,
    output_path: Path,
) -> None:
    backtest_args = [
        "--kline-tsv-path",
        args.kline_tsv_path,
        "--scan-result-path",
        str(scan_result_path),
        "--output-path",
        str(output_path),
        "--benchmark",
        profile.benchmark,
        "--strategy-id",
        profile.strategy_id,
        "--strategy-version",
        profile.strategy_version,
        "--entry-offset",
        str(profile.entry_offset),
        "--entry-price-field",
        profile.entry_price_field,
        "--exit-price-field",
        profile.exit_price_field,
    ]
    for horizon in profile.holding_horizons:
        backtest_args.extend(["--holding-horizon", str(horizon)])
    exit_code = steady_uptrend_breakout_event_backtest.main(backtest_args)
    if exit_code != 0:
        raise RuntimeError(f"steady_uptrend_breakout_event_backtest failed with exit code {exit_code}")


def _run_candidate_pool_benchmark(
    args: argparse.Namespace,
    profile: object,
    scan_result_path: Path,
    output_path: Path,
    candidate_pool_key: str,
) -> None:
    benchmark_definition = profile.benchmark_definition
    benchmark_id = (
        benchmark_definition.benchmark_id
        if benchmark_definition is not None
        else "candidate_pool_equal_weight_v1"
    )
    benchmark_args = [
        "--kline-tsv-path",
        args.kline_tsv_path,
        "--candidate-pool-path",
        str(scan_result_path),
        "--candidate-pool-key",
        candidate_pool_key,
        "--output-path",
        str(output_path),
        "--benchmark-id",
        benchmark_id,
        "--strategy-id",
        f"{profile.strategy_id}.candidate_pool_benchmark",
        "--strategy-version",
        profile.strategy_version,
        "--entry-offset",
        str(profile.entry_offset),
        "--entry-price-field",
        profile.entry_price_field,
        "--exit-price-field",
        profile.exit_price_field,
    ]
    for horizon in profile.holding_horizons:
        benchmark_args.extend(["--holding-horizon", str(horizon)])
    exit_code = candidate_pool_equal_weight_benchmark.main(benchmark_args)
    if exit_code != 0:
        raise RuntimeError(f"candidate_pool_equal_weight_benchmark failed with exit code {exit_code}")


def _run_stage_benchmarks(
    args: argparse.Namespace,
    profile: object,
    scan_result_path: Path,
    output_root: Path,
) -> dict[str, str]:
    available_stage_keys = _available_stage_keys(scan_result_path)
    stage_benchmark_paths: dict[str, str] = {}
    if not available_stage_keys:
        return stage_benchmark_paths
    benchmark_dir = output_root / "stage_benchmarks"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    for stage_key in STAGE_BENCHMARK_KEYS:
        if stage_key not in available_stage_keys:
            continue
        output_path = benchmark_dir / f"{stage_key}.json"
        _run_candidate_pool_benchmark(
            args=args,
            profile=profile,
            scan_result_path=scan_result_path,
            output_path=output_path,
            candidate_pool_key=stage_key,
        )
        stage_benchmark_paths[stage_key] = str(output_path)
    return stage_benchmark_paths


def _available_stage_keys(scan_result_path: Path) -> set[str]:
    payload = json.loads(scan_result_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        return set()
    stage_pools = payload.get("stage_candidate_pools")
    if not isinstance(stage_pools, Mapping):
        return set()
    return {str(key) for key in stage_pools}


if __name__ == "__main__":
    raise SystemExit(main())
