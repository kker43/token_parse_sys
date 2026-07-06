"""Tests for research sample library review job."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workflows.jobs.research_sample_library_review import main


class ResearchSampleLibraryReviewJobTest(unittest.TestCase):
    def test_writes_sample_library_gate_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            sample_path = tmp_path / "samples.json"
            policy_path = tmp_path / "policy.json"
            output_path = tmp_path / "review.json"
            sample_path.write_text(json.dumps(_sample_library()), encoding="utf-8")
            policy_path.write_text(
                json.dumps(
                    {
                        "sample_library_gate_policy": {
                            "min_total_events": 2,
                            "min_dated_events": 2,
                            "min_positive_events": 1,
                            "min_high_value_positive_events": 1,
                            "min_negative_events": 1,
                            "min_hard_negative_events": 1,
                            "min_borderline_negative_events": 0,
                        }
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--sample-library-path",
                    str(sample_path),
                    "--policy-path",
                    str(policy_path),
                    "--output-path",
                    str(output_path),
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(0, exit_code)
            self.assertTrue(payload["passed"])
            self.assertEqual("research_sample_library_coverage", payload["gate"])
            self.assertEqual(2, payload["coverage"]["event_count"])
            self.assertEqual(str(sample_path), payload["sample_library_path"])


def _sample_library() -> dict[str, object]:
    return {
        "sample_library_id": "research_samples.test",
        "family_id": "test_family",
        "family_name": "测试形态",
        "samples": [
            {
                "sample_id": "sample_positive",
                "asset_id": "000001.SZ",
                "asset_name": "测试一",
                "sample_class": "positive",
                "events": [
                    {
                        "event_id": "evt_high",
                        "trade_date": "2026-01-05",
                        "timeframe": "daily",
                        "event_class": "positive_attention_high_value",
                        "value_tier": "high",
                    }
                ],
            },
            {
                "sample_id": "sample_negative",
                "asset_id": "000002.SZ",
                "asset_name": "测试二",
                "sample_class": "negative",
                "events": [
                    {
                        "event_id": "evt_hard",
                        "trade_date": "2026-01-07",
                        "timeframe": "daily",
                        "event_class": "hard_negative_recall",
                        "value_tier": "hard_negative",
                    }
                ],
            },
        ],
    }


if __name__ == "__main__":
    unittest.main()
