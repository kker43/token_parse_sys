"""Tests for steady-uptrend wide recall pool extraction."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from workflows.jobs.steady_uptrend_wide_recall_pool import main


class SteadyUptrendWideRecallPoolJobTest(unittest.TestCase):
    def test_extracts_diverse_rejected_candidates_for_research_review(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scan_path = root / "scan.json"
            output_path = root / "wide_recall.json"
            scan_path.write_text(
                json.dumps(
                    {
                        "v3_rejected_candidates": [
                            _candidate("000001.SZ", "20260102", ["pre_breakout_too_far_from_high"], -0.065, 80),
                            _candidate("000002.SZ", "20260102", ["pre_breakout_too_far_from_high"], -0.070, 75),
                            _candidate("000003.SZ", "20260102", ["blocked_risk_context"], -0.030, 70),
                            _candidate("000004.SZ", "20260103", ["market_breadth_ma20_overheated"], -0.040, 90),
                            _candidate("000005.SZ", "20260104", ["daily_quality_failed"], -0.040, 99),
                        ]
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--scan-result-path",
                    str(scan_path),
                    "--output-path",
                    str(output_path),
                    "--max-items-per-bucket-per-date",
                    "1",
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(0, exit_code)
            self.assertEqual("steady_uptrend_wide_recall_pool", payload["job_name"])
            self.assertEqual(3, payload["candidate_count"])
            self.assertEqual("review_idx<TAB>review_code", payload["review_input_format"])
            self.assertEqual(
                [1, 2, 3],
                [item["review_idx"] for item in payload["wide_recall_candidates"]],
            )
            self.assertEqual(
                [1, 2, 3, 4, 5, 6, 7, 8],
                [option["code"] for option in payload["review_label_options"]],
            )
            self.assertEqual(
                {
                    "near_pre_breakout": 1,
                    "risk_context_rejected": 1,
                    "market_temperature_rejected": 1,
                },
                payload["summary"]["by_research_bucket"],
            )
            self.assertEqual(
                [
                    ("20260102", "000001.SZ", "near_pre_breakout"),
                    ("20260102", "000003.SZ", "risk_context_rejected"),
                    ("20260103", "000004.SZ", "market_temperature_rejected"),
                ],
                [
                    (item["trade_date"], item["asset_id"], item["research_bucket"])
                    for item in payload["wide_recall_candidates"]
                ],
            )
            self.assertTrue(all(item["label_status"] == "proposed" for item in payload["wide_recall_candidates"]))


def _candidate(
    asset_id: str,
    trade_date: str,
    reasons: list[str],
    close_to_high: float,
    score: float,
) -> dict[str, object]:
    return {
        "asset_id": asset_id,
        "trade_date": trade_date,
        "name": asset_id,
        "pre_breakout_watch": True,
        "breakout_watch": False,
        "v3_rejection_reasons": reasons,
        "close_to_high_60d_pct": close_to_high,
        "v3_score": score,
        "setup_score": score,
    }


if __name__ == "__main__":
    unittest.main()
