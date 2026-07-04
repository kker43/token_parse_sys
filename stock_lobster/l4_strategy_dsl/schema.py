"""White-box strategy DSL schema."""

from __future__ import annotations

from dataclasses import dataclass

from stock_lobster.l4_strategy_dsl.candidate_pool import CandidatePoolPolicy
from stock_lobster.l4_strategy_dsl.stage_pipeline import StagePipeline


@dataclass(frozen=True, slots=True)
class StrategyDSL:
    """Human-readable strategy definition over approved label fields."""

    strategy_id: str
    version: str
    name: str
    candidate_pool: CandidatePoolPolicy
    pipeline: StagePipeline
    label_fields: tuple[str, ...]
    status: str = "draft"
