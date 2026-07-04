"""Label registry models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class LabelDefinition:
    """Versioned label definition derived from primitives."""

    label_id: str
    version: str
    primitive_ids: tuple[str, ...]
    description: str


@dataclass(slots=True)
class LabelRegistry:
    """In-memory label registry for the MVP."""

    labels: dict[str, LabelDefinition] = field(default_factory=dict)

    def register(self, label: LabelDefinition) -> None:
        self.labels[label.label_id] = label

    def get(self, label_id: str) -> LabelDefinition:
        return self.labels[label_id]
