"""Tests for the operator-facing data-foundation CLI."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from interfaces.cli.data_foundation import main


def sample_registry() -> dict[str, object]:
    return {
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
                    "trade_date",
                    "close",
                    "published_at",
                    "data_version",
                    "quality_status",
                ],
                "consumer_contract": {
                    "check_quality_status_before_query": True,
                },
            }
        ],
    }


def sample_field_types() -> dict[str, dict[str, str]]:
    return {
        "pub_stock_daily_kline": {
            "asset_id": "string",
            "trade_date": "date_yyyymmdd",
            "close": "numeric",
            "published_at": "timestamp",
            "data_version": "string",
            "quality_status": "string",
        }
    }


def sample_quality_status(status: str = "ready", quality_level: str = "pass") -> dict[str, object]:
    return {
        "statuses": [
            {
                "data_product": "pub_stock_daily_kline",
                "data_date": "20260704",
                "market": "CN_A",
                "asset_type": "stock",
                "status": status,
                "quality_level": quality_level,
                "record_count": 5000,
                "expected_min_records": 4000,
                "source_tables": ["token_daily_details"],
                "source_end_date": "20260704",
                "published_at": "2026-07-04T20:00:00Z",
                "data_version": "v1",
                "error_message": None,
            }
        ]
    }


def sample_observed_inputs() -> dict[str, object]:
    return {
        "products": {
            "pub_stock_daily_kline": {
                "observed_dates": ["20260704"],
                "observed_non_null_fields": [
                    "asset_id",
                    "trade_date",
                    "close",
                    "published_at",
                    "data_version",
                    "quality_status",
                ],
                "observed_data_version": "v1",
                "observed_record_count": 5000,
            }
        }
    }


class DataFoundationCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.registry_path = self.root / "registry.json"
        self.field_types_path = self.root / "field_types.json"
        self.quality_path = self.root / "quality.json"
        self.observed_path = self.root / "observed.json"

        self.registry_path.write_text(json.dumps(sample_registry()), encoding="utf-8")
        self.field_types_path.write_text(json.dumps(sample_field_types()), encoding="utf-8")
        self.quality_path.write_text(json.dumps(sample_quality_status()), encoding="utf-8")
        self.observed_path.write_text(json.dumps(sample_observed_inputs()), encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_list_products_outputs_registry_summary(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "list-products",
                    "--registry-path",
                    str(self.registry_path),
                    "--field-types-path",
                    str(self.field_types_path),
                    "--source-commit",
                    "commit-1234567",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual("commit-1234567", payload["source_commit"])
        self.assertEqual("pub_stock_daily_kline", payload["products"][0]["name"])

    def test_export_data_assets_writes_catalog_json(self) -> None:
        output_path = self.root / "catalog.json"
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "export-data-assets",
                    "--registry-path",
                    str(self.registry_path),
                    "--field-types-path",
                    str(self.field_types_path),
                    "--output-path",
                    str(output_path),
                ]
            )

        self.assertEqual(0, exit_code)
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual("external_provider.pub_stock_daily_kline", payload["products"][0]["data_asset_id"])

    def test_check_readiness_returns_non_zero_for_blocked_product(self) -> None:
        self.quality_path.write_text(
            json.dumps(sample_quality_status(status="failed", quality_level="failed")),
            encoding="utf-8",
        )

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "check-readiness",
                    "--registry-path",
                    str(self.registry_path),
                    "--field-types-path",
                    str(self.field_types_path),
                    "--quality-path",
                    str(self.quality_path),
                    "--observed-inputs-path",
                    str(self.observed_path),
                    "--date",
                    "20260704",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(1, exit_code)
        self.assertFalse(payload["overall_ready"])
        self.assertEqual(["quality_gate_blocked"], payload["results"][0]["reasons"])
