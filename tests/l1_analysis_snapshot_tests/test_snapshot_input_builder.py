"""Tests for building snapshot input from L0 row readers."""

from __future__ import annotations

from typing import Mapping
import unittest

from stock_lobster.l0_data_access.config_loader import DataAssetCatalogLoader
from stock_lobster.l0_data_access.contracts import DataAsset
from stock_lobster.l1_analysis_snapshot import SnapshotInputBuilder, SnapshotSourceRequest
from tests.l1_analysis_snapshot_tests.test_snapshot_builder import sample_catalog_payload


class FakeRowReader:
    def fetch_rows(
        self,
        asset: DataAsset,
        filters: Mapping[str, object],
        fields: tuple[str, ...] | None = None,
        limit: int | None = None,
    ) -> tuple[Mapping[str, object], ...]:
        return (
            {
                "asset_id": filters["asset_id"],
                "trade_date": filters["trade_date"],
                "close": 12.34,
                "amount": 1000000,
                "quality_status": "pass",
            },
        )


class SnapshotInputBuilderTest(unittest.TestCase):
    def test_builds_snapshot_input_payload_from_l0_reader(self) -> None:
        catalog = DataAssetCatalogLoader().from_mapping(sample_catalog_payload()).catalog
        builder = SnapshotInputBuilder(catalog=catalog, row_reader=FakeRowReader())

        payload = builder.build_input(
            stock_codes=("000001.SZ",),
            snapshot_date="20260704",
            source_requests=(
                SnapshotSourceRequest(
                    asset_id="external_provider.pub_stock_daily_kline",
                    fields=("asset_id", "trade_date", "close", "amount", "quality_status"),
                    limit=1,
                ),
            ),
        )

        source = payload["snapshots"][0]["sources"][0]  # type: ignore[index]
        self.assertEqual("20260704", payload["snapshot_date"])
        self.assertEqual("external_provider.pub_stock_daily_kline", source["asset_id"])
        self.assertEqual(12.34, source["rows"][0]["close"])
        self.assertEqual("000001.SZ", source["query_params"]["asset_id"])


if __name__ == "__main__":
    unittest.main()
