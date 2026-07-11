"""Build human-review queues for research sample annotation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ReviewLabelOption:
    """Numeric option used by humans to confirm a proposed sample label."""

    code: int
    event_class: str
    value_tier: str
    label: str
    description: str
    writes_to_sample_library: bool = True

    def to_mapping(self) -> dict[str, object]:
        return {
            "code": self.code,
            "event_class": self.event_class,
            "value_tier": self.value_tier,
            "label": self.label,
            "description": self.description,
            "writes_to_sample_library": self.writes_to_sample_library,
        }


DEFAULT_REVIEW_LABEL_OPTIONS: tuple[ReviewLabelOption, ...] = (
    ReviewLabelOption(
        code=1,
        event_class="positive_attention_high_value",
        value_tier="high",
        label="高价值正样本",
        description="核心口径校准样本，后续走势和形态语义都较强。",
    ),
    ReviewLabelOption(
        code=2,
        event_class="positive_attention_mid_value",
        value_tier="mid",
        label="中价值正样本",
        description="可以参与召回，但需要降权、确认或更强风控。",
    ),
    ReviewLabelOption(
        code=3,
        event_class="weak_or_excluded_attention",
        value_tier="low_or_exclude",
        label="弱样本或排除候选",
        description="形态不够稳健，适合沉淀降权或过滤条件。",
    ),
    ReviewLabelOption(
        code=4,
        event_class="borderline_negative_recall",
        value_tier="borderline_negative",
        label="边界负样本",
        description="召回可能有道理，但需要优化确认、风控或退出规则。",
    ),
    ReviewLabelOption(
        code=5,
        event_class="negative_after_close_recall",
        value_tier="borderline_negative",
        label="召回后失败样本",
        description="召回后表现失败，优先用于失败归因，不直接等同入口错误。",
    ),
    ReviewLabelOption(
        code=6,
        event_class="hard_negative_recall",
        value_tier="hard_negative",
        label="硬负样本",
        description="入口形态或趋势质量明确失败，适合沉淀排除条件。",
    ),
    ReviewLabelOption(
        code=7,
        event_class="out_of_family",
        value_tier="out_of_family",
        label="形态族外",
        description="样本可能有研究价值，但不属于当前稳健上升趋势突破形态族。",
    ),
    ReviewLabelOption(
        code=8,
        event_class="skip_uncertain",
        value_tier="uncertain",
        label="跳过/证据不足",
        description="暂不入库，等待更多图形、日期、回测或上下文证据。",
        writes_to_sample_library=False,
    ),
)


@dataclass(frozen=True)
class AnnotationSuggestionPolicy:
    """Thresholds for proposing sample labels before human confirmation."""

    high_value_return_threshold: float = 0.15
    mid_positive_return_threshold: float = 0.05
    hard_negative_return_threshold: float = -0.10
    hard_negative_drawdown_threshold: float = -0.18
    controlled_high_value_drawdown_threshold: float = -0.12
    high_setup_score_threshold: float = 75.0
    high_ma30_hold_ratio_90d_threshold: float = 0.80
    high_max_ma30_deviation_pct: float = 0.25
    max_review_items: int = 50

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "AnnotationSuggestionPolicy":
        if payload is None:
            return cls()
        valid_fields = set(cls.__dataclass_fields__)
        values = {key: value for key, value in payload.items() if key in valid_fields}
        return cls(**values)

    def to_mapping(self) -> dict[str, object]:
        return {
            "high_value_return_threshold": self.high_value_return_threshold,
            "mid_positive_return_threshold": self.mid_positive_return_threshold,
            "hard_negative_return_threshold": self.hard_negative_return_threshold,
            "hard_negative_drawdown_threshold": self.hard_negative_drawdown_threshold,
            "controlled_high_value_drawdown_threshold": self.controlled_high_value_drawdown_threshold,
            "high_setup_score_threshold": self.high_setup_score_threshold,
            "high_ma30_hold_ratio_90d_threshold": self.high_ma30_hold_ratio_90d_threshold,
            "high_max_ma30_deviation_pct": self.high_max_ma30_deviation_pct,
            "max_review_items": self.max_review_items,
        }


@dataclass(frozen=True)
class AnnotationQueueItem:
    """One proposed sample event requiring human review."""

    queue_item_id: str
    asset_id: str
    asset_name: str
    trade_date: str
    timeframe: str
    source_lane: str
    label_status: str
    suggested_event_class: str
    suggested_value_tier: str
    suggested_review_code: int | None
    suggestion_confidence: str
    suggestion_reasons: tuple[str, ...]
    metrics: Mapping[str, object] = field(default_factory=dict)
    backtest_evidence: Mapping[str, object] | None = None
    reviewer: str | None = None
    review_notes: str | None = None
    confirmed_event_class: str | None = None
    confirmed_value_tier: str | None = None

    def to_mapping(self) -> dict[str, object]:
        return {
            "queue_item_id": self.queue_item_id,
            "asset_id": self.asset_id,
            "asset_name": self.asset_name,
            "trade_date": self.trade_date,
            "timeframe": self.timeframe,
            "source_lane": self.source_lane,
            "label_status": self.label_status,
            "suggested_event_class": self.suggested_event_class,
            "suggested_value_tier": self.suggested_value_tier,
            "suggested_review_code": self.suggested_review_code,
            "review_code_prompt": "填写 review_label_options 中的数字 code；不要直接输入标签文字。",
            "suggestion_confidence": self.suggestion_confidence,
            "suggestion_reasons": list(self.suggestion_reasons),
            "metrics": dict(self.metrics),
            "backtest_evidence": dict(self.backtest_evidence) if self.backtest_evidence else None,
            "human_review": {
                "reviewer": self.reviewer,
                "review_notes": self.review_notes,
                "confirmed_event_class": self.confirmed_event_class,
                "confirmed_value_tier": self.confirmed_value_tier,
            },
        }


@dataclass(frozen=True)
class AnnotationQueue:
    """Human-review queue for proposed sample labels."""

    queue_id: str
    source_scan_result_path: str | None
    source_event_backtest_path: str | None
    candidate_key: str
    holding_horizon: int | None
    policy: AnnotationSuggestionPolicy
    items: tuple[AnnotationQueueItem, ...]

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "queue_id": self.queue_id,
            "label_status": "proposed",
            "requires_human_confirmation": True,
            "source_scan_result_path": self.source_scan_result_path,
            "source_event_backtest_path": self.source_event_backtest_path,
            "candidate_key": self.candidate_key,
            "holding_horizon": self.holding_horizon,
            "policy": self.policy.to_mapping(),
            "review_input_format": "queue_item_id<TAB>review_code",
            "review_label_options": [option.to_mapping() for option in DEFAULT_REVIEW_LABEL_OPTIONS],
            "summary": summarize_annotation_items(self.items),
            "items": [item.to_mapping() for item in self.items],
        }


def build_annotation_queue(
    scan_payload: Mapping[str, Any],
    *,
    event_backtest_payload: Mapping[str, Any] | None = None,
    policy: AnnotationSuggestionPolicy | None = None,
    candidate_key: str = "breakout_candidates",
    holding_horizon: int | None = None,
    source_lane: str = "scan_candidate_review",
    queue_id: str = "research_annotation_queue.steady_uptrend_breakout",
    source_scan_result_path: str | None = None,
    source_event_backtest_path: str | None = None,
) -> AnnotationQueue:
    """Build a proposed annotation queue from scan and optional L6 backtest output."""

    active_policy = policy or AnnotationSuggestionPolicy()
    trades = _trade_evidence_by_event(event_backtest_payload, holding_horizon)
    candidates = _candidate_rows(scan_payload, candidate_key)
    items = tuple(
        _build_item(
            candidate=candidate,
            trade=trades.get(_event_key(candidate)),
            policy=active_policy,
            source_lane=source_lane,
        )
        for candidate in candidates[: active_policy.max_review_items]
    )
    return AnnotationQueue(
        queue_id=queue_id,
        source_scan_result_path=source_scan_result_path,
        source_event_backtest_path=source_event_backtest_path,
        candidate_key=candidate_key,
        holding_horizon=holding_horizon,
        policy=active_policy,
        items=items,
    )


def summarize_annotation_items(items: tuple[AnnotationQueueItem, ...]) -> dict[str, object]:
    """Summarize proposed labels in a review queue."""

    by_suggestion: dict[str, int] = {}
    for item in items:
        by_suggestion[item.suggested_event_class] = by_suggestion.get(item.suggested_event_class, 0) + 1
    return {
        "item_count": len(items),
        "by_suggested_event_class": by_suggestion,
        "all_items_require_human_confirmation": all(item.label_status == "proposed" for item in items),
    }


def _build_item(
    *,
    candidate: Mapping[str, Any],
    trade: Mapping[str, Any] | None,
    policy: AnnotationSuggestionPolicy,
    source_lane: str,
) -> AnnotationQueueItem:
    suggested_event_class, suggested_value_tier, confidence, reasons = _suggest_label(candidate, trade, policy)
    asset_id = str(candidate.get("asset_id", ""))
    trade_date = str(candidate.get("trade_date", ""))
    return AnnotationQueueItem(
        queue_item_id=f"{asset_id}.{trade_date}.{source_lane}",
        asset_id=asset_id,
        asset_name=str(candidate.get("name", "")),
        trade_date=trade_date,
        timeframe="daily",
        source_lane=source_lane,
        label_status="proposed",
        suggested_event_class=suggested_event_class,
        suggested_value_tier=suggested_value_tier,
        suggested_review_code=_suggested_review_code(suggested_event_class),
        suggestion_confidence=confidence,
        suggestion_reasons=tuple(reasons),
        metrics=_compact_candidate_metrics(candidate),
        backtest_evidence=trade,
    )


def _suggest_label(
    candidate: Mapping[str, Any],
    trade: Mapping[str, Any] | None,
    policy: AnnotationSuggestionPolicy,
) -> tuple[str, str, str, list[str]]:
    reasons: list[str] = []
    if _has_hard_quality_failure(candidate):
        reasons.append("扫描指标显示趋势质量或日线质量失败，优先作为入口排除候选。")
        return ("hard_negative_recall", "hard_negative", "medium", reasons)

    if trade:
        holding_return = float(trade.get("holding_return", 0.0))
        max_drawdown = float(trade.get("max_drawdown", 0.0))
        reasons.append(f"L6 event backtest holding_return={holding_return:.4f}.")
        reasons.append(f"L6 event backtest max_drawdown={max_drawdown:.4f}.")
        if (
            holding_return >= policy.high_value_return_threshold
            and max_drawdown >= policy.controlled_high_value_drawdown_threshold
        ):
            reasons.append("收益达到高价值阈值且持有期回撤受控。")
            return ("positive_attention_high_value", "high", "medium", reasons)
        if holding_return >= policy.mid_positive_return_threshold:
            reasons.append("收益达到中价值正样本阈值，但仍需人工确认形态语义。")
            return ("positive_attention_mid_value", "mid", "medium", reasons)
        if (
            holding_return <= policy.hard_negative_return_threshold
            or max_drawdown <= policy.hard_negative_drawdown_threshold
        ):
            reasons.append("后续收益或回撤明显失败，先作为召回后失败样本而非硬负样本。")
            return ("negative_after_close_recall", "borderline_negative", "medium", reasons)
        if holding_return < 0:
            reasons.append("后续收益为负，但未达到硬失败阈值，适合作为边界负样本待审。")
            return ("borderline_negative_recall", "borderline_negative", "medium", reasons)

    if _looks_like_high_quality_positive(candidate, policy):
        reasons.append("扫描指标满足高分、MA30 稳定和不过度乖离条件。")
        return ("positive_attention_high_value", "high", "low", reasons)
    if bool(candidate.get("breakout_watch")) or bool(candidate.get("pre_breakout_watch")):
        reasons.append("候选通过突破或突破前观察扫描条件，但缺少 L6 结果确认。")
        return ("positive_attention_mid_value", "mid", "low", reasons)

    reasons.append("扫描和回测证据不足，保留为不确定样本待审。")
    return ("uncertain_review_required", "uncertain", "low", reasons)


def _has_hard_quality_failure(candidate: Mapping[str, Any]) -> bool:
    if candidate.get("daily_quality_pass") is False or candidate.get("trend_stability_pass") is False:
        return True
    return bool(candidate.get("quality_failure_reasons"))


def _looks_like_high_quality_positive(
    candidate: Mapping[str, Any],
    policy: AnnotationSuggestionPolicy,
) -> bool:
    return (
        float(candidate.get("setup_score", 0.0)) >= policy.high_setup_score_threshold
        and bool(candidate.get("close_new_high_60d_flag"))
        and float(candidate.get("ma30_hold_ratio_90d", 0.0)) >= policy.high_ma30_hold_ratio_90d_threshold
        and float(candidate.get("ma30_deviation_pct", 1.0)) <= policy.high_max_ma30_deviation_pct
    )


def _compact_candidate_metrics(candidate: Mapping[str, Any]) -> dict[str, object]:
    keys = (
        "source_bucket",
        "source_signal_date",
        "selection_reason",
        "industry",
        "market",
        "primary_reason",
        "setup_score",
        "breakout_watch",
        "pre_breakout_watch",
        "daily_quality_pass",
        "trend_stability_pass",
        "context_strength_pass",
        "close_new_high_60d_flag",
        "ma30_deviation_pct",
        "ma30_hold_ratio_90d",
        "red_k_ratio_20d",
        "long_shadow_ratio_20d",
        "max_drawdown_60d",
        "max_drawdown_120d",
        "amount_ratio_20d",
        "quality_failure_reasons",
        "strong_industry_names",
        "strong_concept_names",
    )
    return {key: candidate[key] for key in keys if key in candidate}


def _candidate_rows(scan_payload: Mapping[str, Any], candidate_key: str) -> tuple[Mapping[str, Any], ...]:
    candidates = scan_payload.get(candidate_key, ())
    if not isinstance(candidates, list):
        raise ValueError(f"{candidate_key} must be a list")
    rows: list[Mapping[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError(f"{candidate_key} items must be JSON objects")
        rows.append(candidate)
    return tuple(rows)


def _trade_evidence_by_event(
    event_backtest_payload: Mapping[str, Any] | None,
    holding_horizon: int | None,
) -> dict[str, Mapping[str, Any]]:
    if not event_backtest_payload:
        return {}
    reports = event_backtest_payload.get("reports", ())
    if not isinstance(reports, list) or not reports:
        return {}
    report = _select_report(reports, holding_horizon)
    trades = report.get("trades", ())
    if not isinstance(trades, list):
        return {}
    return {
        str(trade.get("event_id")): trade
        for trade in trades
        if isinstance(trade, Mapping) and trade.get("event_id")
    }


def _select_report(reports: list[object], holding_horizon: int | None) -> Mapping[str, Any]:
    mapping_reports = [report for report in reports if isinstance(report, Mapping)]
    if not mapping_reports:
        return {}
    if holding_horizon is not None:
        for report in mapping_reports:
            result = report.get("result", {})
            if isinstance(result, Mapping) and result.get("holding_horizon") == holding_horizon:
                return report
    return max(
        mapping_reports,
        key=lambda item: int(item.get("result", {}).get("holding_horizon", 0))
        if isinstance(item.get("result", {}), Mapping)
        else 0,
    )


def _event_key(candidate: Mapping[str, Any]) -> str:
    return f"{candidate.get('asset_id')}.{candidate.get('trade_date')}"


def _suggested_review_code(event_class: str) -> int | None:
    if event_class == "uncertain_review_required":
        return 8
    for option in DEFAULT_REVIEW_LABEL_OPTIONS:
        if option.event_class == event_class:
            return option.code
    return None
