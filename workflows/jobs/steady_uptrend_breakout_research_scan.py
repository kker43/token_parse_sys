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
    scan_trend_breakouts,
    summarize_breakout_scan,
)
from workflows.jobs.support import write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build parser for the research scanner."""

    parser = argparse.ArgumentParser(prog="steady_uptrend_breakout_research_scan")
    parser.add_argument("--kline-tsv-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--start-date")
    parser.add_argument("--min-amount-ratio-20d", type=float, default=1.5)
    parser.add_argument("--max-abs-drawdown-60d", type=float, default=0.40)
    parser.add_argument("--max-convergence-5-10-20-pct", type=float)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the research scanner."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    policy = TrendBreakoutScanPolicy(
        min_amount_ratio_20d=args.min_amount_ratio_20d,
        max_abs_drawdown_60d=args.max_abs_drawdown_60d,
        max_convergence_5_10_20_pct=args.max_convergence_5_10_20_pct,
        start_date=args.start_date,
    )
    metrics = scan_trend_breakouts(
        bars=read_kline_tsv(args.kline_tsv_path),
        policy=policy,
    )
    breakout_candidates = [metric for metric in metrics if metric.breakout_watch]
    payload = {
        "schema_version": 1,
        "scanner": "steady_uptrend_breakout_research_scan",
        "policy": {
            "min_amount_ratio_20d": policy.min_amount_ratio_20d,
            "max_abs_drawdown_60d": policy.max_abs_drawdown_60d,
            "max_convergence_5_10_20_pct": policy.max_convergence_5_10_20_pct,
            "start_date": policy.start_date,
        },
        "summary": summarize_breakout_scan(metrics),
        "breakout_candidates": [candidate.to_mapping() for candidate in breakout_candidates],
    }
    write_json_payload(args.output_path, payload)
    print(json.dumps({"output_path": args.output_path, "candidate_count": len(breakout_candidates)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
