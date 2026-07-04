"""Analysis snapshot builders for deterministic L1 production."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

from stock_lobster.core.ids import RunId, new_run_id
from stock_lobster.l0_data_access.catalog import DataAssetCatalog
from stock_lobster.l0_data_access.contracts import DataAsset
from stock_lobster.l1_analysis_snapshot.schema import AnalysisSnapshot
from stock_lobster.l1_analysis_snapshot.schema import AnalysisSnapshotDependency

IDENTITY_FIELDS = frozenset(
    {
        "asset_id",
        "asset_type",
        "data_version",
        "market",
        "period_end_date",
        "published_at",
        "quality_status",
        "source",
        "source_end_date",
        "snapshot_date",
        "trade_date",
    }
)


class AnalysisSnapshotBuilder(Protocol):
    """Build reproducible analysis snapshots from L0 outputs."""

    def build(self, values: Mapping[str, object]) -> AnalysisSnapshot:
        """Build one analysis snapshot."""


@dataclass(frozen=True, slots=True)
class SourceRows:
    """Rows read through one L0 data asset for one snapshot target."""

    asset_id: str
    rows: tuple[Mapping[str, object], ...]
    query_version: str = "manual_v1"
    query_params: Mapping[str, str] = field(default_factory=dict)


class DeterministicAnalysisSnapshotBuilder:
    """Build L1 snapshots from already-fetched L0 rows."""

    def __init__(
        self,
        catalog: DataAssetCatalog,
        analysis_version: str = "analysis_v1",
        feature_prefix_by_asset_id: Mapping[str, str] | None = None,
    ) -> None:
        self.catalog = catalog
        self.analysis_version = analysis_version
        self.feature_prefix_by_asset_id = dict(feature_prefix_by_asset_id or {})

    def build_from_sources(
        self,
        stock_code: str,
        snapshot_date: str,
        sources: tuple[SourceRows, ...],
        run_id: RunId | None = None,
    ) -> AnalysisSnapshot:
        """Build one reproducible snapshot from validated source rows."""

        features: dict[str, object] = {}
        dependencies: list[AnalysisSnapshotDependency] = []

        for source in sources:
            asset = self.catalog.get(source.asset_id)
            self._validate_source_rows(asset=asset, stock_code=stock_code, snapshot_date=snapshot_date, rows=source.rows)
            prefix = self._feature_prefix(asset)
            features.update(self._features_from_rows(prefix=prefix, rows=source.rows))
            dependencies.append(
                AnalysisSnapshotDependency(
                    asset_id=source.asset_id,
                    query_version=source.query_version,
                    query_params={
                        "stock_code": stock_code,
                        "snapshot_date": snapshot_date,
                        **dict(source.query_params),
                    },
                )
            )

        return AnalysisSnapshot(
            stock_code=stock_code,
            snapshot_date=snapshot_date,
            analysis_version=self.analysis_version,
            run_id=run_id or new_run_id(prefix="snapshot"),
            features=features,
            dependencies=tuple(dependencies),
        )

    def _feature_prefix(self, asset: DataAsset) -> str:
        if asset.asset_id in self.feature_prefix_by_asset_id:
            return self.feature_prefix_by_asset_id[asset.asset_id]
        return asset.data_product or asset.asset_id

    def _features_from_rows(self, prefix: str, rows: tuple[Mapping[str, object], ...]) -> dict[str, object]:
        features: dict[str, object] = {}
        for index, row in enumerate(rows):
            row_suffix = "" if len(rows) == 1 else f".{index + 1}"
            for field_name, value in row.items():
                if field_name in IDENTITY_FIELDS:
                    continue
                features[f"{prefix}{row_suffix}.{field_name}"] = value
        return features

    def _validate_source_rows(
        self,
        asset: DataAsset,
        stock_code: str,
        snapshot_date: str,
        rows: tuple[Mapping[str, object], ...],
    ) -> None:
        if not rows:
            raise ValueError(f"source rows are empty for {asset.asset_id}")
        for row in rows:
            missing = [field_name for field_name in asset.required_fields if field_name not in row]
            if missing:
                raise ValueError(f"{asset.asset_id} missing required fields: {', '.join(missing)}")
            if str(row.get("asset_id", stock_code)) != stock_code:
                raise ValueError(f"{asset.asset_id} row asset_id does not match snapshot stock_code")
            for date_field in ("trade_date", "snapshot_date"):
                if date_field in row and str(row[date_field]) != snapshot_date:
                    raise ValueError(f"{asset.asset_id} row {date_field} does not match snapshot_date")
