"""Tests for routine data-foundation workflow jobs."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from workflows.jobs.daily_data_asset_export import main as export_job_main
from workflows.jobs.daily_data_quality_monitor import main as quality_job_main


def sample_registry() -> dict[str, object]:
    return {
        "schema_version": 1,
        "products": [
            {
                "name": "pub_stock_daily_indicator",
                "product_type": "indicator_long_table",
                "market": "CN_A",
                "asset_type": "stock",
                "level": "daily",
                "grain": "asset_indicator_trade_date",
                "primary_key": ["asset_id", "trade_date", "indicator_name"],
                "source_tables": ["close_price_daily_statistic"],
                "data_version": "v1",
                "required_fields": [
                    "asset_id",
                    "trade_date",
                    "indicator_name",
                    "indicator_value",
                    "published_at",
                    "quality_status",
                ],
            }
        ],
    }


def sample_field_types() -> dict[str, dict[str, str]]:
    return {
        "pub_stock_daily_indicator": {
            "asset_id": "string",
            "trade_date": "date_yyyymmdd",
            "indicator_name": "string",
            "indicator_value": "numeric",
            "published_at": "timestamp",
            "quality_status": "string",
        }
    }


def sample_quality_status(status: str = "ready", quality_level: str = "pass") -> dict[str, object]:
    return {
        "statuses": [
            {
                "data_product": "pub_stock_daily_indicator",
                "data_date": "20260704",
                "market": "CN_A",
                "asset_type": "stock",
                "status": status,
                "quality_level": quality_level,
                "record_count": 4200,
                "expected_min_records": 4000,
                "source_tables": ["close_price_daily_statistic"],
                "source_end_date": "20260704",
                "published_at": "2026-07-04T20:00:00Z",
                "data_version": "v1",
                "error_message": None,
            }
        ]
    }


def sample_observed_inputs() -> dict[str, object]:
    return {
        "pub_stock_daily_indicator": {
            "observed_dates": ["20260704"],
            "observed_non_null_fields": [
                "asset_id",
                "trade_date",
                "indicator_name",
                "indicator_value",
                "published_at",
                "quality_status",
            ],
            "observed_data_version": "v1",
            "observed_record_count": 4200,
        }
    }


class DailyDataFoundationJobsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.registry_path = self.root / "registry.json"
        self.field_types_path = self.root / "field_types.json"
        self.quality_path = self.root / "quality.json"
        self.observed_path = self.root / "observed.json"
        self.export_output_path = self.root / "catalog.json"
        self.export_result_path = self.root / "export_result.json"
        self.quality_result_path = self.root / "quality_result.json"

        self.registry_path.write_text(json.dumps(sample_registry()), encoding="utf-8")
        self.field_types_path.write_text(json.dumps(sample_field_types()), encoding="utf-8")
        self.quality_path.write_text(json.dumps(sample_quality_status()), encoding="utf-8")
        self.observed_path.write_text(json.dumps(sample_observed_inputs()), encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_daily_data_asset_export_writes_catalog_and_job_result(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = export_job_main(
                [
                    "--registry-path",
                    str(self.registry_path),
                    "--field-types-path",
                    str(self.field_types_path),
                    "--output-path",
                    str(self.export_output_path),
                    "--job-result-path",
                    str(self.export_result_path),
                ]
            )

        self.assertEqual(0, exit_code)
        catalog_payload = json.loads(self.export_output_path.read_text(encoding="utf-8"))
        result_payload = json.loads(self.export_result_path.read_text(encoding="utf-8"))
        self.assertEqual("success", result_payload["status"])
        self.assertEqual("pub_stock_daily_indicator", catalog_payload["products"][0]["data_product"])

    def test_daily_data_quality_monitor_returns_failure_when_gate_is_blocked(self) -> None:
        self.quality_path.write_text(
            json.dumps(sample_quality_status(status="failed", quality_level="failed")),
            encoding="utf-8",
        )

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = quality_job_main(
                [
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
                    "--job-result-path",
                    str(self.quality_result_path),
                ]
            )

        self.assertEqual(1, exit_code)
        result_payload = json.loads(self.quality_result_path.read_text(encoding="utf-8"))
        self.assertEqual("failed", result_payload["status"])
        self.assertFalse(result_payload["overall_ready"])
        self.assertEqual(["quality_gate_blocked"], result_payload["results"][0]["reasons"])
