"""Adapter boundary for the external token_fetch MySQL producer."""

from __future__ import annotations

from dataclasses import dataclass

from stock_lobster.l0_data_access.contracts import DataAsset


@dataclass(frozen=True, slots=True)
class TokenFetchMysqlAdapter:
    """Read-only adapter descriptor for token_fetch MySQL data assets."""

    connection_name: str

    def describe_asset(self, asset: DataAsset) -> DataAsset:
        """Return the supplied contract without touching factual data."""

        return asset
