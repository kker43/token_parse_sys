"""Tests for shared product contracts and factual data-asset export."""

from __future__ import annotations

import json
import unittest

from data_foundation.catalog_export import TokenFetchDataAssetExporter
from data_foundation.token_fetch_bridge import RegistryReader, TokenFetchProductCatalog
from shared.contracts import PublishedProductRef


SAMPLE_PRODUCT_REGISTRY = {
    "schema_version": 1,
    "products": [
        {
            "name": "pub_stock_daily_kline",
            "product_type": "kline",
            "market": "CN_A",
            "asset_type": "stock",
            "level": "daily",
            "grain": "asset_trade_date",
            "primary_key": ["asset_id", "trade_date"],
            "source_tables": ["token_daily_details"],
            "data_version": "v1",
            "required_fields": [
                "asset_id",
                "market",
                "asset_type",
                "trade_date",
                "close",
                "source_end_date",
                "published_at",
                "data_version",
                "quality_status",
            ],
            "consumer_contract": {
                "check_quality_status_before_query": True,
            },
        },
        {
            "name": "pub_stock_daily_indicator",
            "product_type": "indicator_long_table",
            "market": "CN_A",
            "asset_type": "stock",
            "level": "daily",
            "grain": "asset_indicator_trade_date",
            "primary_key": [
                "asset_id",
                "trade_date",
                "indicator_name",
                "indicator_version",
                "params_hash",
            ],
            "source_tables": [
                "close_price_daily_statistic",
                "amount_daily_statistic",
            ],
            "data_version": "v1",
            "required_fields": [
                "asset_id",
                "market",
                "asset_type",
                "trade_date",
                "indicator_name",
                "indicator_version",
                "params_hash",
                "indicator_value",
                "source_table",
                "source_column",
                "source_start_date",
                "source_end_date",
                "calculation_date",
                "available_time",
                "published_at",
                "data_version",
                "quality_status",
            ],
            "consumer_contract": {
                "check_quality_status_before_query": True,
                "select_indicator_by_name_version_hash": True,
            },
        },
    ],
}


FIELD_TYPES_BY_PRODUCT = {
    "pub_stock_daily_kline": {
        "asset_id": "string",
        "market": "string",
        "asset_type": "string",
        "trade_date": "date_yyyymmdd",
        "close": "numeric",
        "source_end_date": "date_yyyymmdd",
        "published_at": "timestamp",
        "data_version": "string",
        "quality_status": "string",
    },
    "pub_stock_daily_indicator": {
        "asset_id": "string",
        "trade_date": "date_yyyymmdd",
        "indicator_name": "string",
        "indicator_version": "string",
        "params_hash": "string",
        "indicator_value": "numeric",
        "source_table": "string",
        "source_column": "string",
        "source_start_date": "date_yyyymmdd",
        "source_end_date": "date_yyyymmdd",
        "calculation_date": "date_yyyymmdd",
        "available_time": "timestamp",
        "published_at": "timestamp",
        "data_version": "string",
        "quality_status": "string",
    },
}


class DataProductContractTest(unittest.TestCase):
    def test_builds_contracts_from_registry_snapshot(self) -> None:
        reader = RegistryReader()
        snapshot = reader.from_mapping(
            registry_name="data_product_registry",
            payload=SAMPLE_PRODUCT_REGISTRY,
            source_commit="b598b34",
            source_path="/home/ubuntu/token_fetch/config/data_product_registry.yaml",
        )

        catalog = TokenFetchProductCatalog()
        contracts = catalog.build_product_contracts(
            snapshot,
            field_types_by_product=FIELD_TYPES_BY_PRODUCT,
        )

        self.assertEqual(2, len(contracts))
        self.assertEqual("pub_stock_daily_kline", contracts[0].name)
        self.assertEqual("date_yyyymmdd", contracts[0].field_schema()["trade_date"])
        self.assertEqual(
            ("asset_id", "trade_date"),
            contracts[0].primary_key,
        )

    def test_exports_json_catalog_for_l0(self) -> None:
        reader = RegistryReader()
        snapshot = reader.from_mapping(
            registry_name="data_product_registry",
            payload=SAMPLE_PRODUCT_REGISTRY,
            source_commit="b598b34",
            source_path="/home/ubuntu/token_fetch/config/data_product_registry.yaml",
        )
        contracts = TokenFetchProductCatalog().build_product_contracts(
            snapshot,
            field_types_by_product=FIELD_TYPES_BY_PRODUCT,
        )

        exporter = TokenFetchDataAssetExporter()
        payload = exporter.export_catalog(
            contracts,
            source_ref=PublishedProductRef(
                producer="token_fetch",
                product_name="data_product_registry",
                source_path="/home/ubuntu/token_fetch/config/data_product_registry.yaml",
                source_commit="b598b34",
                registry_version="1",
            ),
        )

        self.assertEqual("token_fetch", payload["producer"])
        self.assertEqual(2, len(payload["products"]))
        first_product = payload["products"][0]
        self.assertEqual("token_fetch.pub_stock_daily_kline", first_product["data_asset_id"])
        self.assertEqual("pub_data_quality_status", first_product["quality_gate"]["status_product"])

        rendered = exporter.render_catalog_json(
            contracts,
            source_ref=PublishedProductRef(
                producer="token_fetch",
                product_name="data_product_registry",
                source_path="/home/ubuntu/token_fetch/config/data_product_registry.yaml",
                source_commit="b598b34",
                registry_version="1",
            ),
        )
        parsed = json.loads(rendered)
        self.assertEqual(payload, parsed)
