"""Analysis snapshot schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from stock_lobster.core.ids import RunId


@dataclass(frozen=True, slots=True)
class AnalysisSnapshotDependency:
    """Trace from a snapshot field back to an external data asset."""

    asset_id: str
    query_version: str
    query_params: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AnalysisSnapshot:
    """Stable analytical view for one stock on one date."""

    stock_code: str
    snapshot_date: str
    analysis_version: str
    run_id: RunId
    features: Mapping[str, object]
    dependencies: tuple[AnalysisSnapshotDependency, ...] = field(default_factory=tuple)
