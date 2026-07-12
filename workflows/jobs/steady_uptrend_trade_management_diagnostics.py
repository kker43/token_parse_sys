"""Trade-management diagnostics for steady uptrend short breakout candidates."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Sequence as SequenceAbc
import json
from pathlib import Path
from statistics import mean, median
import sys
from typing import Callable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.l6_backtest_engine import (
    BacktestEvent,
    PriceBar,
    TradeManagementPolicy,
    run_trade_management_backtest,
)
from workflows.jobs.support import write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build parser for the trade-management diagnostics job."""

    parser = argparse.ArgumentParser(prog="steady_uptrend_trade_management_diagnostics")
    parser.add_argument("--kline-tsv-path", required=True)
    parser.add_argument("--scan-result-path", required=True)
    parser.add_argument("--candidate-pool-key", default="observation_candidates")
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--summary-md-path")
    parser.add_argument("--strategy-id", default="strategy.steady_uptrend_pre_breakout_watch")
    parser.add_argument("--strategy-version", default="candidate_v3_1_trade_management_diagnostic")
    parser.add_argument("--benchmark", default="000300.SH")
    parser.add_argument("--weak-breadth-ma20-threshold", type=float)
    parser.add_argument("--weak-breadth-top-n", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run default short trade-management diagnostics."""

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    candidate_pool_variant_policy = _candidate_pool_variant_policy(args, parser=parser)
    bars = _read_price_bars(args.kline_tsv_path)
    scan_payload = _read_scan_payload(args.scan_result_path)
    candidates = _candidate_rows(scan_payload, candidate_pool_key=args.candidate_pool_key)
    candidates = _apply_candidate_pool_variant_policy(
        candidates,
        candidate_pool_variant_policy=candidate_pool_variant_policy,
    )
    events = _events_from_candidates(candidates)
    event_contexts = _event_contexts_from_candidates(candidates)
    variants = _default_variant_policies(
        strategy_id=args.strategy_id,
        strategy_version=args.strategy_version,
        benchmark=args.benchmark,
    )
    reports = {
        variant_name: run_trade_management_backtest(
            bars=bars,
            events=events,
            policy=policy,
        ).to_mapping()
        for variant_name, policy in variants.items()
    }
    payload = {
        "schema_version": 1,
        "job_name": "steady_uptrend_trade_management_diagnostics",
        "source_scan_result_path": args.scan_result_path,
        "candidate_pool_key": args.candidate_pool_key,
        "candidate_pool_variant_policy": candidate_pool_variant_policy,
        "kline_tsv_path": args.kline_tsv_path,
        "event_count": len(events),
        "variants": reports,
        "stability": _build_stability(reports, event_contexts=event_contexts),
    }
    write_json_payload(args.output_path, payload)
    summary = _render_summary(payload)
    summary_path = args.summary_md_path
    if summary_path:
        Path(summary_path).parent.mkdir(parents=True, exist_ok=True)
        Path(summary_path).write_text(summary, encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": args.output_path,
                "summary_md_path": summary_path,
                "event_count": len(events),
                "variant_count": len(reports),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def _candidate_pool_variant_policy(
    args: argparse.Namespace,
    *,
    parser: argparse.ArgumentParser,
) -> dict[str, object]:
    weak_breadth_threshold = args.weak_breadth_ma20_threshold
    weak_breadth_top_n = args.weak_breadth_top_n
    if (weak_breadth_threshold is None) != (weak_breadth_top_n is None):
        parser.error("--weak-breadth-ma20-threshold and --weak-breadth-top-n must be provided together")
    if weak_breadth_threshold is None:
        return {}
    if weak_breadth_top_n <= 0:
        parser.error("--weak-breadth-top-n must be positive")
    return {
        "weak_breadth_limit": {
            "market_breadth_ma20_lt": weak_breadth_threshold,
            "top_n_per_signal_date": weak_breadth_top_n,
        }
    }


def _apply_candidate_pool_variant_policy(
    candidates: Sequence[object],
    *,
    candidate_pool_variant_policy: Mapping[str, object],
) -> tuple[object, ...]:
    weak_breadth_limit = candidate_pool_variant_policy.get("weak_breadth_limit")
    if not isinstance(weak_breadth_limit, Mapping):
        return tuple(candidates)
    return _limit_weak_breadth_candidates(
        candidates,
        breadth_threshold=float(weak_breadth_limit["market_breadth_ma20_lt"]),
        top_n=int(weak_breadth_limit["top_n_per_signal_date"]),
    )


def _limit_weak_breadth_candidates(
    candidates: Sequence[object],
    *,
    breadth_threshold: float,
    top_n: int,
) -> tuple[object, ...]:
    kept: list[object] = []
    weak_counts_by_date: Counter[str] = Counter()
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            kept.append(candidate)
            continue
        signal_date = str(candidate["trade_date"])
        if not _is_weak_breadth_candidate(candidate, breadth_threshold=breadth_threshold):
            kept.append(candidate)
            continue
        if weak_counts_by_date[signal_date] < top_n:
            kept.append(candidate)
            weak_counts_by_date[signal_date] += 1
    return tuple(kept)


def _is_weak_breadth_candidate(
    candidate: Mapping[str, object],
    *,
    breadth_threshold: float,
) -> bool:
    market_temperature = candidate.get("market_temperature")
    if not isinstance(market_temperature, Mapping):
        return False
    raw_breadth = market_temperature.get("breadth_ma20")
    if raw_breadth is None:
        return False
    return float(raw_breadth) < breadth_threshold


def _default_variant_policies(
    *,
    strategy_id: str,
    strategy_version: str,
    benchmark: str,
) -> dict[str, TradeManagementPolicy]:
    base = {
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "benchmark": benchmark,
        "max_holding_days": 5,
    }
    return {
        "baseline_h5": TradeManagementPolicy(**base),
        "stop_loss_8": TradeManagementPolicy(**base, stop_loss_pct=-0.08),
        "stop_loss_10": TradeManagementPolicy(**base, stop_loss_pct=-0.10),
        "stop_loss_12": TradeManagementPolicy(**base, stop_loss_pct=-0.12),
        "stop10_take15": TradeManagementPolicy(**base, stop_loss_pct=-0.10, take_profit_pct=0.15),
        "stop10_take20": TradeManagementPolicy(**base, stop_loss_pct=-0.10, take_profit_pct=0.20),
        "gap5_stop10": TradeManagementPolicy(**base, max_entry_gap_up_pct=0.05, stop_loss_pct=-0.10),
        "gap8_stop10": TradeManagementPolicy(**base, max_entry_gap_up_pct=0.08, stop_loss_pct=-0.10),
        "gap5_stop10_take15": TradeManagementPolicy(
            **base,
            max_entry_gap_up_pct=0.05,
            stop_loss_pct=-0.10,
            take_profit_pct=0.15,
        ),
        "gap8_stop10_take15": TradeManagementPolicy(
            **base,
            max_entry_gap_up_pct=0.08,
            stop_loss_pct=-0.10,
            take_profit_pct=0.15,
        ),
    }


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


def _read_scan_payload(path: str | Path) -> Mapping[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("scan result payload must be a JSON object")
    return payload


def _events_from_candidates(candidates: Sequence[object]) -> tuple[BacktestEvent, ...]:
    events: list[BacktestEvent] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("each candidate must be a JSON object")
        asset_id = str(candidate["asset_id"])
        signal_date = str(candidate["trade_date"])
        events.append(BacktestEvent(asset_id=asset_id, signal_date=signal_date, event_id=f"{asset_id}.{signal_date}"))
    return tuple(events)


def _event_contexts_from_candidates(candidates: Sequence[object]) -> dict[str, Mapping[str, object]]:
    contexts: dict[str, Mapping[str, object]] = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        asset_id = str(candidate["asset_id"])
        signal_date = str(candidate["trade_date"])
        contexts[f"{asset_id}.{signal_date}"] = candidate
    return contexts


def _candidate_rows(payload: object, *, candidate_pool_key: str) -> Sequence[object]:
    if not isinstance(payload, Mapping):
        raise ValueError("scan result payload must be a JSON object")
    value = _lookup_candidate_pool(payload, candidate_pool_key)
    if value is None:
        raise ValueError(f"scan result payload does not contain requested pool: {candidate_pool_key}")
    if not isinstance(value, SequenceAbc) or isinstance(value, (str, bytes)):
        raise ValueError(f"{candidate_pool_key} must be a JSON array")
    return value


def _lookup_candidate_pool(payload: Mapping[str, object], key: str) -> object:
    if key in payload:
        return payload.get(key)
    stage_pools = payload.get("stage_candidate_pools")
    if isinstance(stage_pools, Mapping) and key in stage_pools:
        return stage_pools.get(key)
    return None


def _render_summary(payload: Mapping[str, object]) -> str:
    variants = payload["variants"]
    if not isinstance(variants, Mapping):
        raise ValueError("variants must be a JSON object")
    lines = [
        "# steady uptrend trade management diagnostics",
        "",
        f"- candidate_pool_key: `{payload['candidate_pool_key']}`",
        f"- event_count: {payload['event_count']}",
    ]
    candidate_pool_variant_policy = payload.get("candidate_pool_variant_policy")
    if candidate_pool_variant_policy:
        lines.append(
            f"- candidate_pool_variant_policy: `{json.dumps(candidate_pool_variant_policy, sort_keys=True, ensure_ascii=False)}`"
        )
    lines.extend(
        [
            "",
            "| variant | sample | skipped | avg | median | win | max_dd | avg_dd | worst | best | stops | takes | time_exit |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name, report in variants.items():
        if not isinstance(report, Mapping):
            continue
        result = report["result"]
        exit_counts = report.get("exit_reason_counts", {})
        skipped_events = report.get("skipped_events", [])
        if not isinstance(result, Mapping) or not isinstance(exit_counts, Mapping):
            continue
        return_metrics = result["return_metrics"]
        drawdown_metrics = result["drawdown_metrics"]
        if not isinstance(return_metrics, Mapping) or not isinstance(drawdown_metrics, Mapping):
            continue
        lines.append(
            "| {name} | {sample} | {skipped} | {avg} | {median} | {win} | {max_dd} | {avg_dd} | {worst} | {best} | {stops} | {takes} | {time_exit} |".format(
                name=name,
                sample=result["sample_size"],
                skipped=len(skipped_events) if isinstance(skipped_events, list) else 0,
                avg=_pct(return_metrics["avg_return"]),
                median=_pct(return_metrics["median_return"]),
                win=_pct(result["win_rate"]),
                max_dd=_pct(drawdown_metrics["max_drawdown"]),
                avg_dd=_pct(drawdown_metrics["avg_trade_drawdown"]),
                worst=_pct(return_metrics["worst_return"]),
                best=_pct(return_metrics["best_return"]),
                stops=exit_counts.get("stop_loss", 0),
                takes=exit_counts.get("take_profit", 0),
                time_exit=exit_counts.get("time_exit", 0),
            )
        )
    lines.extend(_render_signal_month_stability(payload))
    lines.extend(_render_market_breadth_stability(payload))
    return "\n".join(lines) + "\n"


def _build_stability(
    reports: Mapping[str, Mapping[str, object]],
    *,
    event_contexts: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    return {
        "signal_month": {
            variant_name: _group_trade_summaries(report, group_fn=lambda trade: str(trade["signal_date"])[:6])
            for variant_name, report in reports.items()
        },
        "market_breadth_ma20_bucket": {
            variant_name: _group_trade_summaries(
                report,
                group_fn=lambda trade: _market_breadth_bucket(event_contexts.get(str(trade["event_id"]))),
            )
            for variant_name, report in reports.items()
        },
    }


def _group_trade_summaries(
    report: Mapping[str, object],
    *,
    group_fn: Callable[[Mapping[str, object]], str],
) -> dict[str, object]:
    trades = report.get("trades", [])
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    if not isinstance(trades, list):
        return {}
    for trade in trades:
        if isinstance(trade, Mapping):
            grouped[group_fn(trade)].append(trade)
    return {
        group_name: _summarize_trade_group(group_trades)
        for group_name, group_trades in sorted(grouped.items())
    }


def _summarize_trade_group(trades: Sequence[Mapping[str, object]]) -> dict[str, object]:
    returns = [float(trade["holding_return"]) for trade in trades]
    drawdowns = [float(trade["max_drawdown"]) for trade in trades]
    wins = sum(1 for value in returns if value > 0)
    exit_counts = Counter(str(trade.get("exit_reason", "")) for trade in trades)
    return {
        "sample_size": len(trades),
        "avg_return": mean(returns) if returns else 0.0,
        "median_return": median(returns) if returns else 0.0,
        "win_rate": wins / len(trades) if trades else 0.0,
        "max_drawdown": min(drawdowns) if drawdowns else 0.0,
        "avg_drawdown": mean(drawdowns) if drawdowns else 0.0,
        "worst_return": min(returns) if returns else 0.0,
        "best_return": max(returns) if returns else 0.0,
        "exit_reason_counts": dict(exit_counts),
    }


def _market_breadth_bucket(context: Mapping[str, object] | None) -> str:
    if context is None:
        return "unknown"
    market_temperature = context.get("market_temperature")
    if not isinstance(market_temperature, Mapping):
        return "unknown"
    raw_breadth = market_temperature.get("breadth_ma20")
    if raw_breadth is None:
        return "unknown"
    breadth = float(raw_breadth)
    if breadth < 0.35:
        return "breadth_lt_35"
    if breadth < 0.55:
        return "breadth_35_55"
    return "breadth_ge_55"


def _render_signal_month_stability(payload: Mapping[str, object]) -> list[str]:
    stability = payload.get("stability", {})
    if not isinstance(stability, Mapping):
        return []
    signal_month = stability.get("signal_month", {})
    if not isinstance(signal_month, Mapping):
        return []
    lines = [
        "",
        "## Signal Month Stability",
        "",
        "| variant | month | sample | avg | median | win | max_dd | worst | best | stops | takes | time_exit |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for variant_name, groups in signal_month.items():
        if not isinstance(groups, Mapping):
            continue
        for month, summary in groups.items():
            if not isinstance(summary, Mapping):
                continue
            exit_counts = summary.get("exit_reason_counts", {})
            if not isinstance(exit_counts, Mapping):
                exit_counts = {}
            lines.append(
                "| {variant} | {month} | {sample} | {avg} | {median} | {win} | {max_dd} | {worst} | {best} | {stops} | {takes} | {time_exit} |".format(
                    variant=variant_name,
                    month=month,
                    sample=summary["sample_size"],
                    avg=_pct(summary["avg_return"]),
                    median=_pct(summary["median_return"]),
                    win=_pct(summary["win_rate"]),
                    max_dd=_pct(summary["max_drawdown"]),
                    worst=_pct(summary["worst_return"]),
                    best=_pct(summary["best_return"]),
                    stops=exit_counts.get("stop_loss", 0),
                    takes=exit_counts.get("take_profit", 0),
                    time_exit=exit_counts.get("time_exit", 0),
                )
            )
    return lines


def _render_market_breadth_stability(payload: Mapping[str, object]) -> list[str]:
    stability = payload.get("stability", {})
    if not isinstance(stability, Mapping):
        return []
    market_bucket = stability.get("market_breadth_ma20_bucket", {})
    if not isinstance(market_bucket, Mapping):
        return []
    lines = [
        "",
        "## Market Breadth MA20 Stability",
        "",
        "| variant | bucket | sample | avg | median | win | max_dd | worst | best | stops | takes | time_exit |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for variant_name, groups in market_bucket.items():
        if not isinstance(groups, Mapping):
            continue
        for bucket, summary in groups.items():
            if not isinstance(summary, Mapping):
                continue
            exit_counts = summary.get("exit_reason_counts", {})
            if not isinstance(exit_counts, Mapping):
                exit_counts = {}
            lines.append(
                "| {variant} | {bucket} | {sample} | {avg} | {median} | {win} | {max_dd} | {worst} | {best} | {stops} | {takes} | {time_exit} |".format(
                    variant=variant_name,
                    bucket=bucket,
                    sample=summary["sample_size"],
                    avg=_pct(summary["avg_return"]),
                    median=_pct(summary["median_return"]),
                    win=_pct(summary["win_rate"]),
                    max_dd=_pct(summary["max_drawdown"]),
                    worst=_pct(summary["worst_return"]),
                    best=_pct(summary["best_return"]),
                    stops=exit_counts.get("stop_loss", 0),
                    takes=exit_counts.get("take_profit", 0),
                    time_exit=exit_counts.get("time_exit", 0),
                )
            )
    return lines


def _pct(value: object) -> str:
    return f"{float(value) * 100:.2f}%"


if __name__ == "__main__":
    raise SystemExit(main())
