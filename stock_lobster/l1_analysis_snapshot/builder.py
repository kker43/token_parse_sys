"""Analysis snapshot builder interfaces."""

from __future__ import annotations

from typing import Mapping, Protocol

from stock_lobster.l1_analysis_snapshot.schema import AnalysisSnapshot


class AnalysisSnapshotBuilder(Protocol):
    """Build reproducible analysis snapshots from L0 outputs."""

    def build(self, values: Mapping[str, object]) -> AnalysisSnapshot:
        """Build one analysis snapshot."""
