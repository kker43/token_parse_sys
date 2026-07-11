"""Replay registered sample events against repaired strategy inputs."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.research import (
    KlineBar,
    MarketTemperature,
    TrendBreakoutMetrics,
    read_stock_signal_context_tsv,
    scan_trend_breakouts,
    v3_rejection_reasons,
)
from stock_lobster.research.sample_library import (
    SampleEventRecord,
    extract_sample_events,
    load_sample_library,
)
from stock_lobster.research.trend_recall_subpools import (
    classify_recall_subpools,
    matched_subpool_ids,
)
from workflows.jobs.daily_strategy_signal_production import _policy_from_strategy_payload
from workflows.jobs.steady_uptrend_v3_research_scan import _build_policy
from stock_lobster.research.steady_uptrend_v3 import SteadyUptrendV3Policy


STRATEGIES = (
    ("breakout_v1", "configs/strategies/steady_uptrend_breakout_watch.example.json", "breakout", False),
    (
        "breakout_v2_weak_shape",
        "configs/strategies/steady_uptrend_breakout_watch_candidate_v2.example.json",
        "breakout",
        False,
    ),
    (
        "pre_breakout_v1",
        "configs/strategies/steady_uptrend_pre_breakout_watch.example.json",
        "pre_breakout",
        False,
    ),
    (
        "pre_breakout_v3",
        "configs/strategies/steady_uptrend_pre_breakout_watch_candidate_v3.example.json",
        "all",
        True,
    ),
    (
        "pre_breakout_v3_1",
        "configs/strategies/steady_uptrend_pre_breakout_watch_candidate_v3_1.example.json",
        "all",
        True,
    ),
)


def classify_target(event: SampleEventRecord) -> str:
    """Map the approved sample taxonomy to replay targets."""

    if event.is_positive:
        return "positive_recall"
    if event.is_hard_negative:
        return "hard_negative_reject"
    if event.is_weak_or_excluded:
        return "exclude_or_low"
    if event.is_borderline_negative:
        return "wait_or_observe_only"
    return "unknown"


def ordered_blockers(
    metric: Mapping[str, object] | None,
    *,
    mode: str,
    min_volume_ratio_5d_20d: float = 1.2,
    min_close_to_high_60d_pct: float = -0.08,
    max_close_to_high_60d_pct: float = -0.002,
    min_sustained_ma30_hold_ratio_90d: float = 0.75,
) -> tuple[str, ...]:
    """Return blockers in pipeline order for one metric mapping."""

    if metric is None:
        return ("missing_metrics",)
    if not bool(metric.get("daily_quality_pass")):
        reasons = tuple(str(value) for value in metric.get("quality_failure_reasons", ()))
        return reasons or ("daily_quality_failed",)
    if not bool(metric.get("steady_uptrend")):
        return ("steady_uptrend_failed",)

    new_high = bool(metric.get("close_new_high_60d_flag"))
    volume_ratio_raw = metric.get("volume_ratio_5d_20d")
    if mode == "breakout":
        if not new_high:
            return ("close_not_new_high_60d",)
        if volume_ratio_raw in (None, ""):
            return ("volume_ratio_5d_20d_missing",)
        if float(volume_ratio_raw) < min_volume_ratio_5d_20d:
            return (f"volume_ratio_5d_20d_below_{min_volume_ratio_5d_20d:g}",)
        return ()

    if mode == "pre_breakout":
        if new_high:
            return ("already_new_high_60d",)
        if float(metric.get("ma30_hold_ratio_90d", 0.0)) < min_sustained_ma30_hold_ratio_90d:
            return ("pre_breakout_ma30_sustained_failed",)
        close_to_high = float(metric.get("close_to_high_60d_pct", -1.0))
        if close_to_high < min_close_to_high_60d_pct:
            return ("pre_breakout_too_far_from_high",)
        if close_to_high > max_close_to_high_60d_pct:
            return ("pre_breakout_too_close_to_high",)
        if volume_ratio_raw in (None, ""):
            return ("volume_ratio_5d_20d_missing",)
        if float(volume_ratio_raw) < min_volume_ratio_5d_20d:
            return (f"volume_ratio_5d_20d_below_{min_volume_ratio_5d_20d:g}",)
        return ()

    if bool(metric.get("breakout_watch")) or bool(metric.get("pre_breakout_watch")):
        return ()
    return ("no_breakout_or_pre_breakout_trigger",)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sample_strategy_replay")
    parser.add_argument("--sample-library-path", required=True)
    parser.add_argument("--kline-tsv-path", required=True)
    parser.add_argument("--weekly-kline-tsv-path", required=True)
    parser.add_argument("--stock-context-tsv-path", required=True)
    parser.add_argument("--csv-output-path", required=True)
    parser.add_argument("--markdown-output-path", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    library = load_sample_library(args.sample_library_path)
    events = tuple(
        event
        for event in extract_sample_events(library)
        if event.timeframe == "daily" and event.trade_date
    )
    asset_ids = {event.asset_id for event in events}
    min_event_date = min(_date_key(event.trade_date) for event in events)
    bars = _read_filtered_kline(Path(args.kline_tsv_path), asset_ids)
    weekly_bars = _read_filtered_kline(Path(args.weekly_kline_tsv_path), asset_ids)
    contexts = tuple(
        context
        for context in read_stock_signal_context_tsv(args.stock_context_tsv_path)
        if context.asset_id in asset_ids
    )

    rows = [_base_row(event) for event in events]
    for strategy_id, relative_config_path, mode, use_v3 in STRATEGIES:
        config = json.loads((PROJECT_ROOT / relative_config_path).read_text(encoding="utf-8"))
        policy = _policy_from_strategy_payload(config, min_event_date)
        metrics = scan_trend_breakouts(
            bars=bars,
            policy=policy,
            weekly_bars=weekly_bars,
            stock_contexts=contexts,
        )
        metric_by_key = {(metric.asset_id, metric.trade_date): metric for metric in metrics}
        v3_policy = (
            _build_policy(SteadyUptrendV3Policy, config.get("v3_filter_policy", {}))
            if use_v3
            else None
        )
        for row, event in zip(rows, events):
            metric = metric_by_key.get((event.asset_id, _date_key(event.trade_date)))
            _add_strategy_result(
                row=row,
                strategy_id=strategy_id,
                metric=metric,
                mode=mode,
                policy=policy,
                v3_policy=v3_policy,
            )
            if strategy_id == "pre_breakout_v1":
                matches = classify_recall_subpools(metric) if metric else {}
                row["trend_recall_subpools.selected"] = any(
                    match.matched for match in matches.values()
                )
                row["trend_recall_subpools.matched_subpools"] = ";".join(
                    matched_subpool_ids(matches)
                )

    csv_path = Path(args.csv_output_path)
    markdown_path = Path(args.markdown_output_path)
    _write_csv(csv_path, rows)
    _write_markdown(markdown_path, rows)
    print(json.dumps({"event_count": len(rows), "csv": str(csv_path), "markdown": str(markdown_path)}))
    return 0


def _base_row(event: SampleEventRecord) -> dict[str, object]:
    return {
        "sample_id": event.sample_id,
        "asset_id": event.asset_id,
        "asset_name": event.asset_name,
        "event_id": event.event_id,
        "trade_date": _date_key(event.trade_date),
        "event_class": event.event_class,
        "value_tier": event.value_tier or "",
        "target": classify_target(event),
    }


def _add_strategy_result(
    *,
    row: dict[str, object],
    strategy_id: str,
    metric: TrendBreakoutMetrics | None,
    mode: str,
    policy: object,
    v3_policy: SteadyUptrendV3Policy | None,
) -> None:
    mapping = metric.to_mapping() if metric else None
    blockers = ordered_blockers(
        mapping,
        mode=mode,
        min_volume_ratio_5d_20d=float(getattr(policy, "min_volume_ratio_5d_20d")),
        min_close_to_high_60d_pct=float(getattr(policy, "min_close_to_high_60d_pct")),
        max_close_to_high_60d_pct=float(getattr(policy, "max_close_to_high_60d_pct")),
        min_sustained_ma30_hold_ratio_90d=float(
            getattr(policy, "min_sustained_ma30_hold_ratio_90d")
        ),
    )
    if metric and not blockers and v3_policy is not None:
        temperature = MarketTemperature(
            trade_date=metric.trade_date,
            sample_size=5_000,
            breadth_ma20=0.0,
            breadth_ma60=0.0,
            avg_return_20d=0.0,
            avg_amount_ratio=1.0,
        )
        blockers = v3_rejection_reasons(metric, market_temperature=temperature, policy=v3_policy)

    prefix = f"{strategy_id}."
    row[prefix + "selected_static"] = bool(metric) and not blockers
    row[prefix + "blockers"] = ";".join(blockers)
    row[prefix + "first_blocker"] = blockers[0] if blockers else ""
    for field in (
        "close",
        "ma30",
        "daily_quality_pass",
        "trend_stability_pass",
        "steady_uptrend",
        "breakout_watch",
        "pre_breakout_watch",
        "avg_amount_20d",
        "amount_ratio_20d",
        "amount_ratio_prev_20d",
        "volume_ratio_5d_20d",
        "ma30_hold_ratio_30d",
        "ma30_hold_ratio_60d",
        "ma30_hold_ratio_90d",
        "close_to_high_60d_pct",
        "return_20d",
        "long_shadow_ratio_20d",
        "large_bearish_body_ratio_20d",
        "single_bull_bar_return_share_20d",
        "impulse_consolidation_days",
        "ma5_10_20_30_convergence_pct",
    ):
        row[prefix + field] = mapping.get(field, "") if mapping else ""


def _read_filtered_kline(path: Path, asset_ids: set[str]) -> tuple[KlineBar, ...]:
    bars: list[KlineBar] = []
    with path.open(encoding="utf-8") as file_obj:
        for line in file_obj:
            if not line.strip():
                continue
            asset_id, trade_date, open_value, high, low, close, amount = line.rstrip("\n").split("\t")
            if asset_id not in asset_ids:
                continue
            bars.append(
                KlineBar(
                    asset_id=asset_id,
                    trade_date=trade_date,
                    open=float(open_value),
                    high=float(high),
                    low=float(low),
                    close=float(close),
                    amount=float(amount),
                )
            )
    return tuple(bars)


def _date_key(value: str | None) -> str:
    return str(value or "").replace("-", "")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, rows: list[dict[str, object]]) -> None:
    strategy_lines = []
    for strategy_id, _, _, _ in STRATEGIES:
        selected_key = f"{strategy_id}.selected_static"
        positives = [row for row in rows if row["target"] == "positive_recall"]
        negatives = [row for row in rows if row["target"] == "hard_negative_reject"]
        strategy_lines.append(
            f"| `{strategy_id}` | {sum(bool(row[selected_key]) for row in positives)}/{len(positives)} "
            f"| {sum(bool(row[selected_key]) for row in negatives)}/{len(negatives)} |"
        )
    positives = [row for row in rows if row["target"] == "positive_recall"]
    negatives = [row for row in rows if row["target"] == "hard_negative_reject"]
    strategy_lines.append(
        "| `trend_recall_subpools_candidate_v1` | "
        f"{sum(bool(row['trend_recall_subpools.selected']) for row in positives)}/{len(positives)} | "
        f"{sum(bool(row['trend_recall_subpools.selected']) for row in negatives)}/{len(negatives)} |"
    )

    blocker_counts = Counter(
        str(row["pre_breakout_v1.first_blocker"])
        for row in rows
        if row["target"] == "positive_recall" and row["pre_breakout_v1.first_blocker"]
    )
    blocker_lines = [f"- `{name}`: {count}" for name, count in blocker_counts.most_common()]
    content = "\n".join(
        [
            "# 5/20 日成交量比统一门槛样本策略基线",
            "",
            "## 口径",
            "",
            "- `amount` 和 `avg_amount_20d` 单位：`thousand_cny`。",
            "- 2 亿元门槛：`200000 thousand_cny`。",
            "- `volume_ratio_5d_20d`：近 5 日平均成交量 / 近 20 日平均成交量，统一硬门槛为 `>= 1.2`。",
            "- `amount_ratio_20d`：包含当日的 20 日成交额均值，仅用于诊断和评分。",
            "- `amount_ratio_prev_20d`：不含当日的前 20 日成交额均值，仅用于诊断和评分。",
            "- v3/v3.1 为静态门槛结果，不包含跨日 cooldown 和全市场 TopN 位置。",
            "",
            "## 策略结果",
            "",
            "| 策略 | 正样本静态召回 | 硬负样本静态误召回 |",
            "| --- | ---: | ---: |",
            *strategy_lines,
            "",
            "## pre_breakout_v1 正样本首阻断",
            "",
            *blocker_lines,
            "",
            f"明细见 `{path.with_suffix('.csv').name}`。",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
