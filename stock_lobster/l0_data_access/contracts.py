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
    owner_layer: str = "L0"
    table_name: str | None = None
    storage_path: str | None = None
    first_available_date: str | None = None
    latest_available_date: str | None = None


@dataclass(frozen=True, slots=True)
class ExternalDataContract:
    """A named collection of external assets exposed by a producer."""

    contract_id: str
    producer: str
    assets: tuple[DataAsset, ...] = field(default_factory=tuple)
