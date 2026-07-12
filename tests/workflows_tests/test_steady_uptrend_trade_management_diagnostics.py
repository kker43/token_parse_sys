"""Tests for steady uptrend short trade-management diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workflows.jobs.steady_uptrend_trade_management_diagnostics import main


class SteadyUptrendTradeManagementDiagnosticsJobTest(unittest.TestCase):
    def test_outputs_default_trade_management_variants(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            kline_path = tmp_path / "kline.tsv"
            scan_path = tmp_path / "scan.json"
            output_path = tmp_path / "diagnostics.json"
            summary_path = tmp_path / "diagnostics.md"

            kline_path.write_text(
                "\n".join(
                    [
                        "000001.SZ\t20260101\t10\t10.2\t9.8\t10\t100",
                        "000001.SZ\t20260102\t10\t10.8\t9.5\t10.6\t100",
                        "000001.SZ\t20260103\t10.6\t10.9\t8.9\t9.1\t100",
                        "000001.SZ\t20260104\t9.1\t9.4\t8.8\t9.2\t100",
                        "000001.SZ\t20260105\t9.2\t9.5\t9.0\t9.4\t100",
                        "000001.SZ\t20260106\t9.4\t9.8\t9.2\t9.6\t100",
                        "000002.SZ\t20260201\t20\t20.5\t19.8\t20\t100",
                        "000002.SZ\t20260202\t20\t20.8\t19.5\t20.6\t100",
                        "000002.SZ\t20260203\t20.6\t21.2\t20.4\t21.0\t100",
                        "000002.SZ\t20260204\t21.0\t21.5\t20.8\t21.2\t100",
                        "000002.SZ\t20260205\t21.2\t21.8\t21.0\t21.6\t100",
                        "000002.SZ\t20260206\t21.6\t22.0\t21.4\t21.8\t100",
                    ]
                ),
                encoding="utf-8",
            )
            scan_path.write_text(
                json.dumps(
                    {
                        "observation_candidates": [
                            {
                                "asset_id": "000001.SZ",
                                "trade_date": "20260101",
                                "market_temperature": {
                                    "breadth_ma20": 0.30
                                },
                            },
                            {
                                "asset_id": "000002.SZ",
                                "trade_date": "20260201",
                                "market_temperature": {
                                    "breadth_ma20": 0.60
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--kline-tsv-path",
                    str(kline_path),
                    "--scan-result-path",
                    str(scan_path),
                    "--candidate-pool-key",
                    "observation_candidates",
                    "--output-path",
                    str(output_path),
                    "--summary-md-path",
                    str(summary_path),
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(0, exit_code)
            self.assertEqual("steady_uptrend_trade_management_diagnostics", payload["job_name"])
            self.assertEqual("observation_candidates", payload["candidate_pool_key"])
            self.assertIn("baseline_h5", payload["variants"])
            self.assertIn("stop_loss_10", payload["variants"])
            self.assertEqual(2, payload["variants"]["baseline_h5"]["result"]["sample_size"])
            self.assertEqual(
                1,
                payload["stability"]["signal_month"]["baseline_h5"]["202601"]["sample_size"],
            )
            self.assertEqual(
                1,
                payload["stability"]["signal_month"]["baseline_h5"]["202602"]["sample_size"],
            )
            self.assertEqual(
                1,
                payload["stability"]["market_breadth_ma20_bucket"]["baseline_h5"]["breadth_lt_35"]["sample_size"],
            )
            self.assertEqual(
                1,
                payload["stability"]["market_breadth_ma20_bucket"]["baseline_h5"]["breadth_ge_55"]["sample_size"],
            )
            self.assertTrue(summary_path.read_text(encoding="utf-8").startswith("# steady uptrend trade management"))

    def test_can_limit_daily_candidates_in_weak_market_breadth(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            kline_path = tmp_path / "kline.tsv"
            scan_path = tmp_path / "scan.json"
            output_path = tmp_path / "diagnostics.json"

            rows: list[str] = []
            for asset_id, start_price, month in (
                ("000001.SZ", 10, "202601"),
                ("000002.SZ", 20, "202602"),
                ("000003.SZ", 30, "202601"),
            ):
                for index in range(6):
                    price = start_price + index
                    rows.append(f"{asset_id}\t{month}{index + 1:02d}\t{price}\t{price + 1}\t{price - 1}\t{price + 0.5}\t100")
            kline_path.write_text("\n".join(rows), encoding="utf-8")
            scan_path.write_text(
                json.dumps(
                    {
                        "observation_candidates": [
                            {
                                "asset_id": "000001.SZ",
                                "trade_date": "20260101",
                                "market_temperature": {"breadth_ma20": 0.30},
                            },
                            {
                                "asset_id": "000003.SZ",
                                "trade_date": "20260101",
                                "market_temperature": {"breadth_ma20": 0.30},
                            },
                            {
                                "asset_id": "000002.SZ",
                                "trade_date": "20260201",
                                "market_temperature": {"breadth_ma20": 0.60},
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--kline-tsv-path",
                    str(kline_path),
                    "--scan-result-path",
                    str(scan_path),
                    "--candidate-pool-key",
                    "observation_candidates",
                    "--weak-breadth-ma20-threshold",
                    "0.35",
                    "--weak-breadth-top-n",
                    "1",
                    "--output-path",
                    str(output_path),
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(0, exit_code)
            self.assertEqual(2, payload["event_count"])
            self.assertEqual(
                {
                    "market_breadth_ma20_lt": 0.35,
                    "top_n_per_signal_date": 1,
                },
                payload["candidate_pool_variant_policy"]["weak_breadth_limit"],
            )
            self.assertEqual(2, payload["variants"]["baseline_h5"]["result"]["sample_size"])


if __name__ == "__main__":
    unittest.main()
