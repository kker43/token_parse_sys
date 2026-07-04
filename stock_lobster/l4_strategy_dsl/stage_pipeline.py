"""Stage pipeline schema."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class StageDefinition:
    """One white-box execution stage in a strategy."""

    stage_id: str
    stage_name: str
    stage_type: str
    pass_conditions: tuple[str, ...] = field(default_factory=tuple)
    reject_conditions: tuple[str, ...] = field(default_factory=tuple)
    score_fields: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class StagePipeline:
    """Ordered stages for candidate filtering and ranking."""

    stages: tuple[StageDefinition, ...]
