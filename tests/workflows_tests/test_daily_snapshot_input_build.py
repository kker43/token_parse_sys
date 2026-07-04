"""Tests for the snapshot input build workflow job."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from stock_lobster.l0_data_access.adapters.external_mysql import ExternalMysqlAdapter
from tests.l1_analysis_snapshot_tests.test_snapshot_builder import sample_catalog_payload
from tests.l0_data_access_tests.test_external_mysql_adapter import FakeConnection, FakeCursor
from workflows.jobs.daily_snapshot_input_build import main


class DailySnapshotInputBuildJobTest(unittest.TestCase):
    def test_job_builds_snapshot_input_from_schedule(self) -> None:
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            catalog_path = root / "catalog.json"
            mysql_config_path = root / "mysql.json"
            request_path = root / "request.json"
            output_path = root / "input.json"
            result_path = root / "result.json"
            schedule_path = root / "schedule.json"
            catalog_path.write_text(json.dumps(sample_catalog_payload()), encoding="utf-8")
            mysql_config_path.write_text(
                json.dumps({"user": "readonly", "password": "", "database": "tokens"}),
                encoding="utf-8",
            )
            request_path.write_text(
                json.dumps(
                    {
                        "analysis_version": "analysis_v1",
                        "snapshot_date": "20260704",
                        "stock_codes": ["000001.SZ"],
                        "source_assets": [
                            {
                                "asset_id": "external_provider.pub_stock_daily_kline",
                                "fields": ["asset_id", "trade_date", "close"],
                                "limit": 1,
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
                        "mysql_config_path": str(mysql_config_path),
                        "request_path": str(request_path),
                        "output_path": str(output_path),
                        "job_result_path": str(result_path),
                    }
                ),
                encoding="utf-8",
            )

            cursor = FakeCursor()
            adapter = ExternalMysqlAdapter(
                connection_name="fixture",
                connection_factory=lambda: FakeConnection(cursor),
            )
            stdout = io.StringIO()
            with patch.object(ExternalMysqlAdapter, "from_config_path", return_value=adapter):
                with redirect_stdout(stdout):
                    exit_code = main(["--schedule-config-path", str(schedule_path)])

            output_payload = json.loads(output_path.read_text(encoding="utf-8"))
            result_payload = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        self.assertEqual("success", result_payload["status"])
        self.assertEqual(1, result_payload["stock_count"])
        self.assertEqual(12.34, output_payload["snapshots"][0]["sources"][0]["rows"][0]["close"])


if __name__ == "__main__":
    unittest.main()
