"""Repository interfaces for L0 contracts."""

from __future__ import annotations

from typing import Protocol

from stock_lobster.l0_data_access.contracts import DataAsset


class DataAssetRepository(Protocol):
    """Storage boundary for data asset contracts."""

    def save(self, asset: DataAsset) -> None:
        """Persist a data asset contract."""

    def get(self, asset_id: str) -> DataAsset:
        """Load a data asset contract."""
