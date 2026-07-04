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

    def to_mapping(self) -> dict[str, object]:
        """Render this dependency as a stable JSON-friendly mapping."""

        return {
            "asset_id": self.asset_id,
            "query_version": self.query_version,
            "query_params": dict(self.query_params),
        }


@dataclass(frozen=True, slots=True)
class AnalysisSnapshot:
    """Stable analytical view for one stock on one date."""

    stock_code: str
    snapshot_date: str
    analysis_version: str
    run_id: RunId
    features: Mapping[str, object]
    dependencies: tuple[AnalysisSnapshotDependency, ...] = field(default_factory=tuple)

    def to_mapping(self) -> dict[str, object]:
        """Render this snapshot as a stable JSON-friendly mapping."""

        return {
            "stock_code": self.stock_code,
            "snapshot_date": self.snapshot_date,
            "analysis_version": self.analysis_version,
            "run_id": str(self.run_id),
            "features": dict(self.features),
            "dependencies": [dependency.to_mapping() for dependency in self.dependencies],
        }
