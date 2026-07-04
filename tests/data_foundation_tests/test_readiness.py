"""Tests for deterministic published-product readiness checks."""

from __future__ import annotations

import unittest

from data_foundation.quality import (
    DataProductReadinessChecker,
    DataProductReadinessInputs,
)
from shared.contracts import DataProductContract, DataProductField, DataQualityStatus


def make_contract() -> DataProductContract:
    return DataProductContract(
        name="pub_stock_daily_indicator",
        product_type="indicator_long_table",
        market="CN_A",
        asset_type="stock",
        grain="asset_indicator_trade_date",
        data_version="v1",
        update_frequency="daily",
        required_fields=(
            DataProductField("asset_id", "string"),
            DataProductField("trade_date", "date_yyyymmdd"),
            DataProductField("indicator_name", "string"),
            DataProductField("indicator_value", "numeric"),
            DataProductField("published_at", "timestamp"),
            DataProductField("quality_status", "string"),
        ),
        primary_key=(
            "asset_id",
            "trade_date",
            "indicator_name",
        ),
        source_tables=("close_price_daily_statistic",),
    )


def make_quality_status(**overrides: object) -> DataQualityStatus:
    payload = {
        "data_product": "pub_stock_daily_indicator",
        "data_date": "20260704",
        "market": "CN_A",
        "asset_type": "stock",
        "status": "ready",
        "quality_level": "pass",
        "record_count": 4200,
        "expected_min_records": 4000,
        "source_tables": ["close_price_daily_statistic"],
        "source_end_date": "20260704",
        "published_at": "2026-07-04T20:00:00Z",
        "data_version": "v1",
        "error_message": None,
    }
    payload.update(overrides)
    return DataQualityStatus.from_mapping(payload)


class DataProductReadinessCheckerTest(unittest.TestCase):
    def test_accepts_ready_product_when_all_checks_pass(self) -> None:
        contract = make_contract()
        quality_status = make_quality_status()
        inputs = DataProductReadinessInputs(
            requested_date="20260704",
            observed_dates=frozenset({"20260704"}),
            observed_non_null_fields=frozenset(
                {
                    "asset_id",
                    "trade_date",
                    "indicator_name",
                    "indicator_value",
                    "published_at",
                    "quality_status",
                }
            ),
            observed_data_version="v1",
            observed_record_count=4200,
        )

        result = DataProductReadinessChecker().check(contract, quality_status, inputs)

        self.assertTrue(result.ready)
        self.assertEqual((), result.reasons)

    def test_blocks_product_when_quality_gate_fails(self) -> None:
        contract = make_contract()
        quality_status = make_quality_status(status="failed", quality_level="failed")
        inputs = DataProductReadinessInputs(
            requested_date="20260704",
            observed_non_null_fields=frozenset(
                {
                    "asset_id",
                    "trade_date",
                    "indicator_name",
                    "indicator_value",
                    "published_at",
                    "quality_status",
                }
            ),
            observed_data_version="v1",
        )

        result = DataProductReadinessChecker().check(contract, quality_status, inputs)

        self.assertFalse(result.ready)
        self.assertIn("quality_gate_blocked", result.reasons)

    def test_blocks_product_when_required_fields_are_missing(self) -> None:
        contract = make_contract()
        quality_status = make_quality_status()
        inputs = DataProductReadinessInputs(
            requested_date="20260704",
            observed_dates=frozenset({"20260704"}),
            observed_non_null_fields=frozenset({"asset_id", "trade_date"}),
            observed_data_version="v2",
            observed_record_count=3999,
        )

        result = DataProductReadinessChecker().check(contract, quality_status, inputs)

        self.assertFalse(result.ready)
        self.assertIn("record_count_mismatch", result.reasons)
        self.assertIn("data_version_mismatch", result.reasons)
        self.assertTrue(
            any(reason.startswith("missing_non_null_fields:") for reason in result.reasons)
        )
