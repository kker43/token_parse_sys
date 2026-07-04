"""Contracts for published product quality and readiness state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class DataQualityStatus:
    """Readiness state for one published data product on one data date."""

    data_product: str
    data_date: str
    market: str
    asset_type: str
    status: str
    quality_level: str
    record_count: int
    expected_min_records: int
    source_tables: tuple[str, ...] = field(default_factory=tuple)
    source_end_date: str | None = None
    published_at: str | None = None
    data_version: str | None = None
    error_message: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "DataQualityStatus":
        """Build one quality-status object from a registry or query row mapping."""

        return cls(
            data_product=str(payload["data_product"]),
            data_date=str(payload["data_date"]),
            market=str(payload.get("market", "CN_A")),
            asset_type=str(payload.get("asset_type", "stock")),
            status=str(payload["status"]),
            quality_level=str(payload["quality_level"]),
            record_count=int(payload.get("record_count", 0)),
            expected_min_records=int(payload.get("expected_min_records", 0)),
            source_tables=tuple(str(value) for value in payload.get("source_tables", ())),
            source_end_date=(
                str(payload["source_end_date"]) if payload.get("source_end_date") is not None else None
            ),
            published_at=(
                str(payload["published_at"]) if payload.get("published_at") is not None else None
            ),
            data_version=(
                str(payload["data_version"]) if payload.get("data_version") is not None else None
            ),
            error_message=(
                str(payload["error_message"]) if payload.get("error_message") is not None else None
            ),
        )

    def is_consumable(self, allowed_statuses: tuple[str, ...], allowed_quality_levels: tuple[str, ...]) -> bool:
        """Return whether the product is safe for downstream consumption."""

        return self.status in allowed_statuses and self.quality_level in allowed_quality_levels
