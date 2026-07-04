"""Catalog of approved external data assets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from stock_lobster.l0_data_access.contracts import DataAsset


@dataclass(slots=True)
class DataAssetCatalog:
    """In-memory catalog used until persistent registry storage is chosen."""

    assets: dict[str, DataAsset] = field(default_factory=dict)

    def register(self, asset: DataAsset) -> None:
        self.assets[asset.asset_id] = asset

    def get(self, asset_id: str) -> DataAsset:
        return self.assets[asset_id]

    def list_assets(self) -> Iterable[DataAsset]:
        return tuple(self.assets.values())
