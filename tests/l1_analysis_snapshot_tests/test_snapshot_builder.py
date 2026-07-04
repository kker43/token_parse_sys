"""Tests for deterministic L1 analysis snapshot building."""

from __future__ import annotations

import unittest

from stock_lobster.core.ids import RunId
from stock_lobster.l0_data_access import DataAssetCatalogLoader
from stock_lobster.l1_analysis_snapshot import (
    DeterministicAnalysisSnapshotBuilder,
    SourceRows,
)


def sample_catalog_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "producer": "external_provider",
        "products": [
            {
                "data_asset_id": "external_provider.pub_stock_daily_kline",
                "data_product": "pub_stock_daily_kline",
                "source_type": "published_product",
                "source_name": "external_provider",
                "field_schema": {
                    "asset_id": "string",
                    "trade_date": "date_yyyymmdd",
                    "close": "numeric",
                    "amount": "numeric",
                    "quality_status": "string",
                },
                "required_fields": ["asset_id", "trade_date", "close", "amount", "quality_status"],
                "primary_key": ["asset_id", "trade_date"],
                "source_tables": ["token_daily_details"],
                "update_frequency": "daily",
                "data_version": "v1",
                "quality_gate": {
                    "status_product": "pub_data_quality_status",
                    "allowed_statuses": ["ready"],
                    "allowed_quality_levels": ["pass", "warning"],
                },
            }
        ],
    }


class DeterministicAnalysisSnapshotBuilderTest(unittest.TestCase):
    def test_builds_snapshot_features_and_dependencies(self) -> None:
        catalog = DataAssetCatalogLoader().from_mapping(sample_catalog_payload()).catalog
        builder = DeterministicAnalysisSnapshotBuilder(catalog=catalog, analysis_version="analysis_v1")

        snapshot = builder.build_from_sources(
            stock_code="000001.SZ",
            snapshot_date="20260704",
            run_id=RunId("run_fixture"),
            sources=(
                SourceRows(
                    asset_id="external_provider.pub_stock_daily_kline",
                    query_version="query_v1",
                    query_params={"market": "CN_A"},
                    rows=(
                        {
                            "asset_id": "000001.SZ",
                            "trade_date": "20260704",
                            "close": 12.34,
                            "amount": 1000000,
                            "quality_status": "pass",
                        },
                    ),
                ),
            ),
        )

        self.assertEqual("000001.SZ", snapshot.stock_code)
        self.assertEqual("analysis_v1", snapshot.analysis_version)
        self.assertEqual(12.34, snapshot.features["pub_stock_daily_kline.close"])
        self.assertEqual(1000000, snapshot.features["pub_stock_daily_kline.amount"])
        self.assertNotIn("pub_stock_daily_kline.asset_id", snapshot.features)
        self.assertEqual("external_provider.pub_stock_daily_kline", snapshot.dependencies[0].asset_id)
        self.assertEqual("20260704", snapshot.dependencies[0].query_params["snapshot_date"])

    def test_rejects_mismatched_snapshot_date(self) -> None:
        catalog = DataAssetCatalogLoader().from_mapping(sample_catalog_payload()).catalog
        builder = DeterministicAnalysisSnapshotBuilder(catalog=catalog)

        with self.assertRaisesRegex(ValueError, "trade_date"):
            builder.build_from_sources(
                stock_code="000001.SZ",
                snapshot_date="20260704",
                sources=(
                    SourceRows(
                        asset_id="external_provider.pub_stock_daily_kline",
                        rows=(
                            {
                                "asset_id": "000001.SZ",
                                "trade_date": "20260703",
                                "close": 12.34,
                                "amount": 1000000,
                                "quality_status": "pass",
                            },
                        ),
                    ),
                ),
            )
