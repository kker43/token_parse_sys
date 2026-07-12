"""Research job for steady uptrend v3 observation and signal candidates."""

from __future__ import annotations

import argparse
from dataclasses import fields
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence

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
from stock_lobster.research.steady_uptrend_v3 import (
    MarketTemperature,
    SteadyUptrendV3Policy,
    build_market_temperatures,
    select_v3_observation_candidates,
    select_v3_signal_candidates,
    summarize_v3_rejections,
    v3_rejection_reasons,
    v3_score,
)
from stock_lobster.research.trend_breakout_scan import TrendBreakoutMetrics
from workflows.jobs.support import write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build parser for the v3 research scanner."""

    parser = argparse.ArgumentParser(prog="steady_uptrend_v3_research_scan")
    parser.add_argument("--kline-tsv-path", required=True)
    parser.add_argument("--weekly-kline-tsv-path")
    parser.add_argument("--stock-context-tsv-path")
    parser.add_argument("--strategy-config-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--start-date")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the v3 research scanner."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    config = _read_json_object(args.strategy_config_path)
    scan_policy = _build_policy(
        TrendBreakoutScanPolicy,
        config.get("candidate_scan_policy", {}),
        overrides={"start_date": args.start_date} if args.start_date else {},
    )
    v3_policy = _build_policy(SteadyUptrendV3Policy, config.get("v3_filter_policy", {}))

    bars = read_kline_tsv(args.kline_tsv_path)
    weekly_bars = read_kline_tsv(args.weekly_kline_tsv_path) if args.weekly_kline_tsv_path else None
    stock_contexts = read_stock_signal_context_tsv(args.stock_context_tsv_path) if args.stock_context_tsv_path else None
    metrics = scan_trend_breakouts(
        bars=bars,
        policy=scan_policy,
        weekly_bars=weekly_bars,
        stock_contexts=stock_contexts,
    )
    market_temperatures = build_market_temperatures(
        bars,
        start_date=scan_policy.start_date,
    )
    trade_date_order = tuple(sorted({bar.trade_date for bar in bars}))
    candidate_pool = select_candidates(metrics, mode="all", top_n_per_date=None)
    observation_candidates = select_v3_observation_candidates(
        metrics,
        market_temperatures=market_temperatures,
        policy=v3_policy,
        trade_date_order=trade_date_order,
    )
    signal_candidates = select_v3_signal_candidates(
        metrics,
        market_temperatures=market_temperatures,
        policy=v3_policy,
        trade_date_order=trade_date_order,
    )
    rejected_candidates = tuple(
        item
        for item in candidate_pool
        if v3_rejection_reasons(
            item,
            market_temperature=market_temperatures.get(item.trade_date),
            policy=v3_policy,
        )
    )
    payload = {
        "schema_version": 1,
        "scanner": "steady_uptrend_v3_research_scan",
        "strategy_id": str(config.get("strategy_id", "strategy.steady_uptrend_pre_breakout_watch")),
        "strategy_version": str(config.get("version", "candidate_v3")),
        "strategy_config_path": str(Path(args.strategy_config_path).resolve()),
        "kline_tsv_path": args.kline_tsv_path,
        "weekly_kline_tsv_path": args.weekly_kline_tsv_path,
        "stock_context_tsv_path": args.stock_context_tsv_path,
        "candidate_pool_policy": {
            "pool_id": "steady_uptrend_breakout.recall_pool.v3",
            "mode": "all",
            "description": (
                "Base recall pool before v3 market-temperature, rotation-context, ranking, "
                "and daily TopN filters; includes breakout_watch and pre_breakout_watch."
            ),
        },
        "candidate_scan_policy": _policy_mapping(scan_policy),
        "v3_filter_policy": v3_policy.to_mapping(),
        "summary": summarize_breakout_scan(metrics),
        "market_temperature_summary": _market_temperature_summary(market_temperatures),
        "market_temperatures": [
            market_temperatures[trade_date].to_mapping()
            for trade_date in sorted(market_temperatures)
        ],
        "v3_rejection_reason_counts": summarize_v3_rejections(
            candidate_pool,
            market_temperatures=market_temperatures,
            policy=v3_policy,
        ),
        "stage_candidate_pool_policy": {
            "candidate_pool": "breakout_watch == true OR pre_breakout_watch == true",
            "observation_pool": "pre_breakout_watch == true and no v3 rejection reasons",
            "signal_pool": "breakout_watch == true and no v3 rejection reasons, after daily TopN",
        },
        "stage_candidate_pool_counts": {
            "candidate_pool": len(candidate_pool),
            "observation_pool": len(observation_candidates),
            "signal_pool": len(signal_candidates),
            "rejected_pool": len(rejected_candidates),
        },
        "candidate_pool": [
            _candidate_mapping(item, market_temperatures=market_temperatures, policy=v3_policy)
            for item in candidate_pool
        ],
        "candidate_pool_count": len(candidate_pool),
        "observation_candidates": [
            _candidate_mapping(item, market_temperatures=market_temperatures, policy=v3_policy)
            for item in observation_candidates
        ],
        "observation_candidate_count": len(observation_candidates),
        "signal_candidates": [
            _candidate_mapping(item, market_temperatures=market_temperatures, policy=v3_policy)
            for item in signal_candidates
        ],
        "signal_candidate_count": len(signal_candidates),
        "breakout_candidates": [
            _candidate_mapping(item, market_temperatures=market_temperatures, policy=v3_policy)
            for item in signal_candidates
        ],
        "breakout_candidate_count": len(signal_candidates),
        "v3_rejected_candidates": [
            _candidate_mapping(item, market_temperatures=market_temperatures, policy=v3_policy)
            for item in rejected_candidates
        ],
        "v3_rejected_candidate_count": len(rejected_candidates),
    }
    write_json_payload(args.output_path, payload)
    print(
        json.dumps(
            {
                "output_path": args.output_path,
                "candidate_pool_count": len(candidate_pool),
                "observation_candidate_count": len(observation_candidates),
                "signal_candidate_count": len(signal_candidates),
                "rejected_candidate_count": len(rejected_candidates),
            },
            indent=2,
        )
    )
    return 0


def _read_json_object(path: str | Path) -> Mapping[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("strategy config must be a JSON object")
    return payload


def _build_policy(policy_cls: type[object], payload: object, overrides: Mapping[str, object] | None = None) -> object:
    if payload is None:
        values: dict[str, object] = {}
    elif isinstance(payload, Mapping):
        values = dict(payload)
    else:
        raise ValueError(f"{policy_cls.__name__} config must be a JSON object")
    if overrides:
        values.update({key: value for key, value in overrides.items() if value is not None})
    allowed = {field.name for field in fields(policy_cls)}
    kwargs = {key: _tuple_if_sequence(value) for key, value in values.items() if key in allowed}
    return policy_cls(**kwargs)  # type: ignore[misc]


def _tuple_if_sequence(value: object) -> object:
    if isinstance(value, list):
        return tuple(value)
    return value


def _policy_mapping(policy: object) -> dict[str, object]:
    return {
        field.name: _json_safe(getattr(policy, field.name))
        for field in fields(policy)
    }


def _json_safe(value: object) -> object:
    if isinstance(value, tuple):
        return list(value)
    return value


def _candidate_mapping(
    candidate: TrendBreakoutMetrics,
    *,
    market_temperatures: Mapping[str, MarketTemperature],
    policy: SteadyUptrendV3Policy,
) -> dict[str, object]:
    temperature = market_temperatures.get(candidate.trade_date)
    payload = candidate.to_mapping()
    payload["v3_score"] = v3_score(candidate, market_temperature=temperature, policy=policy)
    payload["v3_rejection_reasons"] = list(
        v3_rejection_reasons(candidate, market_temperature=temperature, policy=policy)
    )
    payload["market_temperature"] = temperature.to_mapping() if temperature else None
    return payload


def _market_temperature_summary(
    market_temperatures: Mapping[str, MarketTemperature],
) -> dict[str, object]:
    if not market_temperatures:
        return {
            "date_count": 0,
            "max_breadth_ma20": None,
            "max_avg_return_20d": None,
            "max_avg_amount_ratio": None,
        }
    temperatures = tuple(market_temperatures.values())
    return {
        "date_count": len(temperatures),
        "max_breadth_ma20": max(item.breadth_ma20 for item in temperatures),
        "max_avg_return_20d": max(item.avg_return_20d for item in temperatures),
        "max_avg_amount_ratio": max(item.avg_amount_ratio for item in temperatures),
        "min_sample_size": min(item.sample_size for item in temperatures),
        "max_sample_size": max(item.sample_size for item in temperatures),
    }


if __name__ == "__main__":
    raise SystemExit(main())
