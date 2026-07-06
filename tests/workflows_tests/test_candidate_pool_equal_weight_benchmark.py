"""Tests for candidate-pool equal-weight benchmark job."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workflows.jobs.candidate_pool_equal_weight_benchmark import main


class CandidatePoolEqualWeightBenchmarkJobTest(unittest.TestCase):
    def test_writes_candidate_pool_benchmark_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            kline_path = tmp_path / "kline.tsv"
            candidate_pool_path = tmp_path / "candidate_pool.json"
            output_path = tmp_path / "benchmark.json"
            kline_path.write_text(
                "\n".join(
                    [
                        "000001.SZ\t20260101\t10\t10\t10\t10\t100",
                        "000001.SZ\t20260102\t10\t11\t10\t11\t100",
                        "000001.SZ\t20260103\t11\t12\t11\t12\t100",
                        "000002.SZ\t20260101\t20\t20\t20\t20\t100",
                        "000002.SZ\t20260102\t20\t20\t18\t18\t100",
                        "000002.SZ\t20260103\t18\t18\t16\t16\t100",
                    ]
                ),
                encoding="utf-8",
            )
            candidate_pool_path.write_text(
                json.dumps(
                    {
                        "breakout_candidates": [
                            {"asset_id": "000001.SZ", "trade_date": "20260101"}
                        ],
                        "candidate_pool": [
                            {"asset_id": "000001.SZ", "trade_date": "20260101"},
                            {"asset_id": "000002.SZ", "trade_date": "20260101"},
                        ],
                        "stage_candidate_pools": {
                            "signal_pool": [
                                {"asset_id": "000001.SZ", "trade_date": "20260101"}
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--kline-tsv-path",
                    str(kline_path),
                    "--candidate-pool-path",
                    str(candidate_pool_path),
                    "--output-path",
                    str(output_path),
                    "--holding-horizon",
                    "2",
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(0, exit_code)
            self.assertEqual(2, payload["event_count"])
            self.assertEqual(1, len(payload["benchmark_results"]))
            self.assertAlmostEqual(
                0.0,
                payload["benchmark_results"][0]["return_metrics"]["avg_signal_date_return"],
            )

    def test_reads_requested_stage_candidate_pool_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            kline_path = tmp_path / "kline.tsv"
            candidate_pool_path = tmp_path / "candidate_pool.json"
            output_path = tmp_path / "benchmark.json"
            kline_path.write_text(
                "\n".join(
                    [
                        "000001.SZ\t20260101\t10\t10\t10\t10\t100",
                        "000001.SZ\t20260102\t10\t11\t10\t11\t100",
                        "000001.SZ\t20260103\t11\t12\t11\t12\t100",
                        "000002.SZ\t20260101\t20\t20\t20\t20\t100",
                        "000002.SZ\t20260102\t20\t20\t18\t18\t100",
                        "000002.SZ\t20260103\t18\t18\t16\t16\t100",
                    ]
                ),
                encoding="utf-8",
            )
            candidate_pool_path.write_text(
                json.dumps(
                    {
                        "candidate_pool": [
                            {"asset_id": "000001.SZ", "trade_date": "20260101"},
                            {"asset_id": "000002.SZ", "trade_date": "20260101"},
                        ],
                        "stage_candidate_pools": {
                            "signal_pool": [
                                {"asset_id": "000001.SZ", "trade_date": "20260101"}
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--kline-tsv-path",
                    str(kline_path),
                    "--candidate-pool-path",
                    str(candidate_pool_path),
                    "--candidate-pool-key",
                    "signal_pool",
                    "--output-path",
                    str(output_path),
                    "--holding-horizon",
                    "2",
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(0, exit_code)
            self.assertEqual("signal_pool", payload["source_candidate_pool_key"])
            self.assertEqual(1, payload["event_count"])

    def test_rejects_missing_explicit_candidate_pool_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            kline_path = tmp_path / "kline.tsv"
            candidate_pool_path = tmp_path / "candidate_pool.json"
            output_path = tmp_path / "benchmark.json"
            kline_path.write_text(
                "\n".join(
                    [
                        "000001.SZ\t20260101\t10\t10\t10\t10\t100",
                        "000001.SZ\t20260102\t10\t11\t10\t11\t100",
                    ]
                ),
                encoding="utf-8",
            )
            candidate_pool_path.write_text(
                json.dumps(
                    {
                        "candidate_pool": [
                            {"asset_id": "000001.SZ", "trade_date": "20260101"}
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                main(
                    [
                        "--kline-tsv-path",
                        str(kline_path),
                        "--candidate-pool-path",
                        str(candidate_pool_path),
                        "--candidate-pool-key",
                        "signal_pool",
                        "--output-path",
                        str(output_path),
                        "--holding-horizon",
                        "1",
                    ]
                )


if __name__ == "__main__":
    unittest.main()
