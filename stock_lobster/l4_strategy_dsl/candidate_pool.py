"""Candidate pool policy schemas."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CandidatePoolPolicy:
    """Versioned policy that defines how a candidate stock pool is produced."""

    policy_id: str
    version: str
    source_type: str
    parameters: dict[str, object]
