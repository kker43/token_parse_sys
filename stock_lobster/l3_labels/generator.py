"""Label generation boundary."""

from __future__ import annotations

from stock_lobster.l1_analysis_snapshot.schema import AnalysisSnapshot
from stock_lobster.l3_labels.registry import LabelDefinition
from stock_lobster.l3_labels.snapshot import LabelSnapshot


def build_label_snapshot(
    definition: LabelDefinition,
    analysis_snapshot: AnalysisSnapshot,
    values: dict[str, bool | float],
) -> LabelSnapshot:
    """Build a label snapshot from deterministic primitive outputs."""

    return LabelSnapshot(
        label_id=definition.label_id,
        label_version=definition.version,
        stock_code=analysis_snapshot.stock_code,
        snapshot_date=analysis_snapshot.snapshot_date,
        run_id=analysis_snapshot.run_id,
        values=values,
    )
