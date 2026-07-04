"""Read normalized product and indicator registries from external factual-producer exports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from shared.contracts import DataProductContract, DataQualityStatus, IndicatorContract


@dataclass(frozen=True, slots=True)
class RegistrySnapshot:
    """One exported registry payload with source provenance metadata."""

    registry_name: str
    payload: Mapping[str, object]
    source_commit: str
    source_path: str
    registry_version: str = "unknown"


class RegistryReader:
    """Load JSON registry snapshots exported from an external factual producer."""

    def read_json(
        self,
        path: str | Path,
        registry_name: str,
        source_commit: str,
        source_path: str,
    ) -> RegistrySnapshot:
        """Load one exported registry snapshot from a local JSON file."""

        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Registry {path} must contain a JSON object")
        return self.from_mapping(
            registry_name=registry_name,
            payload=payload,
            source_commit=source_commit,
            source_path=source_path,
        )

    def from_mapping(
        self,
        registry_name: str,
        payload: Mapping[str, object],
        source_commit: str,
        source_path: str,
    ) -> RegistrySnapshot:
        """Wrap an in-memory registry mapping in provenance metadata."""

        registry_version = str(payload.get("schema_version", "unknown"))
        return RegistrySnapshot(
            registry_name=registry_name,
            payload=dict(payload),
            source_commit=source_commit,
            source_path=source_path,
            registry_version=registry_version,
        )


class PublishedProductCatalog:
    """Translate published registry payloads into shared product contracts."""

    def build_product_contracts(
        self,
        snapshot: RegistrySnapshot,
        field_types_by_product: Mapping[str, Mapping[str, str]] | None = None,
    ) -> tuple[DataProductContract, ...]:
        """Build product contracts from a published data product registry snapshot."""

        products = snapshot.payload.get("products", ())
        return tuple(
            DataProductContract.from_registry_item(
                item,
                field_types=(field_types_by_product or {}).get(str(item["name"]), {}),
            )
            for item in products
            if isinstance(item, Mapping)
        )

    def build_indicator_contracts(self, snapshot: RegistrySnapshot) -> tuple[IndicatorContract, ...]:
        """Build indicator contracts from a published indicator registry snapshot."""

        indicators = snapshot.payload.get("indicators", ())
        return tuple(
            IndicatorContract(
                name=str(item["name"]),
                version=str(item.get("version", "legacy_v1")),
                params_hash=str(item.get("params_hash", "default")),
                source_table=str(item["source_table"]),
                source_column=str(item["source_column"]),
                value_type=str(item.get("value_type", "unknown")),
                enabled=bool(item.get("enabled", True)),
                description=str(item.get("description", "")),
            )
            for item in indicators
            if isinstance(item, Mapping)
        )


class PublishedQualityReader:
    """Normalize query rows for the published product quality-status product."""

    def parse_status_row(self, payload: Mapping[str, Any]) -> DataQualityStatus:
        """Parse one readiness row returned by `pub_data_quality_status`."""

        return DataQualityStatus.from_mapping(payload)
