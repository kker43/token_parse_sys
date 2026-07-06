"""Job for scanning steady uptrend breakout research candidates from kline TSV."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.research import (
    TrendBreakoutScanPolicy,
    read_kline_tsv,
    read_stock_signal_context_tsv,
    scan_trend_breakouts,
    select_candidates,
    summarize_breakout_scan,
)
from workflows.jobs.support import write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build parser for the research scanner."""

    parser = argparse.ArgumentParser(prog="steady_uptrend_breakout_research_scan")
    parser.add_argument("--kline-tsv-path", required=True)
    parser.add_argument("--weekly-kline-tsv-path")
    parser.add_argument("--stock-context-tsv-path")
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--start-date")
    parser.add_argument("--min-amount-ratio-20d", type=float, default=1.5)
    parser.add_argument("--max-abs-drawdown-60d", type=float, default=0.40)
    parser.add_argument("--max-abs-drawdown-120d", type=float, default=0.55)
    parser.add_argument("--min-red-k-ratio-20d", type=float, default=0.45)
    parser.add_argument("--max-long-shadow-ratio-20d", type=float, default=0.65)
    parser.add_argument("--allow-close-below-ma30", action="store_true")
    parser.add_argument("--allow-missing-weekly-context", action="store_true")
    parser.add_argument("--max-abs-weekly-drawdown-26w", type=float, default=0.55)
    parser.add_argument("--max-weekly-ma20-deviation-pct", type=float)
    parser.add_argument("--max-ma30-deviation-pct", type=float, default=0.35)
    parser.add_argument("--min-sustained-ma30-hold-ratio-90d", type=float, default=0.75)
    parser.add_argument("--min-recent-ma30-hold-ratio-30d", type=float, default=0.75)
    parser.add_argument("--min-recent-ma30-hold-ratio-60d", type=float, default=0.55)
    parser.add_argument("--min-base-breakout-ma30-hold-ratio-60d", type=float, default=0.50)
    parser.add_argument("--min-base-breakout-return-20d", type=float, default=0.20)
    parser.add_argument("--allow-pre-breakout-without-sustained-ma30", action="store_true")
    parser.add_argument("--require-normal-listing", action="store_true")
    parser.add_argument("--min-total-mv", type=float)
    parser.add_argument("--min-avg-amount-20d", type=float)
    parser.add_argument("--max-turnover-rate-20d", type=float)
    parser.add_argument("--max-turnover-spike-ratio-20d", type=float)
    parser.add_argument("--require-context-strength", action="store_true")
    parser.add_argument("--max-convergence-5-10-20-pct", type=float)
    parser.add_argument("--enable-weak-shape-filter", action="store_true")
    parser.add_argument("--min-large-bearish-body-pct", type=float, default=0.025)
    parser.add_argument("--max-large-bearish-body-ratio-20d", type=float)
    parser.add_argument("--max-consecutive-green-k-20d", type=int)
    parser.add_argument("--max-single-bull-bar-return-share-20d", type=float)
    parser.add_argument("--min-impulse-consolidation-days", type=int)
    parser.add_argument("--min-ma5-10-20-30-convergence-pct", type=float)
    parser.add_argument("--candidate-mode", choices=("breakout", "pre_breakout", "all"), default="breakout")
    parser.add_argument("--top-n-per-date", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the research scanner."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    policy = TrendBreakoutScanPolicy(
        min_amount_ratio_20d=args.min_amount_ratio_20d,
        max_abs_drawdown_60d=args.max_abs_drawdown_60d,
        max_abs_drawdown_120d=args.max_abs_drawdown_120d,
        min_red_k_ratio_20d=args.min_red_k_ratio_20d,
        max_long_shadow_ratio_20d=args.max_long_shadow_ratio_20d,
        require_close_above_ma30=not args.allow_close_below_ma30,
        require_weekly_uptrend=bool(args.weekly_kline_tsv_path) and not args.allow_missing_weekly_context,
        max_abs_weekly_drawdown_26w=args.max_abs_weekly_drawdown_26w,
        max_weekly_ma20_deviation_pct=args.max_weekly_ma20_deviation_pct,
        max_ma30_deviation_pct=args.max_ma30_deviation_pct,
        min_sustained_ma30_hold_ratio_90d=args.min_sustained_ma30_hold_ratio_90d,
        min_recent_ma30_hold_ratio_30d=args.min_recent_ma30_hold_ratio_30d,
        min_recent_ma30_hold_ratio_60d=args.min_recent_ma30_hold_ratio_60d,
        min_base_breakout_ma30_hold_ratio_60d=args.min_base_breakout_ma30_hold_ratio_60d,
        min_base_breakout_return_20d=args.min_base_breakout_return_20d,
        require_pre_breakout_sustained_ma30=not args.allow_pre_breakout_without_sustained_ma30,
        require_normal_listing=args.require_normal_listing,
        min_total_mv=args.min_total_mv,
        min_avg_amount_20d=args.min_avg_amount_20d,
        max_turnover_rate_20d=args.max_turnover_rate_20d,
        max_turnover_spike_ratio_20d=args.max_turnover_spike_ratio_20d,
        require_context_strength=args.require_context_strength,
        max_convergence_5_10_20_pct=args.max_convergence_5_10_20_pct,
        enable_weak_shape_filter=args.enable_weak_shape_filter,
        min_large_bearish_body_pct=args.min_large_bearish_body_pct,
        max_large_bearish_body_ratio_20d=args.max_large_bearish_body_ratio_20d,
        max_consecutive_green_k_20d=args.max_consecutive_green_k_20d,
        max_single_bull_bar_return_share_20d=args.max_single_bull_bar_return_share_20d,
        min_impulse_consolidation_days=args.min_impulse_consolidation_days,
        min_ma5_10_20_30_convergence_pct=args.min_ma5_10_20_30_convergence_pct,
        start_date=args.start_date,
    )
    weekly_bars = read_kline_tsv(args.weekly_kline_tsv_path) if args.weekly_kline_tsv_path else None
    stock_contexts = read_stock_signal_context_tsv(args.stock_context_tsv_path) if args.stock_context_tsv_path else None
    metrics = scan_trend_breakouts(
        bars=read_kline_tsv(args.kline_tsv_path),
        policy=policy,
        weekly_bars=weekly_bars,
        stock_contexts=stock_contexts,
    )
    candidate_pool = select_candidates(metrics, mode="all", top_n_per_date=None)
    breakout_candidates = select_candidates(
        metrics,
        mode=args.candidate_mode,
        top_n_per_date=args.top_n_per_date,
    )
    stage_pools = _stage_candidate_pools(metrics=metrics, signal_pool=breakout_candidates)
    payload = {
        "schema_version": 1,
        "scanner": "steady_uptrend_breakout_research_scan",
        "candidate_mode": args.candidate_mode,
        "top_n_per_date": args.top_n_per_date,
        "candidate_pool_policy": {
            "pool_id": "steady_uptrend_breakout.recall_pool.v1",
            "mode": "all",
            "top_n_per_date": None,
            "description": (
                "Recall pool before final candidate_mode/top_n selection; includes breakout_watch "
                "and pre_breakout_watch candidates generated by the same TrendBreakoutScanPolicy."
            ),
        },
        "policy": {
            "min_amount_ratio_20d": policy.min_amount_ratio_20d,
            "max_abs_drawdown_60d": policy.max_abs_drawdown_60d,
            "max_abs_drawdown_120d": policy.max_abs_drawdown_120d,
            "min_red_k_ratio_20d": policy.min_red_k_ratio_20d,
            "max_long_shadow_ratio_20d": policy.max_long_shadow_ratio_20d,
            "require_close_above_ma30": policy.require_close_above_ma30,
            "require_weekly_uptrend": policy.require_weekly_uptrend,
            "max_abs_weekly_drawdown_26w": policy.max_abs_weekly_drawdown_26w,
            "max_weekly_ma20_deviation_pct": policy.max_weekly_ma20_deviation_pct,
            "min_close_to_high_60d_pct": policy.min_close_to_high_60d_pct,
            "max_close_to_high_60d_pct": policy.max_close_to_high_60d_pct,
            "min_pre_breakout_amount_ratio_20d": policy.min_pre_breakout_amount_ratio_20d,
            "max_ma20_deviation_pct": policy.max_ma20_deviation_pct,
            "max_ma30_deviation_pct": policy.max_ma30_deviation_pct,
            "min_sustained_ma30_hold_ratio_90d": policy.min_sustained_ma30_hold_ratio_90d,
            "min_recent_ma30_hold_ratio_30d": policy.min_recent_ma30_hold_ratio_30d,
            "min_recent_ma30_hold_ratio_60d": policy.min_recent_ma30_hold_ratio_60d,
            "min_base_breakout_ma30_hold_ratio_60d": policy.min_base_breakout_ma30_hold_ratio_60d,
            "min_base_breakout_return_20d": policy.min_base_breakout_return_20d,
            "require_pre_breakout_sustained_ma30": policy.require_pre_breakout_sustained_ma30,
            "require_normal_listing": policy.require_normal_listing,
            "min_total_mv": policy.min_total_mv,
            "min_avg_amount_20d": policy.min_avg_amount_20d,
            "max_turnover_rate_20d": policy.max_turnover_rate_20d,
            "max_turnover_spike_ratio_20d": policy.max_turnover_spike_ratio_20d,
            "require_context_strength": policy.require_context_strength,
            "max_convergence_5_10_20_pct": policy.max_convergence_5_10_20_pct,
            "enable_weak_shape_filter": policy.enable_weak_shape_filter,
            "min_large_bearish_body_pct": policy.min_large_bearish_body_pct,
            "max_large_bearish_body_ratio_20d": policy.max_large_bearish_body_ratio_20d,
            "max_consecutive_green_k_20d": policy.max_consecutive_green_k_20d,
            "max_single_bull_bar_return_share_20d": policy.max_single_bull_bar_return_share_20d,
            "min_impulse_consolidation_days": policy.min_impulse_consolidation_days,
            "min_ma5_10_20_30_convergence_pct": policy.min_ma5_10_20_30_convergence_pct,
            "start_date": policy.start_date,
        },
        "summary": summarize_breakout_scan(metrics),
        "stage_candidate_pool_policy": {
            "quality_pool": "daily_quality_pass == true",
            "trend_pool": "steady_uptrend == true",
            "refined_pool": "breakout_watch == true OR pre_breakout_watch == true",
            "signal_pool": "final candidates after candidate_mode and top_n_per_date",
        },
        "stage_candidate_pool_counts": {
            stage_id: len(stage_candidates)
            for stage_id, stage_candidates in stage_pools.items()
        },
        "stage_candidate_pools": {
            stage_id: [candidate.to_mapping() for candidate in stage_candidates]
            for stage_id, stage_candidates in stage_pools.items()
        },
        "candidate_pool": [candidate.to_mapping() for candidate in candidate_pool],
        "candidate_pool_count": len(candidate_pool),
        "breakout_candidates": [candidate.to_mapping() for candidate in breakout_candidates],
        "breakout_candidate_count": len(breakout_candidates),
    }
    write_json_payload(args.output_path, payload)
    print(
        json.dumps(
            {
                "output_path": args.output_path,
                "candidate_pool_count": len(candidate_pool),
                "candidate_count": len(breakout_candidates),
            },
            indent=2,
        )
    )
    return 0


def _stage_candidate_pools(
    metrics: tuple[object, ...],
    signal_pool: tuple[object, ...],
) -> dict[str, tuple[object, ...]]:
    return {
        "quality_pool": tuple(item for item in metrics if item.daily_quality_pass),
        "trend_pool": tuple(item for item in metrics if item.steady_uptrend),
        "refined_pool": tuple(item for item in metrics if item.breakout_watch or item.pre_breakout_watch),
        "signal_pool": signal_pool,
    }


if __name__ == "__main__":
    raise SystemExit(main())
