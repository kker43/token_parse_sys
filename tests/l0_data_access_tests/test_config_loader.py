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
        "producer": "external_provider",
        "source_ref": {
            "producer": "external_provider",
            "product_name": "data_product_registry",
            "source_path": "/data/external_provider/config/data_product_registry.yaml",
            "source_commit": "commit-1234567",
            "registry_version": "1",
        },
        "products": [
            {
                "data_asset_id": "external_provider.pub_stock_daily_kline",
                "data_product": "pub_stock_daily_kline",
                "source_type": "published_product",
                "source_name": "external_provider",
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
                    "field_units": {
                        "amount": "thousand_cny",
                        "vol": "lot",
                    },
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

        asset = snapshot.catalog.get("external_provider.pub_stock_daily_kline")
        self.assertEqual("external_provider", snapshot.producer)
        self.assertEqual("pub_stock_daily_kline", asset.data_product)
        self.assertEqual(("ready",), asset.allowed_statuses)
        self.assertEqual(("pass", "warning"), asset.allowed_quality_levels)
        self.assertEqual(("asset_id", "trade_date"), asset.primary_key)
        self.assertEqual("thousand_cny", asset.field_units["amount"])
        asset.require_field_unit("amount", "thousand_cny")
        with self.assertRaisesRegex(ValueError, "amount unit mismatch"):
            asset.require_field_unit("amount", "cny")
