"""Factor reuse audit helpers for research workflows."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable, Mapping


@dataclass(frozen=True, slots=True)
class FactorRequirement:
    """One requested factor or indicator need."""

    name: str
    meaning: str
    timeframe: str | None = None
    window: int | None = None
    reuse_family: str | None = None


@dataclass(frozen=True, slots=True)
class FactorReuseDecision:
    """Deterministic factor reuse decision."""

    requirement_name: str
    decision: str
    matched_indicator: str | None
    reason: str
    similar_indicators: tuple[str, ...] = ()

    def to_mapping(self) -> dict[str, object]:
        """Render this decision as JSON-friendly mapping."""

        return {
            "requirement_name": self.requirement_name,
            "decision": self.decision,
            "matched_indicator": self.matched_indicator,
            "reason": self.reason,
            "similar_indicators": list(self.similar_indicators),
        }


def load_indicator_catalog(path: str | Path) -> tuple[dict[str, object], ...]:
    """Load indicator definitions from the project indicator registry."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    indicators = payload.get("indicators", ())
    if not isinstance(indicators, list):
        raise ValueError("indicator registry must contain an indicators list")
    return tuple(dict(item) for item in indicators if isinstance(item, Mapping))


def audit_factor_reuse(
    requirements: Iterable[FactorRequirement],
    indicators: Iterable[Mapping[str, object]],
) -> tuple[FactorReuseDecision, ...]:
    """Audit whether requested factors can reuse existing indicator definitions."""

    indicator_list = tuple(dict(item) for item in indicators)
    by_name = {str(item["name"]): item for item in indicator_list if "name" in item}
    decisions: list[FactorReuseDecision] = []
    for requirement in requirements:
        if requirement.name in by_name:
            decisions.append(
                FactorReuseDecision(
                    requirement_name=requirement.name,
                    decision="reuse_existing",
                    matched_indicator=requirement.name,
                    reason="已有完全匹配因子，必须复用。",
                )
            )
            continue

        same_family = _same_family_indicators(requirement, indicator_list)
        if same_family:
            decisions.append(
                FactorReuseDecision(
                    requirement_name=requirement.name,
                    decision="reuse_with_window_param",
                    matched_indicator=same_family[0],
                    reason="存在同类口径族，优先通过周期或窗口参数扩展复用。",
                    similar_indicators=tuple(same_family),
                )
            )
            continue

        similar = _similar_by_tokens(requirement, indicator_list)
        if similar:
            decisions.append(
                FactorReuseDecision(
                    requirement_name=requirement.name,
                    decision="research_temporary",
                    matched_indicator=similar[0],
                    reason="存在近似因子，研究阶段可临时参考，但生产前需要确认差异。",
                    similar_indicators=tuple(similar),
                )
            )
            continue

        decisions.append(
            FactorReuseDecision(
                requirement_name=requirement.name,
                decision="new_factor_required",
                matched_indicator=None,
                reason="未找到完全匹配、同类参数化或近似替代因子。",
            )
        )
    return tuple(decisions)


def _same_family_indicators(
    requirement: FactorRequirement,
    indicators: tuple[dict[str, object], ...],
) -> list[str]:
    if requirement.reuse_family is None:
        return []
    matches: list[str] = []
    for item in indicators:
        if item.get("reuse_family") == requirement.reuse_family:
            matches.append(str(item["name"]))
            continue
        if requirement.reuse_family == "rolling_max_drawdown(close, window)" and "drawdown" in str(item.get("name", "")):
            matches.append(str(item["name"]))
    return matches


def _similar_by_tokens(
    requirement: FactorRequirement,
    indicators: tuple[dict[str, object], ...],
) -> list[str]:
    requirement_tokens = set(requirement.name.split("_"))
    matches: list[str] = []
    for item in indicators:
        name = str(item.get("name", ""))
        tokens = set(name.split("_"))
        if len(requirement_tokens.intersection(tokens)) >= 2:
            matches.append(name)
    return matches
