"""Initial primitive function examples over AnalysisSnapshot."""

from __future__ import annotations

from stock_lobster.l1_analysis_snapshot.schema import AnalysisSnapshot


def has_feature(snapshot: AnalysisSnapshot, feature_name: str) -> bool:
    """Return whether a snapshot contains a named analytical feature."""

    return feature_name in snapshot.features
