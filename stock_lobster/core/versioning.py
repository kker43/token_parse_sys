"""Versioning contracts shared by Stock Lobster layers."""

from __future__ import annotations

from dataclasses import dataclass

from stock_lobster.core.audit import AuditStamp
from stock_lobster.core.ids import RunId


@dataclass(frozen=True, slots=True)
class VersionedArtifact:
    """Base metadata for durable artifacts that affect strategy behavior."""

    artifact_id: str
    version: str
    run_id: RunId
    audit: AuditStamp
