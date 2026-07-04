"""Application helpers for data-foundation interfaces and workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from data_foundation.catalog_export.data_asset_exporter import TokenFetchDataAssetExporter
from data_foundation.quality.readiness import (
    DataProductReadinessChecker,
    DataProductReadinessInputs,
    DataProductReadinessResult,
)
from data_foundation.token_fetch_bridge.registry_reader import (
    RegistryReader,
    RegistrySnapshot,
    TokenFetchProductCatalog,
    TokenFetchQualityReader,
)
from shared.contracts import DataProductContract, DataQualityStatus, PublishedProductRef


@dataclass(frozen=True, slots=True)
class ProductRegistryBundle:
    """Normalized published-product contracts with upstream provenance."""

    snapshot: RegistrySnapshot
    contracts: tuple[DataProductContract, ...]

    def contract_by_name(self) -> dict[str, DataProductContract]:
        """Index contracts by product name."""

        return {contract.name: contract for contract in self.contracts}

    def source_ref(self, producer_name: str) -> PublishedProductRef:
        """Build a source reference for exported downstream configs."""

        return PublishedProductRef(
            producer=producer_name,
            product_name=self.snapshot.registry_name,
            source_path=self.snapshot.source_path,
            source_commit=self.snapshot.source_commit,
            registry_version=self.snapshot.registry_version,
        )


def _read_json_payload(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_field_types_by_product(path: str | Path | None) -> dict[str, dict[str, str]]:
    """Load optional field-type metadata for published products."""

    if path is None:
        return {}

    payload = _read_json_payload(path)
    if not isinstance(payload, Mapping):
        raise ValueError("Field types payload must be a JSON object")

    result: dict[str, dict[str, str]] = {}
    for product_name, fields in payload.items():
        if not isinstance(fields, Mapping):
            raise ValueError(f"Field types for {product_name} must be a JSON object")
        result[str(product_name)] = {str(field_name): str(data_type) for field_name, data_type in fields.items()}
    return result


def load_product_registry_bundle(
    registry_path: str | Path,
    source_commit: str = "unknown",
    source_path: str = "/home/ubuntu/token_fetch",
    registry_name: str = "data_product_registry",
    field_types_by_product: Mapping[str, Mapping[str, str]] | None = None,
) -> ProductRegistryBundle:
    """Load and normalize published product contracts from one registry export."""

    snapshot = RegistryReader().read_json(
        path=registry_path,
        registry_name=registry_name,
        source_commit=source_commit,
        source_path=source_path,
    )
    contracts = TokenFetchProductCatalog().build_product_contracts(
        snapshot=snapshot,
        field_types_by_product=field_types_by_product,
    )
    return ProductRegistryBundle(snapshot=snapshot, contracts=contracts)


def list_product_summaries(bundle: ProductRegistryBundle) -> list[dict[str, object]]:
    """Return JSON-friendly contract summaries for operator interfaces."""

    return [
        {
            "name": contract.name,
            "product_type": contract.product_type,
            "market": contract.market,
            "asset_type": contract.asset_type,
            "grain": contract.grain,
            "data_version": contract.data_version,
            "update_frequency": contract.update_frequency,
            "primary_key": list(contract.primary_key),
            "required_fields": list(contract.required_field_names()),
            "source_tables": list(contract.source_tables),
        }
        for contract in bundle.contracts
    ]


def export_data_asset_catalog(
    bundle: ProductRegistryBundle,
    output_path: str | Path,
    producer_name: str = "token_fetch",
) -> dict[str, object]:
    """Export data-asset config JSON for the current product bundle."""

    exporter = TokenFetchDataAssetExporter(producer_name=producer_name)
    payload = exporter.export_catalog(bundle.contracts, source_ref=bundle.source_ref(producer_name))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def load_quality_statuses(path: str | Path) -> tuple[DataQualityStatus, ...]:
    """Load published quality-status rows from a JSON snapshot."""

    payload = _read_json_payload(path)
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, Mapping):
        rows = payload.get("statuses", payload.get("rows", ()))
    else:
        raise ValueError("Quality status payload must be a JSON list or object")

    if not isinstance(rows, Iterable):
        raise ValueError("Quality status rows must be iterable")

    reader = TokenFetchQualityReader()
    statuses: list[DataQualityStatus] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("Each quality status row must be a JSON object")
        statuses.append(reader.parse_status_row(row))
    return tuple(statuses)


def load_observed_inputs_by_product(path: str | Path | None) -> dict[str, dict[str, object]]:
    """Load optional observed evidence keyed by product name."""

    if path is None:
        return {}

    payload = _read_json_payload(path)
    if not isinstance(payload, Mapping):
        raise ValueError("Observed inputs payload must be a JSON object")

    observed_payload = payload.get("products", payload)
    if not isinstance(observed_payload, Mapping):
        raise ValueError("Observed inputs products must be a JSON object")

    result: dict[str, dict[str, object]] = {}
    for product_name, value in observed_payload.items():
        if not isinstance(value, Mapping):
            raise ValueError(f"Observed inputs for {product_name} must be a JSON object")
        result[str(product_name)] = dict(value)
    return result


def _build_readiness_inputs(
    requested_date: str,
    payload: Mapping[str, object] | None,
) -> DataProductReadinessInputs:
    payload = payload or {}
    return DataProductReadinessInputs(
        requested_date=requested_date,
        observed_dates=frozenset(str(value) for value in payload.get("observed_dates", ())),
        observed_non_null_fields=frozenset(
            str(value) for value in payload.get("observed_non_null_fields", ())
        ),
        observed_data_version=(
            str(payload["observed_data_version"])
            if payload.get("observed_data_version") is not None
            else None
        ),
        observed_record_count=(
            int(payload["observed_record_count"])
            if payload.get("observed_record_count") is not None
            else None
        ),
    )


def check_product_readiness(
    bundle: ProductRegistryBundle,
    quality_statuses: Iterable[DataQualityStatus],
    requested_date: str,
    observed_inputs_by_product: Mapping[str, Mapping[str, object]] | None = None,
    selected_products: Iterable[str] | None = None,
) -> tuple[DataProductReadinessResult, ...]:
    """Check readiness for one date across all or selected products."""

    selected = {str(name) for name in selected_products or ()}
    if selected:
        unknown_products = sorted(selected.difference(bundle.contract_by_name()))
        if unknown_products:
            raise KeyError(f"Unknown products requested: {', '.join(unknown_products)}")

    quality_index = {
        (status.data_product, status.data_date): status
        for status in quality_statuses
    }
    checker = DataProductReadinessChecker()
    results: list[DataProductReadinessResult] = []

    for contract in bundle.contracts:
        if selected and contract.name not in selected:
            continue

        inputs = _build_readiness_inputs(
            requested_date=requested_date,
            payload=(observed_inputs_by_product or {}).get(contract.name),
        )
        quality_status = quality_index.get((contract.name, requested_date))
        results.append(checker.check(contract=contract, quality_status=quality_status, inputs=inputs))

    return tuple(results)


def readiness_report(
    bundle: ProductRegistryBundle,
    results: Iterable[DataProductReadinessResult],
) -> dict[str, object]:
    """Build a stable JSON-friendly readiness report."""

    rendered_results = []
    ready_count = 0
    for result in results:
        if result.ready:
            ready_count += 1

        rendered_results.append(
            {
                "data_product": result.data_product,
                "requested_date": result.requested_date,
                "ready": result.ready,
                "reasons": list(result.reasons),
                "quality_status": (
                    {
                        "data_product": result.quality_status.data_product,
                        "data_date": result.quality_status.data_date,
                        "status": result.quality_status.status,
                        "quality_level": result.quality_status.quality_level,
                        "record_count": result.quality_status.record_count,
                        "expected_min_records": result.quality_status.expected_min_records,
                        "data_version": result.quality_status.data_version,
                    }
                    if result.quality_status is not None
                    else None
                ),
            }
        )

    return {
        "registry_name": bundle.snapshot.registry_name,
        "registry_version": bundle.snapshot.registry_version,
        "source_commit": bundle.snapshot.source_commit,
        "source_path": bundle.snapshot.source_path,
        "product_count": len(bundle.contracts),
        "ready_product_count": ready_count,
        "overall_ready": ready_count == len(rendered_results),
        "results": rendered_results,
    }
