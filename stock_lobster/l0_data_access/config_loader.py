"""Load L0 data-asset contracts from exported catalog JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from stock_lobster.l0_data_access.catalog import DataAssetCatalog
from stock_lobster.l0_data_access.contracts import DataAsset


@dataclass(frozen=True, slots=True)
class DataAssetCatalogSnapshot:
    """Loaded L0 data-asset catalog plus upstream export provenance."""

    producer: str
    schema_version: int
    catalog: DataAssetCatalog
    source_ref: Mapping[str, str] | None = None


class DataAssetCatalogLoader:
    """Read exported data-asset config JSON into L0 contract objects."""

    def load_json(self, path: str | Path) -> DataAssetCatalogSnapshot:
        """Load one exported catalog JSON file."""

        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Catalog {path} must contain a JSON object")
        return self.from_mapping(payload)

    def from_mapping(self, payload: Mapping[str, object]) -> DataAssetCatalogSnapshot:
        """Load one in-memory exported catalog mapping."""

        products = payload.get("products", ())
        if not isinstance(products, list):
            raise ValueError("Catalog products must be a JSON list")

        catalog = DataAssetCatalog()
        for item in products:
            if not isinstance(item, Mapping):
                raise ValueError("Catalog product entries must be JSON objects")
            catalog.register(self._build_data_asset(item))

        source_ref = payload.get("source_ref")
        normalized_source_ref = dict(source_ref) if isinstance(source_ref, Mapping) else None

        return DataAssetCatalogSnapshot(
            producer=str(payload.get("producer", "unknown")),
            schema_version=int(payload.get("schema_version", 1)),
            catalog=catalog,
            source_ref=normalized_source_ref,
        )

    def _build_data_asset(self, item: Mapping[str, object]) -> DataAsset:
        quality_gate = item.get("quality_gate", {})
        if quality_gate and not isinstance(quality_gate, Mapping):
            raise ValueError("quality_gate must be a JSON object")

        return DataAsset(
            asset_id=str(item["data_asset_id"]),
            data_product=str(item.get("data_product")) if item.get("data_product") is not None else None,
            source_type=str(item["source_type"]),
            source_name=str(item["source_name"]),
            market=str(item.get("market", "CN_A")),
            asset_type=str(item.get("asset_type", "stock")),
            grain=str(item.get("grain")) if item.get("grain") is not None else None,
            field_schema={str(key): str(value) for key, value in dict(item.get("field_schema", {})).items()},
            required_fields=tuple(str(value) for value in item.get("required_fields", ())),
            primary_key=tuple(str(value) for value in item.get("primary_key", ())),
            source_tables=tuple(str(value) for value in item.get("source_tables", ())),
            update_frequency=str(item.get("update_frequency", "unknown")),
            data_version=str(item["data_version"]) if item.get("data_version") is not None else None,
            quality_status=str(quality_gate.get("status_product", "pub_data_quality_status")),
            allowed_statuses=tuple(str(value) for value in quality_gate.get("allowed_statuses", ())),
            allowed_quality_levels=tuple(
                str(value) for value in quality_gate.get("allowed_quality_levels", ())
            ),
            consumer_contract=dict(item.get("consumer_contract", {})),
        )
