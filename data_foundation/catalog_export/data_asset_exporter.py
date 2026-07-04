"""Convert published product contracts into L0 data-asset config payloads."""

from __future__ import annotations

import json
from typing import Iterable

from shared.contracts import DataProductContract, PublishedProductRef


class TokenFetchDataAssetExporter:
    """Build JSON-friendly data-asset configs from token_fetch product contracts."""

    def __init__(self, producer_name: str = "token_fetch") -> None:
        self.producer_name = producer_name

    def contract_to_data_asset(self, contract: DataProductContract) -> dict[str, object]:
        """Convert one published product contract into an L0 config item."""

        return {
            "data_asset_id": f"{self.producer_name}.{contract.name}",
            "data_product": contract.name,
            "source_type": "published_product",
            "source_name": self.producer_name,
            "market": contract.market,
            "asset_type": contract.asset_type,
            "grain": contract.grain,
            "field_schema": contract.field_schema(),
            "required_fields": list(contract.required_field_names()),
            "primary_key": list(contract.primary_key),
            "source_tables": list(contract.source_tables),
            "update_frequency": contract.update_frequency,
            "data_version": contract.data_version,
            "quality_gate": {
                "status_product": contract.quality_status_product,
                "allowed_statuses": list(contract.allowed_statuses),
                "allowed_quality_levels": list(contract.allowed_quality_levels),
            },
            "consumer_contract": dict(contract.consumer_contract),
        }

    def export_catalog(
        self,
        contracts: Iterable[DataProductContract],
        source_ref: PublishedProductRef | None = None,
    ) -> dict[str, object]:
        """Build a full JSON-serializable data-asset catalog payload."""

        catalog: dict[str, object] = {
            "schema_version": 1,
            "producer": self.producer_name,
            "products": [self.contract_to_data_asset(contract) for contract in contracts],
        }
        if source_ref is not None:
            catalog["source_ref"] = {
                "producer": source_ref.producer,
                "product_name": source_ref.product_name,
                "source_path": source_ref.source_path,
                "source_commit": source_ref.source_commit,
                "registry_version": source_ref.registry_version,
            }
        return catalog

    def render_catalog_json(
        self,
        contracts: Iterable[DataProductContract],
        source_ref: PublishedProductRef | None = None,
    ) -> str:
        """Render a stable JSON payload that can be checked into configs."""

        return json.dumps(self.export_catalog(contracts, source_ref=source_ref), indent=2, sort_keys=True)
