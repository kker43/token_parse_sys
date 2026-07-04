"""Audit metadata for reproducible project artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping


@dataclass(frozen=True, slots=True)
class AuditStamp:
    """Minimal audit metadata shared by versioned artifacts."""

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "system"
    notes: Mapping[str, str] = field(default_factory=dict)
