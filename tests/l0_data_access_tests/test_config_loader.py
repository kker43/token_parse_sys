"""Tests for loading exported data-asset catalogs into L0 contracts."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stock_lobster.l0_data_access import DataAssetCatalogLoader


def sample_catalog_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "producer": "token_fetch",
        "source_ref": {
            "producer": "token_fetch",
            "product_name": "data_product_registry",
            "source_path": "/home/ubuntu/token_fetch/config/data_product_registry.yaml",
            "source_commit": "b598b34",
            "registry_version": "1",
        },
        "products": [
            {
                "data_asset_id": "token_fetch.pub_stock_daily_kline",
                "data_product": "pub_stock_daily_kline",
                "source_type": "published_product",
                "source_name": "token_fetch",
                "market": "CN_A",
                "asset_type": "stock",
                "grain": "asset_trade_date",
                "field_schema": {
                    "asset_id": "string",
                    "trade_date": "date_yyyymmdd",
                    "close": "numeric",
                },
                "required_fields": ["asset_id", "trade_date", "close"],
                "primary_key": ["asset_id", "trade_date"],
                "source_tables": ["token_daily_details"],
                "update_frequency": "daily",
                "data_version": "v1",
                "quality_gate": {
                    "status_product": "pub_data_quality_status",
                    "allowed_statuses": ["ready"],
                    "allowed_quality_levels": ["pass", "warning"],
                },
                "consumer_contract": {
                    "check_quality_status_before_query": True,
                },
            }
        ],
    }


class DataAssetCatalogLoaderTest(unittest.TestCase):
    def test_loads_catalog_json_into_l0_assets(self) -> None:
        with TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "catalog.json"
            path.write_text(json.dumps(sample_catalog_payload()), encoding="utf-8")

            snapshot = DataAssetCatalogLoader().load_json(path)

        asset = snapshot.catalog.get("token_fetch.pub_stock_daily_kline")
        self.assertEqual("token_fetch", snapshot.producer)
        self.assertEqual("pub_stock_daily_kline", asset.data_product)
        self.assertEqual(("ready",), asset.allowed_statuses)
        self.assertEqual(("pass", "warning"), asset.allowed_quality_levels)
        self.assertEqual(("asset_id", "trade_date"), asset.primary_key)
