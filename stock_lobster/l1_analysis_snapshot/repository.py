"""Repositories for analysis snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field

from stock_lobster.l1_analysis_snapshot.schema import AnalysisSnapshot


@dataclass(slots=True)
class InMemoryAnalysisSnapshotRepository:
    """Simple repository for early tests."""

    snapshots: dict[tuple[str, str, str], AnalysisSnapshot] = field(default_factory=dict)

    def save(self, snapshot: AnalysisSnapshot) -> None:
        key = (snapshot.stock_code, snapshot.snapshot_date, snapshot.analysis_version)
        self.snapshots[key] = snapshot

    def get(
        self,
        stock_code: str,
        snapshot_date: str,
        analysis_version: str,
    ) -> AnalysisSnapshot:
        return self.snapshots[(stock_code, snapshot_date, analysis_version)]
