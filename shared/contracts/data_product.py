"""Contracts for published factual data products and indicator definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class DataProductField:
    """One field exposed by a published data product."""

    name: str
    data_type: str = "unknown"
    nullable: bool = False
    description: str = ""


@dataclass(frozen=True, slots=True)
class PublishedProductRef:
    """Reference to the upstream producer snapshot behind a product contract."""

    producer: str
    product_name: str
    source_path: str
    source_commit: str
    registry_version: str = "unknown"


@dataclass(frozen=True, slots=True)
class IndicatorContract:
    """Published basic-indicator definition owned by the factual producer."""

    name: str
    version: str
    params_hash: str
    source_table: str
    source_column: str
    value_type: str
    enabled: bool = True
    description: str = ""


@dataclass(frozen=True, slots=True)
class DataProductContract:
    """Stable downstream contract for one published factual product."""

    name: str
    product_type: str
    market: str
    asset_type: str
    grain: str
    data_version: str
    update_frequency: str
    required_fields: tuple[DataProductField, ...]
    primary_key: tuple[str, ...]
    source_tables: tuple[str, ...]
    quality_status_product: str = "pub_data_quality_status"
    allowed_statuses: tuple[str, ...] = ("ready",)
    allowed_quality_levels: tuple[str, ...] = ("pass", "warning")
    consumer_contract: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def from_registry_item(
        cls,
        item: Mapping[str, object],
        field_types: Mapping[str, str] | None = None,
    ) -> "DataProductContract":
        """Build a contract from a registry item exported by token_fetch."""

        required_field_names = tuple(str(name) for name in item.get("required_fields", ()))
        fields = tuple(
            DataProductField(
                name=field_name,
                data_type=(field_types or {}).get(field_name, "unknown"),
                nullable=False,
            )
            for field_name in required_field_names
        )

        level = str(item.get("level", "unknown"))
        update_frequency = level if level != "unknown" else str(item.get("freshness", "unknown"))

        return cls(
            name=str(item["name"]),
            product_type=str(item.get("product_type", "unknown")),
            market=str(item.get("market", "CN_A")),
            asset_type=str(item.get("asset_type", "stock")),
            grain=str(item.get("grain", "unknown")),
            data_version=str(item.get("data_version", "v1")),
            update_frequency=update_frequency,
            required_fields=fields,
            primary_key=tuple(str(value) for value in item.get("primary_key", ())),
            source_tables=tuple(str(value) for value in item.get("source_tables", ())),
            consumer_contract=dict(item.get("consumer_contract", {})),
        )

    def field_schema(self) -> dict[str, str]:
        """Return the field schema as a JSON-friendly mapping."""

        return {field.name: field.data_type for field in self.required_fields}

    def required_field_names(self) -> tuple[str, ...]:
        """Return required field names in declaration order."""

        return tuple(field.name for field in self.required_fields)

    def required_non_nullable_fields(self) -> tuple[str, ...]:
        """Return fields that must be present and non-null to consume the product."""

        return tuple(field.name for field in self.required_fields if not field.nullable)

    def has_field(self, field_name: str) -> bool:
        """Return whether the contract exposes a field."""

        return field_name in self.required_field_names()
