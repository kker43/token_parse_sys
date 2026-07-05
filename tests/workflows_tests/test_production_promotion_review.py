"""Tests for production-promotion review job."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workflows.jobs.production_promotion_review import main


class ProductionPromotionReviewJobTest(unittest.TestCase):
    def test_writes_failed_review_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            policy_path = tmp_path / "policy.json"
            evidence_path = tmp_path / "evidence.json"
            output_path = tmp_path / "review.json"
            policy_path.write_text(
                json.dumps(
                    {
                        "policy_id": "fixture",
                        "thresholds": {
                            "approved_production": {
                                "min_backtest_sample_size": 30,
                                "max_abs_backtest_drawdown": 0.25
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            evidence_path.write_text(
                json.dumps(
                    {
                        "artifact_id": "strategy.test",
                        "artifact_type": "strategy",
                        "current_status": "draft",
                        "target_status": "approved_production",
                        "owner": "stock_lobster",
                        "description": "fixture",
                        "backtest_sample_size": 17,
                        "backtest_max_drawdown": -0.30
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--policy-path",
                    str(policy_path),
                    "--evidence-path",
                    str(evidence_path),
                    "--output-path",
                    str(output_path),
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(1, exit_code)
            self.assertFalse(payload["review"]["passed"])


if __name__ == "__main__":
    unittest.main()
