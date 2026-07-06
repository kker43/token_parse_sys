"""Tests for research annotation queue build job."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workflows.jobs.research_annotation_queue_build import main


class ResearchAnnotationQueueBuildJobTest(unittest.TestCase):
    def test_writes_proposed_annotation_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            scan_path = tmp_path / "scan.json"
            backtest_path = tmp_path / "backtest.json"
            policy_path = tmp_path / "policy.json"
            output_path = tmp_path / "queue.json"
            scan_path.write_text(json.dumps(_scan_payload()), encoding="utf-8")
            backtest_path.write_text(json.dumps(_backtest_payload()), encoding="utf-8")
            policy_path.write_text(
                json.dumps(
                    {
                        "annotation_suggestion_policy": {
                            "high_value_return_threshold": 0.15,
                            "mid_positive_return_threshold": 0.05,
                            "hard_negative_return_threshold": -0.10,
                            "hard_negative_drawdown_threshold": -0.18,
                            "max_review_items": 10,
                        }
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--scan-result-path",
                    str(scan_path),
                    "--event-backtest-path",
                    str(backtest_path),
                    "--policy-path",
                    str(policy_path),
                    "--holding-horizon",
                    "20",
                    "--output-path",
                    str(output_path),
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(0, exit_code)
            self.assertEqual("proposed", payload["label_status"])
            self.assertTrue(payload["requires_human_confirmation"])
            self.assertEqual(2, payload["summary"]["item_count"])
            self.assertEqual("queue_item_id<TAB>review_code", payload["review_input_format"])
            self.assertEqual(
                list(range(1, 9)),
                [option["code"] for option in payload["review_label_options"]],
            )
            self.assertEqual(
                "positive_attention_high_value",
                payload["items"][0]["suggested_event_class"],
            )
            self.assertEqual(1, payload["items"][0]["suggested_review_code"])
            self.assertIsNone(payload["items"][0]["human_review"]["confirmed_event_class"])


def _scan_payload() -> dict[str, object]:
    return {
        "breakout_candidates": [
            {
                "asset_id": "000001.SZ",
                "trade_date": "20260101",
                "name": "测试一",
                "setup_score": 82.0,
                "daily_quality_pass": True,
                "trend_stability_pass": True,
                "breakout_watch": True,
                "close_new_high_60d_flag": True,
            },
            {
                "asset_id": "000002.SZ",
                "trade_date": "20260102",
                "name": "测试二",
                "setup_score": 61.0,
                "daily_quality_pass": True,
                "trend_stability_pass": True,
                "breakout_watch": True,
                "close_new_high_60d_flag": True,
            },
        ]
    }


def _backtest_payload() -> dict[str, object]:
    return {
        "reports": [
            {
                "result": {"holding_horizon": 20},
                "trades": [
                    {
                        "event_id": "000001.SZ.20260101",
                        "holding_return": 0.18,
                        "max_drawdown": -0.06,
                    },
                    {
                        "event_id": "000002.SZ.20260102",
                        "holding_return": -0.04,
                        "max_drawdown": -0.08,
                    },
                ],
            }
        ]
    }


if __name__ == "__main__":
    unittest.main()
