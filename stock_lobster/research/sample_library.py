"""Research sample library coverage and promotion readiness helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Any, Mapping


POSITIVE_EVENT_PREFIX = "positive_attention"


@dataclass(frozen=True)
class SampleLibraryGatePolicy:
    """Minimum coverage requirements before a sample library is strategy-review ready."""

    min_total_events: int = 40
    min_dated_events: int = 30
    min_positive_events: int = 30
    min_high_value_positive_events: int = 15
    min_negative_events: int = 15
    min_hard_negative_events: int = 8
    min_borderline_negative_events: int = 10

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "SampleLibraryGatePolicy":
        if payload is None:
            return cls()
        valid_fields = set(cls.__dataclass_fields__)
        values = {key: int(value) for key, value in payload.items() if key in valid_fields}
        return cls(**values)

    def to_mapping(self) -> dict[str, int]:
        return {
            "min_total_events": self.min_total_events,
            "min_dated_events": self.min_dated_events,
            "min_positive_events": self.min_positive_events,
            "min_high_value_positive_events": self.min_high_value_positive_events,
            "min_negative_events": self.min_negative_events,
            "min_hard_negative_events": self.min_hard_negative_events,
            "min_borderline_negative_events": self.min_borderline_negative_events,
        }


@dataclass(frozen=True)
class SampleEventRecord:
    """Normalized event record extracted from a research sample library."""

    sample_id: str
    asset_id: str
    asset_name: str
    sample_class: str
    event_id: str
    trade_date: str | None
    timeframe: str
    event_class: str
    value_tier: str | None

    @property
    def has_trade_date(self) -> bool:
        return bool(self.trade_date)

    @property
    def is_positive(self) -> bool:
        return self.event_class.startswith(POSITIVE_EVENT_PREFIX)

    @property
    def is_high_value_positive(self) -> bool:
        if not self.is_positive:
            return False
        return self.value_tier == "high" or "high_value" in self.event_class or "best" in self.event_class

    @property
    def is_negative(self) -> bool:
        return "negative" in self.event_class or (self.value_tier or "").endswith("negative")

    @property
    def is_hard_negative(self) -> bool:
        return "hard_negative" in self.event_class or self.value_tier == "hard_negative"

    @property
    def is_borderline_negative(self) -> bool:
        return "borderline_negative" in self.event_class or self.value_tier == "borderline_negative"

    @property
    def is_weak_or_excluded(self) -> bool:
        return "weak" in self.event_class or "excluded" in self.event_class or self.value_tier == "low_or_exclude"


@dataclass(frozen=True)
class SampleLibraryCoverage:
    """Sample coverage counts for one pattern family."""

    sample_library_id: str
    family_id: str
    family_name: str
    stock_count: int
    event_count: int
    dated_event_count: int
    positive_event_count: int
    high_value_positive_event_count: int
    negative_event_count: int
    hard_negative_event_count: int
    borderline_negative_event_count: int
    weak_or_excluded_event_count: int
    missing_trade_date_events: tuple[str, ...] = field(default_factory=tuple)

    def to_mapping(self) -> dict[str, object]:
        return {
            "sample_library_id": self.sample_library_id,
            "family_id": self.family_id,
            "family_name": self.family_name,
            "stock_count": self.stock_count,
            "event_count": self.event_count,
            "dated_event_count": self.dated_event_count,
            "positive_event_count": self.positive_event_count,
            "high_value_positive_event_count": self.high_value_positive_event_count,
            "negative_event_count": self.negative_event_count,
            "hard_negative_event_count": self.hard_negative_event_count,
            "borderline_negative_event_count": self.borderline_negative_event_count,
            "weak_or_excluded_event_count": self.weak_or_excluded_event_count,
            "missing_trade_date_events": list(self.missing_trade_date_events),
        }


@dataclass(frozen=True)
class SampleLibraryGateResult:
    """Coverage gate result used before strategy threshold tuning."""

    coverage: SampleLibraryCoverage
    policy: SampleLibraryGatePolicy
    passed: bool
    gaps: tuple[str, ...]
    next_actions: tuple[str, ...]

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "gate": "research_sample_library_coverage",
            "passed": self.passed,
            "coverage": self.coverage.to_mapping(),
            "policy": self.policy.to_mapping(),
            "gaps": list(self.gaps),
            "next_actions": list(self.next_actions),
        }


def load_sample_library(path: str | Path) -> Mapping[str, Any]:
    """Load one JSON research sample library."""

    return json.loads(Path(path).read_text(encoding="utf-8"))


def extract_sample_events(library: Mapping[str, Any]) -> tuple[SampleEventRecord, ...]:
    """Extract normalized event records from the current research sample JSON shape."""

    records: list[SampleEventRecord] = []
    for sample in library.get("samples", []):
        sample_id = str(sample.get("sample_id", ""))
        asset_id = str(sample.get("asset_id", ""))
        asset_name = str(sample.get("asset_name", ""))
        sample_class = str(sample.get("sample_class", ""))
        for event in sample.get("events", []):
            records.append(
                SampleEventRecord(
                    sample_id=sample_id,
                    asset_id=asset_id,
                    asset_name=asset_name,
                    sample_class=sample_class,
                    event_id=str(event.get("event_id", "")),
                    trade_date=event.get("trade_date"),
                    timeframe=str(event.get("timeframe", "")),
                    event_class=str(event.get("event_class", "")),
                    value_tier=event.get("value_tier"),
                )
            )
    return tuple(records)


def summarize_sample_library(library: Mapping[str, Any]) -> SampleLibraryCoverage:
    """Summarize stock and event coverage for a sample library."""

    events = extract_sample_events(library)
    missing_trade_date_events = tuple(
        event.event_id for event in events if not event.has_trade_date and event.timeframe == "daily"
    )
    return SampleLibraryCoverage(
        sample_library_id=str(library.get("sample_library_id", "")),
        family_id=str(library.get("family_id", "")),
        family_name=str(library.get("family_name", "")),
        stock_count=len(library.get("samples", [])),
        event_count=len(events),
        dated_event_count=sum(1 for event in events if event.has_trade_date),
        positive_event_count=sum(1 for event in events if event.is_positive),
        high_value_positive_event_count=sum(1 for event in events if event.is_high_value_positive),
        negative_event_count=sum(1 for event in events if event.is_negative),
        hard_negative_event_count=sum(1 for event in events if event.is_hard_negative),
        borderline_negative_event_count=sum(1 for event in events if event.is_borderline_negative),
        weak_or_excluded_event_count=sum(1 for event in events if event.is_weak_or_excluded),
        missing_trade_date_events=missing_trade_date_events,
    )


def evaluate_sample_library(
    library: Mapping[str, Any],
    policy: SampleLibraryGatePolicy | None = None,
) -> SampleLibraryGateResult:
    """Evaluate whether a sample library has enough coverage for strategy tuning."""

    gate_policy = policy or SampleLibraryGatePolicy()
    coverage = summarize_sample_library(library)
    gaps = _build_gaps(coverage=coverage, policy=gate_policy)
    return SampleLibraryGateResult(
        coverage=coverage,
        policy=gate_policy,
        passed=not gaps,
        gaps=tuple(gaps),
        next_actions=tuple(_build_next_actions(coverage=coverage, policy=gate_policy)),
    )


def _build_gaps(coverage: SampleLibraryCoverage, policy: SampleLibraryGatePolicy) -> list[str]:
    checks = (
        ("total_events", coverage.event_count, policy.min_total_events),
        ("dated_events", coverage.dated_event_count, policy.min_dated_events),
        ("positive_events", coverage.positive_event_count, policy.min_positive_events),
        (
            "high_value_positive_events",
            coverage.high_value_positive_event_count,
            policy.min_high_value_positive_events,
        ),
        ("negative_events", coverage.negative_event_count, policy.min_negative_events),
        ("hard_negative_events", coverage.hard_negative_event_count, policy.min_hard_negative_events),
        (
            "borderline_negative_events",
            coverage.borderline_negative_event_count,
            policy.min_borderline_negative_events,
        ),
    )
    return [
        f"{name}: current={current}, required={required}, gap={required - current}"
        for name, current, required in checks
        if current < required
    ]


def _build_next_actions(
    coverage: SampleLibraryCoverage,
    policy: SampleLibraryGatePolicy,
) -> list[str]:
    actions: list[str] = []
    if coverage.dated_event_count < policy.min_dated_events:
        actions.append("补齐已有截图样本的精确 daily trade_date，优先让事件可回测。")
    if coverage.positive_event_count < policy.min_positive_events:
        actions.append("从扫描候选和人工金样本中补充 positive_high/positive_mid 事件。")
    if coverage.high_value_positive_event_count < policy.min_high_value_positive_events:
        actions.append("优先补充长期盘整突破、低回撤缩量回落后再突破等高价值正样本。")
    if coverage.negative_event_count < policy.min_negative_events:
        actions.append("补充失败召回样本，区分入口错误、趋势质量差和后续退出失败。")
    if coverage.hard_negative_event_count < policy.min_hard_negative_events:
        actions.append("补充形态族外或趋势质量明确失败的 hard_negative 样本。")
    if coverage.borderline_negative_event_count < policy.min_borderline_negative_events:
        actions.append("补充 borderline_negative 样本，用于优化风控、确认和退出规则。")
    if not actions:
        actions.append("样本覆盖通过，可以进入阈值稳定性回测和验证集拆分。")
    return actions
