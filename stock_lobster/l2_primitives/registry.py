"""Primitive registry models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from stock_lobster.l1_analysis_snapshot.schema import AnalysisSnapshot

PrimitiveFunction = Callable[[AnalysisSnapshot], bool | float]


@dataclass(frozen=True, slots=True)
class PrimitiveDefinition:
    """Registered pure function definition."""

    primitive_id: str
    version: str
    function: PrimitiveFunction
    output_type: str
    description: str


@dataclass(slots=True)
class PrimitiveRegistry:
    """In-memory primitive registry for the MVP."""

    primitives: dict[str, PrimitiveDefinition] = field(default_factory=dict)

    def register(self, primitive: PrimitiveDefinition) -> None:
        self.primitives[primitive.primitive_id] = primitive

    def get(self, primitive_id: str) -> PrimitiveDefinition:
        return self.primitives[primitive_id]
