"""Build file-driven L1 snapshot input from L0 row readers."""

from __future__ import annotations

from datetime import date, datetime
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping

from stock_lobster.l0_data_access.catalog import DataAssetCatalog
from stock_lobster.l0_data_access.contracts import DataAsset
from stock_lobster.l0_data_access.repositories import DataAssetRowReader


def _json_safe_value(value: object) -> object:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _json_safe_row(row: Mapping[str, object]) -> dict[str, object]:
    return {str(key): _json_safe_value(value) for key, value in row.items()}


@dataclass(frozen=True, slots=True)
class SnapshotSourceRequest:
    """Request one L0 asset for each target stock/date snapshot."""

    asset_id: str
    fields: tuple[str, ...] | None = None
    extra_filters: Mapping[str, object] = field(default_factory=dict)
    date_field: str | None = None
    query_version: str = "l0_mysql_v1"
    limit: int | None = None


class SnapshotInputBuilder:
    """Build `daily_snapshot_production` input from a row reader."""

    def __init__(self, catalog: DataAssetCatalog, row_reader: DataAssetRowReader) -> None:
        self.catalog = catalog
        self.row_reader = row_reader

    def build_input(
        self,
        stock_codes: tuple[str, ...],
        snapshot_date: str,
        source_requests: tuple[SnapshotSourceRequest, ...],
        analysis_version: str = "analysis_v1",
    ) -> dict[str, object]:
        """Build a JSON-friendly snapshot input payload."""

        snapshots: list[dict[str, object]] = []
        for stock_code in stock_codes:
            sources: list[dict[str, object]] = []
            for request in source_requests:
                asset = self.catalog.get(request.asset_id)
                date_field = request.date_field or self._infer_date_field(asset)
                filters = {
                    "asset_id": stock_code,
                    date_field: snapshot_date,
                    **dict(request.extra_filters),
                }
                rows = self.row_reader.fetch_rows(
                    asset=asset,
                    filters=filters,
                    fields=request.fields,
                    limit=request.limit,
                )
                sources.append(
                    {
                        "asset_id": request.asset_id,
                        "query_version": request.query_version,
                        "query_params": {str(key): str(value) for key, value in filters.items()},
                        "rows": [_json_safe_row(row) for row in rows],
                    }
                )
            snapshots.append({"stock_code": stock_code, "snapshot_date": snapshot_date, "sources": sources})

        return {
            "schema_version": 1,
            "analysis_version": analysis_version,
            "snapshot_date": snapshot_date,
            "snapshots": snapshots,
        }

    def _infer_date_field(self, asset: DataAsset) -> str:
        for field_name in ("trade_date", "snapshot_date", "period_end_date", "data_date"):
            if field_name in asset.field_schema:
                return field_name
        raise ValueError(f"{asset.asset_id} does not expose a supported date field")
