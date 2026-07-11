"""External data contract models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class DataAsset:
    """A registered external data asset contract, not a factual data copy."""

    asset_id: str
    source_type: str
    source_name: str
    field_schema: Mapping[str, str]
    update_frequency: str
    quality_status: str
    data_product: str | None = None
    market: str = "CN_A"
    asset_type: str = "stock"
    grain: str | None = None
    required_fields: tuple[str, ...] = field(default_factory=tuple)
    primary_key: tuple[str, ...] = field(default_factory=tuple)
    source_tables: tuple[str, ...] = field(default_factory=tuple)
    data_version: str | None = None
    allowed_statuses: tuple[str, ...] = field(default_factory=tuple)
    allowed_quality_levels: tuple[str, ...] = field(default_factory=tuple)
    consumer_contract: Mapping[str, object] = field(default_factory=dict)
    field_units: Mapping[str, str] = field(default_factory=dict)
    owner_layer: str = "L0"
    table_name: str | None = None
    storage_path: str | None = None
    first_available_date: str | None = None
    latest_available_date: str | None = None

    def require_field_unit(self, field_name: str, expected_unit: str) -> None:
        """Require one external field to use the unit expected by the consumer."""

        actual = self.field_units.get(field_name)
        if actual != expected_unit:
            raise ValueError(
                f"{self.asset_id}.{field_name} unit mismatch: expected {expected_unit}, got {actual}"
            )


@dataclass(frozen=True, slots=True)
class ExternalDataContract:
    """A named collection of external assets exposed by a producer."""

    contract_id: str
    producer: str
    assets: tuple[DataAsset, ...] = field(default_factory=tuple)
