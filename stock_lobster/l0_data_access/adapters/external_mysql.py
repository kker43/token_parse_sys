"""Adapter boundary for an external MySQL factual-data producer."""

from __future__ import annotations

from dataclasses import dataclass

from stock_lobster.l0_data_access.contracts import DataAsset


@dataclass(frozen=True, slots=True)
class ExternalMysqlAdapter:
    """Read-only adapter descriptor for external MySQL data assets."""

    connection_name: str

    def describe_asset(self, asset: DataAsset) -> DataAsset:
        """Return the supplied contract without touching factual data."""

        return asset
