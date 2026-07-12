"""Research-only scan for ordered structural recall and signal selection."""

from __future__ import annotations

import argparse
from dataclasses import fields
import json
from pathlib import Path
import sys
from typing import Iterable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.research import (
    LayeredCandidate,
    LayeredSignalPolicy,
    TrendBreakoutMetrics,
    TrendBreakoutScanPolicy,
    TrendRecallSubpoolPolicy,
    read_kline_tsv,
    read_stock_signal_context_tsv,
    scan_trend_breakouts,
    select_layered_candidates,
)
from stock_lobster.research.steady_uptrend_v3 import MarketTemperature, build_market_temperatures
from workflows.jobs.support import write_json_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="layered_recall_signal_research_scan")
    parser.add_argument("--kline-tsv-path", required=True)
    parser.add_argument("--weekly-kline-tsv-path")
    parser.add_argument("--stock-context-tsv-path")
    parser.add_argument("--strategy-config-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--start-date")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    config = _read_json_object(args.strategy_config_path)
    scan_policy = _build_policy(
        TrendBreakoutScanPolicy,
        config.get("candidate_scan_policy", {}),
        {"start_date": args.start_date} if args.start_date else None,
    )
    bars = read_kline_tsv(args.kline_tsv_path)
    weekly_bars = read_kline_tsv(args.weekly_kline_tsv_path) if args.weekly_kline_tsv_path else None
    contexts = read_stock_signal_context_tsv(args.stock_context_tsv_path) if args.stock_context_tsv_path else None
    metrics = scan_trend_breakouts(
        bars,
        policy=scan_policy,
        weekly_bars=weekly_bars,
        stock_contexts=contexts,
    )
    temperatures = build_market_temperatures(bars, start_date=scan_policy.start_date)
    trade_date_order = tuple(sorted({bar.trade_date for bar in bars}))
    payload = build_stage_payload(
        metrics,
        market_temperatures=temperatures,
        config=config,
        trade_date_order=trade_date_order,
    )
    payload.update(
        {
            "schema_version": 1,
            "scanner": "layered_recall_signal_research_scan",
            "strategy_id": str(config.get("strategy_id", "strategy.steady_uptrend_layered_signal")),
            "strategy_version": str(config.get("version", "candidate_v4")),
            "strategy_status": str(config.get("status", "research_only")),
            "strategy_config_path": str(Path(args.strategy_config_path).resolve()),
            "kline_tsv_path": args.kline_tsv_path,
            "weekly_kline_tsv_path": args.weekly_kline_tsv_path,
            "stock_context_tsv_path": args.stock_context_tsv_path,
            "candidate_scan_policy": _policy_mapping(scan_policy),
        }
    )
    write_json_payload(args.output_path, payload)
    print(json.dumps({"output_path": args.output_path, **payload["stage_counts"]}, indent=2))
    return 0


def build_stage_payload(
    metrics: Iterable[TrendBreakoutMetrics],
    *,
    market_temperatures: Mapping[str, MarketTemperature],
    config: Mapping[str, object],
    trade_date_order: Iterable[str] | None = None,
) -> dict[str, object]:
    recall_policy = _build_policy(TrendRecallSubpoolPolicy, config.get("recall_policy", {}))
    signal_policy = _build_policy(LayeredSignalPolicy, config.get("signal_policy", {}))
    result = select_layered_candidates(
        metrics,
        market_temperatures=market_temperatures,
        recall_policy=recall_policy,
        signal_policy=signal_policy,
        trade_date_order=trade_date_order,
    )
    return {
        "recall_policy": _policy_mapping(recall_policy),
        "signal_policy": _policy_mapping(signal_policy),
        "stage_counts": result.stage_counts(),
        "recall_candidates": [_candidate_mapping(item, market_temperatures) for item in result.recall_candidates],
        "waiting_candidates": [_candidate_mapping(item, market_temperatures) for item in result.waiting_candidates],
        "hard_risk_rejected_candidates": [
            _candidate_mapping(item, market_temperatures)
            for item in result.hard_risk_rejected_candidates
        ],
        "signal_eligible_candidates": [
            _candidate_mapping(item, market_temperatures)
            for item in result.signal_eligible_candidates
        ],
        "ranked_topn": [_candidate_mapping(item, market_temperatures) for item in result.ranked_topn],
        "final_signals": [_candidate_mapping(item, market_temperatures) for item in result.final_signals],
    }


def _candidate_mapping(
    candidate: LayeredCandidate,
    market_temperatures: Mapping[str, MarketTemperature],
) -> dict[str, object]:
    metric = candidate.decision.metric
    payload = metric.to_mapping()
    payload.update(
        {
            "matched_subpools": list(candidate.decision.matched_subpools),
            "recall_candidate": candidate.decision.recall_candidate,
            "waiting_reasons": list(candidate.state.waiting_reasons),
            "hard_risk_reasons": list(candidate.state.hard_risk_reasons),
            "confirmation_reasons": list(candidate.state.confirmation_reasons),
            "effective_activity_ratio": candidate.state.effective_activity_ratio,
            "signal_eligible": candidate.state.signal_eligible,
            "layered_score": candidate.score,
            "post_rank_rejection_reasons": list(candidate.post_rank_rejection_reasons),
            "market_temperature": (
                market_temperatures[metric.trade_date].to_mapping()
                if metric.trade_date in market_temperatures
                else None
            ),
        }
    )
    return payload


def _read_json_object(path: str | Path) -> Mapping[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("strategy config must be a JSON object")
    return payload


def _build_policy(
    policy_cls: type[object],
    payload: object,
    overrides: Mapping[str, object] | None = None,
) -> object:
    if payload is None:
        values: dict[str, object] = {}
    elif isinstance(payload, Mapping):
        values = dict(payload)
    else:
        raise ValueError(f"{policy_cls.__name__} config must be a JSON object")
    if overrides:
        values.update(overrides)
    allowed = {field.name for field in fields(policy_cls)}
    kwargs = {
        key: tuple(value) if isinstance(value, list) else value
        for key, value in values.items()
        if key in allowed
    }
    return policy_cls(**kwargs)  # type: ignore[misc]


def _policy_mapping(policy: object) -> dict[str, object]:
    return {
        field.name: list(value) if isinstance(value := getattr(policy, field.name), tuple) else value
        for field in fields(policy)
    }


if __name__ == "__main__":
    raise SystemExit(main())
