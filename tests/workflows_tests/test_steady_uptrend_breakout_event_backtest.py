"""Tests for steady uptrend breakout event backtest job."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workflows.jobs.steady_uptrend_breakout_event_backtest import _read_events, main


class SteadyUptrendBreakoutEventBacktestJobTest(unittest.TestCase):
    def test_reads_configured_v4_candidate_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "scan.json"
            path.write_text(
                json.dumps(
                    {
                        "final_signals": [
                            {"asset_id": "000001.SZ", "trade_date": "20260101"}
                        ]
                    }
                ),
                encoding="utf-8",
            )

            events = _read_events(path, candidate_key="final_signals")

        self.assertEqual(1, len(events))
        self.assertEqual("000001.SZ.20260101", events[0].event_id)

    def test_runs_event_backtest_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            kline_path = tmp_path / "kline.tsv"
            scan_path = tmp_path / "scan.json"
            output_path = tmp_path / "backtest.json"

            kline_path.write_text(
                "\n".join(
                    f"000001.SZ\t202601{index + 1:02d}\t{10 + index}\t{11 + index}\t{9 + index}\t{10.5 + index}\t100"
                    for index in range(8)
                ),
                encoding="utf-8",
            )
            scan_path.write_text(
                json.dumps(
                    {
                        "breakout_candidates": [
                            {
                                "asset_id": "000001.SZ",
                                "trade_date": "20260101",
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
                    "--output-path",
                    str(output_path),
                    "--holding-horizon",
                    "3",
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(0, exit_code)
            self.assertEqual(1, payload["event_count"])
            self.assertEqual(1, payload["reports"][0]["result"]["sample_size"])


if __name__ == "__main__":
    unittest.main()
