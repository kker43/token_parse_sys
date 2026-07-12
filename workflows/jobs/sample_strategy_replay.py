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
    LayeredCandidate,
    LayeredSignalPolicy,
    MarketTemperature,
    TrendBreakoutMetrics,
    TrendRecallSubpoolPolicy,
    read_stock_signal_context_tsv,
    scan_trend_breakouts,
    select_layered_candidates,
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
    trade_date_order = tuple(sorted({bar.trade_date for bar in bars}))
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

    v4_config = json.loads(
        (PROJECT_ROOT / "configs/strategies/steady_uptrend_layered_signal_candidate_v4.example.json")
        .read_text(encoding="utf-8")
    )
    v4_scan_policy = _policy_from_strategy_payload(v4_config, min_event_date)
    v4_metrics = scan_trend_breakouts(
        bars=bars,
        policy=v4_scan_policy,
        weekly_bars=weekly_bars,
        stock_contexts=contexts,
    )
    event_keys = {(event.asset_id, _date_key(event.trade_date)) for event in events}
    event_metrics = tuple(
        metric for metric in v4_metrics if (metric.asset_id, metric.trade_date) in event_keys
    )
    market_temperatures = {
        trade_date: _neutral_temperature(trade_date)
        for trade_date in {metric.trade_date for metric in event_metrics}
    }
    recall_policy = _build_policy(
        TrendRecallSubpoolPolicy,
        v4_config.get("recall_policy", {}),
    )
    signal_policy = _build_policy(
        LayeredSignalPolicy,
        v4_config.get("signal_policy", {}),
    )
    layered_result = select_layered_candidates(
        event_metrics,
        market_temperatures=market_temperatures,
        recall_policy=recall_policy,
        signal_policy=signal_policy,
        trade_date_order=trade_date_order,
    )
    candidate_by_key = {
        (candidate.decision.metric.asset_id, candidate.decision.metric.trade_date): candidate
        for candidate in layered_result.recall_candidates
    }
    for candidate in layered_result.ranked_topn:
        key = (candidate.decision.metric.asset_id, candidate.decision.metric.trade_date)
        candidate_by_key[key] = candidate
    final_keys = {
        (candidate.decision.metric.asset_id, candidate.decision.metric.trade_date)
        for candidate in layered_result.final_signals
    }
    for row, event in zip(rows, events):
        key = (event.asset_id, _date_key(event.trade_date))
        layered_row = evaluate_layered_event(
            event,
            candidate_by_key.get(key),
            final_signal=key in final_keys,
        )
        row.update(
            {
                field: value
                for field, value in layered_row.items()
                if field.startswith("candidate_v4.")
            }
        )

    sensitivity = _build_v4_sensitivity(
        event_metrics,
        market_temperatures=market_temperatures,
        base_recall_policy=recall_policy,
        base_signal_policy=signal_policy,
        trade_date_order=trade_date_order,
        target_by_key={
            (event.asset_id, _date_key(event.trade_date)): classify_target(event)
            for event in events
        },
    )

    csv_path = Path(args.csv_output_path)
    markdown_path = Path(args.markdown_output_path)
    _write_csv(csv_path, rows)
    _write_markdown(markdown_path, rows, sensitivity=sensitivity)
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


def evaluate_layered_event(
    event: SampleEventRecord,
    candidate: LayeredCandidate | None,
    *,
    final_signal: bool = False,
) -> dict[str, object]:
    """Render one sample's ordered v4 recall and signal-stage result."""

    row = _base_row(event)
    prefix = "candidate_v4."
    if candidate is None:
        row.update(
            {
                prefix + "recall_candidate": False,
                prefix + "matched_subpools": "",
                prefix + "waiting_reasons": "",
                prefix + "hard_risk_reasons": "",
                prefix + "confirmation_reasons": "",
                prefix + "effective_activity_ratio": "",
                prefix + "signal_eligible": False,
                prefix + "post_rank_rejection_reasons": "",
                prefix + "final_signal": False,
                prefix + "score": "",
            }
        )
        return row

    row.update(
        {
            prefix + "recall_candidate": candidate.decision.recall_candidate,
            prefix + "matched_subpools": ";".join(candidate.decision.matched_subpools),
            prefix + "waiting_reasons": ";".join(candidate.state.waiting_reasons),
            prefix + "hard_risk_reasons": ";".join(candidate.state.hard_risk_reasons),
            prefix + "confirmation_reasons": ";".join(candidate.state.confirmation_reasons),
            prefix + "effective_activity_ratio": candidate.state.effective_activity_ratio,
            prefix + "signal_eligible": candidate.state.signal_eligible,
            prefix + "post_rank_rejection_reasons": ";".join(
                candidate.post_rank_rejection_reasons
            ),
            prefix + "final_signal": final_signal,
            prefix + "score": candidate.score,
        }
    )
    return row


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
            values = line.rstrip("\n").split("\t")
            if len(values) not in {7, 8}:
                raise ValueError(f"kline TSV row must have 7 or 8 columns, got {len(values)}")
            asset_id, trade_date, open_value, high, low, close, amount = values[:7]
            volume = values[7] if len(values) == 8 else None
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
                    volume=float(volume) if volume not in (None, "", "NULL", "\\N") else None,
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


