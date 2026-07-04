"""Event backtest job for steady uptrend breakout candidates."""

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
    BacktestEvent,
    EventBacktestPolicy,
    PriceBar,
    run_event_backtest,
)
from workflows.jobs.support import write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build parser for the event backtest job."""

    parser = argparse.ArgumentParser(prog="steady_uptrend_breakout_event_backtest")
    parser.add_argument("--kline-tsv-path", required=True)
    parser.add_argument("--scan-result-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--holding-horizon", action="append", type=int, dest="holding_horizons")
    parser.add_argument("--entry-offset", type=int, default=1)
    parser.add_argument("--entry-price-field", default="open")
    parser.add_argument("--exit-price-field", default="close")
    parser.add_argument("--benchmark", default="000300.SH")
    parser.add_argument("--strategy-id", default="strategy.steady_uptrend_breakout_watch")
    parser.add_argument("--strategy-version", default="candidate_v1")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run event backtests for one or more holding horizons."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    holding_horizons = tuple(args.holding_horizons or (5, 10, 20))
    bars = _read_price_bars(args.kline_tsv_path)
    events = _read_events(args.scan_result_path)
    reports = []
    for holding_horizon in holding_horizons:
        report = run_event_backtest(
            bars=bars,
            events=events,
            policy=EventBacktestPolicy(
                strategy_id=args.strategy_id,
                strategy_version=args.strategy_version,
                holding_horizon=holding_horizon,
                benchmark=args.benchmark,
                entry_offset=args.entry_offset,
                entry_price_field=args.entry_price_field,
                exit_price_field=args.exit_price_field,
            ),
        )
        reports.append(report.to_mapping())

    output_payload = {
        "schema_version": 1,
        "job_name": "steady_uptrend_breakout_event_backtest",
        "source_scan_result_path": args.scan_result_path,
        "kline_tsv_path": args.kline_tsv_path,
        "event_count": len(events),
        "reports": reports,
    }
    write_json_payload(args.output_path, output_payload)
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


def _read_events(path: str | Path) -> tuple[BacktestEvent, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    candidates = payload.get("breakout_candidates", ())
    events: list[BacktestEvent] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("each breakout candidate must be a JSON object")
        asset_id = str(candidate["asset_id"])
        signal_date = str(candidate["trade_date"])
        events.append(
            BacktestEvent(
                asset_id=asset_id,
                signal_date=signal_date,
                event_id=f"{asset_id}.{signal_date}",
            )
        )
    return tuple(events)


if __name__ == "__main__":
    raise SystemExit(main())
