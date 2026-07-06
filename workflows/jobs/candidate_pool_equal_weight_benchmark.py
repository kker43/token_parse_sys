"""Candidate-pool equal-weight benchmark job."""

from __future__ import annotations

import argparse
from collections.abc import Sequence as SequenceAbc
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.l6_backtest_engine import (
    BacktestEvent,
    EventBacktestPolicy,
    PriceBar,
    run_candidate_pool_equal_weight_benchmark,
)
from workflows.jobs.support import write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build parser for candidate-pool benchmark generation."""

    parser = argparse.ArgumentParser(prog="candidate_pool_equal_weight_benchmark")
    parser.add_argument("--kline-tsv-path", required=True)
    parser.add_argument("--candidate-pool-path", required=True)
    parser.add_argument("--candidate-pool-key", default="candidate_pool")
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--holding-horizon", action="append", type=int, dest="holding_horizons")
    parser.add_argument("--entry-offset", type=int, default=1)
    parser.add_argument("--entry-price-field", default="open")
    parser.add_argument("--exit-price-field", default="close")
    parser.add_argument("--benchmark-id", default="candidate_pool_equal_weight_v1")
    parser.add_argument("--strategy-id", default="strategy.candidate_pool_benchmark")
    parser.add_argument("--strategy-version", default="benchmark_v1")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Generate candidate-pool equal-weight benchmark results."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    holding_horizons = tuple(args.holding_horizons or (5, 10, 20, 60))
    bars = _read_price_bars(args.kline_tsv_path)
    events = _read_events(args.candidate_pool_path, candidate_pool_key=args.candidate_pool_key)
    benchmark_results = []
    for holding_horizon in holding_horizons:
        result = run_candidate_pool_equal_weight_benchmark(
            bars=bars,
            candidate_events=events,
            policy=EventBacktestPolicy(
                strategy_id=args.strategy_id,
                strategy_version=args.strategy_version,
                holding_horizon=holding_horizon,
                benchmark="CANDIDATE_POOL_EQUAL_WEIGHT",
                entry_offset=args.entry_offset,
                entry_price_field=args.entry_price_field,
                exit_price_field=args.exit_price_field,
            ),
            benchmark_id=args.benchmark_id,
        )
        benchmark_results.append(result.to_mapping())

    payload = {
        "schema_version": 1,
        "job_name": "candidate_pool_equal_weight_benchmark",
        "benchmark_id": args.benchmark_id,
        "source_candidate_pool_path": args.candidate_pool_path,
        "source_candidate_pool_key": args.candidate_pool_key,
        "kline_tsv_path": args.kline_tsv_path,
        "event_count": len(events),
        "benchmark_results": benchmark_results,
    }
    write_json_payload(args.output_path, payload)
    print(
        json.dumps(
            {
                "output_path": args.output_path,
                "event_count": len(events),
                "holding_horizons": list(holding_horizons),
            },
            indent=2,
        )
    )
    return 0


def _read_price_bars(path: str | Path) -> tuple[PriceBar, ...]:
    bars: list[PriceBar] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        asset_id, trade_date, open_value, high, low, close, *_ = line.split("\t")
        bars.append(
            PriceBar(
                asset_id=asset_id,
                trade_date=trade_date,
                open=float(open_value),
                high=float(high),
                low=float(low),
                close=float(close),
            )
        )
    return tuple(bars)


def _read_events(path: str | Path, candidate_pool_key: str = "candidate_pool") -> tuple[BacktestEvent, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    candidates = _candidate_rows(payload, candidate_pool_key=candidate_pool_key)
    events: list[BacktestEvent] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("each candidate pool row must be a JSON object")
        asset_id = str(candidate["asset_id"])
        signal_date = str(candidate["trade_date"])
        event_id = str(candidate.get("event_id", f"{asset_id}.{signal_date}"))
        events.append(BacktestEvent(asset_id=asset_id, signal_date=signal_date, event_id=event_id))
    return tuple(events)


def _candidate_rows(payload: object, candidate_pool_key: str) -> Sequence[object]:
    if not isinstance(payload, Mapping):
        raise ValueError("candidate pool payload must be a JSON object")
    keys = (
        (candidate_pool_key, "breakout_candidates", "candidates")
        if candidate_pool_key == "candidate_pool"
        else (candidate_pool_key,)
    )
    for key in keys:
        value = _lookup_candidate_pool(payload, key)
        if value is not None:
            if not isinstance(value, SequenceAbc) or isinstance(value, (str, bytes)):
                raise ValueError(f"{key} must be a JSON array")
            return value
    raise ValueError(f"candidate pool payload does not contain requested pool: {candidate_pool_key}")


def _lookup_candidate_pool(payload: Mapping[str, object], key: str) -> object:
    if key in payload:
        return payload.get(key)
    stage_pools = payload.get("stage_candidate_pools")
    if isinstance(stage_pools, Mapping) and key in stage_pools:
        return stage_pools.get(key)
    return None


if __name__ == "__main__":
    raise SystemExit(main())