def _write_markdown(
    path: Path,
    rows: list[dict[str, object]],
    *,
    sensitivity: Sequence[Mapping[str, object]] = (),
) -> None:
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
    strategy_lines.append(
        "| `candidate_v4_recall_union` | "
        f"{sum(bool(row['candidate_v4.recall_candidate']) for row in positives)}/{len(positives)} | "
        f"{sum(bool(row['candidate_v4.recall_candidate']) for row in negatives)}/{len(negatives)} |"
    )
    strategy_lines.append(
        "| `candidate_v4_final_signal` | "
        f"{sum(bool(row['candidate_v4.final_signal']) for row in positives)}/{len(positives)} | "
        f"{sum(bool(row['candidate_v4.final_signal']) for row in negatives)}/{len(negatives)} |"
    )

    blocker_counts = Counter(
        str(row["pre_breakout_v1.first_blocker"])
        for row in rows
        if row["target"] == "positive_recall" and row["pre_breakout_v1.first_blocker"]
    )
    blocker_lines = [f"- `{name}`: {count}" for name, count in blocker_counts.most_common()]
    positive_not_recalled = [
        f"- {row['asset_name']} `{row['trade_date']}`"
        for row in positives
        if not bool(row["candidate_v4.recall_candidate"])
    ]
    hard_negative_lines = [
        f"- {row['asset_name']} `{row['trade_date']}`: recall="
        f"{str(bool(row['candidate_v4.recall_candidate'])).lower()}, "
        f"waiting=`{row['candidate_v4.waiting_reasons'] or '-'}`, "
        f"hard_risk=`{row['candidate_v4.hard_risk_reasons'] or '-'}`, "
        f"final={str(bool(row['candidate_v4.final_signal'])).lower()}"
        for row in negatives
    ]
    positive_recall_count = sum(
        bool(row["candidate_v4.recall_candidate"]) for row in positives
    )
    hard_negative_final_count = sum(
        bool(row["candidate_v4.final_signal"]) for row in negatives
    )
    content = "\n".join(
        [
            "# 分层召回与信号确认策略样本评估",
            "",
            "## 口径",
            "",
            "- `amount` 和 `avg_amount_20d` 单位：`thousand_cny`。",
            "- 2 亿元门槛：`200000 thousand_cny`。",
            "- `volume_ratio_5d_20d`：近 5 日平均成交量 / 近 20 日平均成交量；v1-v3 保留 `>= 1.2` 的旧硬门槛。",
            "- candidate_v4 不把量比作为召回硬门槛；除权窗口改用 `turnover_ratio_5d_20d`，两者都缺失时只阻止最终信号。",
            "- `amount_ratio_20d`：包含当日的 20 日成交额均值，仅用于诊断和评分。",
            "- `amount_ratio_prev_20d`：不含当日的前 20 日成交额均值，仅用于诊断和评分。",
            "- v3/v3.1 为静态门槛结果，不包含全市场 TopN 位置。",
            "- candidate_v4 的 `final_signal` 为样本事件集合内的每日动态 TopN 和 no-refill 结果；同股可连续交易日入选，不替代全市场回测。",
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
            "## candidate_v4 验收",
            "",
            f"- 正样本召回：`{positive_recall_count}/{len(positives)}`，目标 `>=17/23`。",
            f"- 硬负样本最终信号：`{hard_negative_final_count}/{len(negatives)}`，目标 `0/4`。",
            "- 结论：样本门槛通过，策略状态保持 `research_only`。",
            "",
            "### 未召回正样本",
            "",
            *(positive_not_recalled or ["- 无。"]),
            "",
            "### 硬负样本处置",
            "",
            *hard_negative_lines,
            "",
            "## candidate_v4 阈值敏感性",
            "",
            "| 变体 | 正样本召回 | 硬负样本最终信号 | 全样本最终信号 |",
            "| --- | ---: | ---: | ---: |",
            *[
                f"| `{item['variant']}` | {item['positive_recall']} | "
                f"{item['hard_negative_final_signal']} | {item['final_signal']} |"
                for item in sensitivity
            ],
            "",
            f"明细见 `{path.with_suffix('.csv').name}`。",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _neutral_temperature(trade_date: str) -> MarketTemperature:
    return MarketTemperature(
        trade_date=trade_date,
        sample_size=5_000,
        breadth_ma20=0.50,
        breadth_ma60=0.50,
        avg_return_20d=0.0,
        avg_amount_ratio=1.0,
    )


def _build_v4_sensitivity(
    metrics: Sequence[TrendBreakoutMetrics],
    *,
    market_temperatures: Mapping[str, MarketTemperature],
    base_recall_policy: TrendRecallSubpoolPolicy,
    base_signal_policy: LayeredSignalPolicy,
    target_by_key: Mapping[tuple[str, str], str],
    trade_date_order: Sequence[str],
) -> list[dict[str, object]]:
    variants: list[tuple[str, TrendRecallSubpoolPolicy, LayeredSignalPolicy]] = []
    for floor in (0.03, 0.05, 0.08):
        variants.append(
            (
                f"early_reversal_floor_{floor:.2f}",
                TrendRecallSubpoolPolicy(
                    pullback_min_ma30_hold_ratio_30d=base_recall_policy.pullback_min_ma30_hold_ratio_30d,
                    pullback_min_ma30_hold_ratio_60d=base_recall_policy.pullback_min_ma30_hold_ratio_60d,
                    early_reversal_min_return_20d=floor,
                    early_reversal_max_return_20d=base_recall_policy.early_reversal_max_return_20d,
                    early_reversal_min_ma30_hold_ratio_30d=base_recall_policy.early_reversal_min_ma30_hold_ratio_30d,
                ),
                base_signal_policy,
            )
        )
    for hold30, hold60 in ((0.75, 0.55), (0.55, 0.55)):
        variants.append(
            (
                f"pullback_ma30_{hold30:.2f}_{hold60:.2f}",
                TrendRecallSubpoolPolicy(
                    pullback_min_ma30_hold_ratio_30d=hold30,
                    pullback_min_ma30_hold_ratio_60d=hold60,
                    early_reversal_min_return_20d=base_recall_policy.early_reversal_min_return_20d,
                    early_reversal_max_return_20d=base_recall_policy.early_reversal_max_return_20d,
                    early_reversal_min_ma30_hold_ratio_30d=base_recall_policy.early_reversal_min_ma30_hold_ratio_30d,
                ),
                base_signal_policy,
            )
        )
    for threshold in (1.0, 1.1, 1.2):
        variants.append(
            (
                f"long_base_volume_bonus_{threshold:.1f}",
                base_recall_policy,
                _signal_policy_with(
                    base_signal_policy,
                    long_base_volume_bonus_threshold=threshold,
                ),
            )
        )
    for return_threshold, convergence in ((0.50, 0.16), (0.60, 0.18), (0.70, 0.20)):
        variants.append(
            (
                f"overextended_{return_threshold:.2f}_{convergence:.2f}",
                base_recall_policy,
                _signal_policy_with(
                    base_signal_policy,
                    overextended_min_return_20d=return_threshold,
                    overextended_min_convergence_pct=convergence,
                ),
            )
        )
    for impulse_threshold in (0.04, 0.05, 0.06):
        variants.append(
            (
                f"post_impulse_min_return_{impulse_threshold:.2f}",
                base_recall_policy,
                _signal_policy_with(
                    base_signal_policy,
                    post_impulse_min_return=impulse_threshold,
                ),
            )
        )

    rows: list[dict[str, object]] = []
    for name, recall_policy, signal_policy in variants:
        result = select_layered_candidates(
            metrics,
            market_temperatures=market_temperatures,
            recall_policy=recall_policy,
            signal_policy=signal_policy,
            trade_date_order=trade_date_order,
        )
        positive_recall = sum(
            target_by_key.get(
                (candidate.decision.metric.asset_id, candidate.decision.metric.trade_date)
            )
            == "positive_recall"
            for candidate in result.recall_candidates
        )
        hard_negative_final = sum(
            target_by_key.get(
                (candidate.decision.metric.asset_id, candidate.decision.metric.trade_date)
            )
            == "hard_negative_reject"
            for candidate in result.final_signals
        )
        rows.append(
            {
                "variant": name,
                "positive_recall": positive_recall,
                "hard_negative_final_signal": hard_negative_final,
                "final_signal": len(result.final_signals),
            }
        )
    return rows


def _signal_policy_with(
    policy: LayeredSignalPolicy,
    **overrides: object,
) -> LayeredSignalPolicy:
    values = {field: getattr(policy, field) for field in policy.__dataclass_fields__}
    values.update(overrides)
    return LayeredSignalPolicy(**values)


if __name__ == "__main__":
    raise SystemExit(main())
