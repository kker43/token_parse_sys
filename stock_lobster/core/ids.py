"""Identifier helpers."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class RunId:
    """Opaque run identifier used for reproducibility."""

    value: str

    def __str__(self) -> str:
        return self.value


def new_run_id(prefix: str = "run") -> RunId:
    """Create a new run identifier with a readable prefix."""

    return RunId(f"{prefix}_{uuid4().hex}")
