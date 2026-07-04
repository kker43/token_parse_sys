"""Tests for the routine L1 snapshot-production workflow job."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests.l1_analysis_snapshot_tests.test_snapshot_builder import sample_catalog_payload
from workflows.jobs.daily_snapshot_production import main


class DailySnapshotProductionJobTest(unittest.TestCase):
    def test_job_reads_schedule_config(self) -> None:
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            catalog_path = root / "catalog.json"
            input_path = root / "snapshot_input.json"
            output_path = root / "snapshots.json"
            result_path = root / "result.json"
            schedule_path = root / "daily_snapshot.json"
            catalog_path.write_text(json.dumps(sample_catalog_payload()), encoding="utf-8")
            input_path.write_text(
                json.dumps(
                    {
                        "snapshot_date": "20260704",
                        "snapshots": [
                            {
                                "stock_code": "000001.SZ",
                                "sources": [
                                    {
                                        "asset_id": "external_provider.pub_stock_daily_kline",
                                        "rows": [
                                            {
                                                "asset_id": "000001.SZ",
                                                "trade_date": "20260704",
                                                "close": 12.34,
                                                "amount": 1000000,
                                                "quality_status": "pass",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            schedule_path.write_text(
                json.dumps(
                    {
                        "catalog_path": str(catalog_path),
                        "snapshot_input_path": str(input_path),
                        "output_path": str(output_path),
                        "job_result_path": str(result_path),
                        "analysis_version": "analysis_v1",
                    }
                ),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["--schedule-config-path", str(schedule_path)])

            result_payload = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        self.assertEqual(str(schedule_path.resolve()), result_payload["schedule_config_path"])
        self.assertEqual(1, result_payload["snapshot_count"])

    def test_job_writes_snapshot_output_and_result(self) -> None:
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            catalog_path = root / "catalog.json"
            input_path = root / "snapshot_input.json"
            output_path = root / "snapshots.json"
            result_path = root / "result.json"
            catalog_path.write_text(json.dumps(sample_catalog_payload()), encoding="utf-8")
            input_path.write_text(
                json.dumps(
                    {
                        "analysis_version": "analysis_v1",
                        "snapshot_date": "20260704",
                        "snapshots": [
                            {
                                "stock_code": "000001.SZ",
                                "sources": [
                                    {
                                        "asset_id": "external_provider.pub_stock_daily_kline",
                                        "query_version": "query_v1",
                                        "rows": [
                                            {
                                                "asset_id": "000001.SZ",
                                                "trade_date": "20260704",
                                                "close": 12.34,
                                                "amount": 1000000,
                                                "quality_status": "pass",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--catalog-path",
                        str(catalog_path),
                        "--snapshot-input-path",
                        str(input_path),
                        "--output-path",
                        str(output_path),
                        "--job-result-path",
                        str(result_path),
                    ]
                )

            output_payload = json.loads(output_path.read_text(encoding="utf-8"))
            result_payload = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        self.assertEqual("success", result_payload["status"])
        self.assertEqual(1, result_payload["snapshot_count"])
        self.assertEqual(12.34, output_payload["snapshots"][0]["features"]["pub_stock_daily_kline.close"])
