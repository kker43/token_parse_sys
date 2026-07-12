"""Research-only S1-S5 scan for the mature steady-uptrend MVP."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict, fields
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.research import (
    SteadyUptrendMvpCandidate,
    SteadyUptrendMvpPolicy,
    build_steady_uptrend_mvp_report,
    evaluate_steady_uptrend_mvp,
    read_kline_tsv,
    read_stock_signal_context_tsv,
)
from stock_lobster.research.trend_breakout_scan import KlineBar, StockSignalContext
from workflows.jobs.support import write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build the deterministic research scan CLI."""

    parser = argparse.ArgumentParser(prog="steady_uptrend_s1_s5_mvp_scan")
    parser.add_argument("--kline-tsv-path", required=True)
    parser.add_argument("--weekly-kline-tsv-path", required=True)
    parser.add_argument("--stock-context-tsv-path", required=True)
    parser.add_argument("--strategy-config-path", required=True)
    parser.add_argument("--signal-date", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--markdown-output-path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Evaluate one signal date from supplied read-only fact artifacts."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    config = _read_json_object(args.strategy_config_path)
    strategy_id = _required_string(config, "strategy_id")
    status = _required_string(config, "status")
    version = _required_string(config, "version")
    policy = _build_policy(config.get("policy"))
    dependency_versions = _string_mapping(config.get("data_dependency_versions"))

    daily_bars = read_kline_tsv(args.kline_tsv_path)
    weekly_bars = read_kline_tsv(args.weekly_kline_tsv_path)
    contexts = read_stock_signal_context_tsv(args.stock_context_tsv_path)
    evaluations = _evaluate_universe(
        daily_bars,
        weekly_bars,
        contexts,
        signal_date=args.signal_date,
        policy=policy,
    )
    payload = build_steady_uptrend_mvp_report(
        evaluations,
        strategy_id=strategy_id,
        run_id=args.run_id,
        signal_date=args.signal_date,
        data_dependency_versions=dependency_versions,
    )
    payload.update(
        {
            "schema_version": 1,
            "scanner": "steady_uptrend_s1_s5_mvp_scan",
            "version": version,
            "status": status,
            "policy": asdict(policy),
        }
    )
    write_json_payload(args.output_path, payload)
    if args.markdown_output_path:
        markdown_output = Path(args.markdown_output_path)
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(str(payload["markdown"]), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": args.output_path,
                "signal_date": args.signal_date,
                "input_count": len(evaluations),
                "candidate_count": len(payload["candidates"]),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def _evaluate_universe(
    daily_bars: tuple[KlineBar, ...],
    weekly_bars: tuple[KlineBar, ...],
    contexts: tuple[StockSignalContext, ...],
    *,
    signal_date: str,
    policy: SteadyUptrendMvpPolicy,
) -> tuple[SteadyUptrendMvpCandidate, ...]:
    daily_by_asset: dict[str, list[KlineBar]] = defaultdict(list)
    weekly_by_asset: dict[str, list[KlineBar]] = defaultdict(list)
    for bar in daily_bars:
        if bar.trade_date <= signal_date:
            daily_by_asset[bar.asset_id].append(bar)
    for bar in weekly_bars:
        if bar.trade_date <= signal_date:
            weekly_by_asset[bar.asset_id].append(bar)
    context_by_asset = {
        context.asset_id: context
        for context in contexts
        if context.trade_date == signal_date
    }
    assets_with_signal_bar = {
        asset_id
        for asset_id, bars in daily_by_asset.items()
        if bars and max(bar.trade_date for bar in bars) == signal_date
    }
    asset_ids = sorted(assets_with_signal_bar | set(context_by_asset))
    return tuple(
        evaluate_steady_uptrend_mvp(
            daily_by_asset.get(asset_id, ()),
            weekly_by_asset.get(asset_id, ()),
            context_by_asset.get(asset_id),
            signal_date=signal_date,
            policy=policy,
        )
        for asset_id in asset_ids
    )


def _build_policy(payload: object) -> SteadyUptrendMvpPolicy:
    if payload is None:
        return SteadyUptrendMvpPolicy()
    if not isinstance(payload, Mapping):
        raise ValueError("policy must be a JSON object")
    allowed = {field.name for field in fields(SteadyUptrendMvpPolicy)}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"unknown policy keys: {', '.join(unknown)}")
    return SteadyUptrendMvpPolicy(**dict(payload))


def _read_json_object(path: str | Path) -> Mapping[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("strategy config must be a JSON object")
    return payload


def _required_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _string_mapping(payload: object) -> dict[str, str]:
    if not isinstance(payload, Mapping) or not payload:
        raise ValueError("data_dependency_versions must be a non-empty JSON object")
    result: dict[str, str] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, str) or not value:
            raise ValueError("data_dependency_versions keys and values must be strings")
        result[key] = value
    return result


if __name__ == "__main__":
    raise SystemExit(main())
