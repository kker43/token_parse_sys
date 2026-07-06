"""Tests for observation lifecycle records."""

from __future__ import annotations

import unittest

from stock_lobster.l6_backtest_engine import EvaluationProfile
from stock_lobster.observation import ObservationRecord, build_pending_test_tracking_record


class ObservationRecordTest(unittest.TestCase):
    def test_builds_pending_test_tracking_record_without_approval(self) -> None:
        profile = EvaluationProfile(
            profile_id="evaluation.test.v1",
            strategy_id="strategy.test",
            strategy_version="candidate_v1",
            benchmark="CANDIDATE_POOL_EQUAL_WEIGHT",
            comparison_benchmarks=("CN_A_EQUAL_WEIGHT", "000905.SH", "000852.SH", "000300.SH", "000698.SH"),
            holding_horizons=(5, 20),
            selection_frequency="daily_after_close",
        )

        record = build_pending_test_tracking_record(
            profile=profile,
            source_evidence_id="evidence.test",
            promotion_blockers=("sample_size 20 < 30",),
        )

        self.assertEqual("pending_approval", record.lifecycle_status)
        self.assertEqual("pending_user_approval", record.approval_status)
        self.assertIn("CN_A_EQUAL_WEIGHT", record.to_mapping()["comparison_benchmarks"])
        self.assertIn("000698.SH", record.to_mapping()["comparison_benchmarks"])
        self.assertEqual(["sample_size 20 < 30"], record.to_mapping()["promotion_blockers"])

    def test_rejects_non_pending_record_without_approval(self) -> None:
        with self.assertRaises(ValueError):
            ObservationRecord(
                observation_id="observation.test",
                strategy_id="strategy.test",
                strategy_version="candidate_v1",
                lifecycle_status="test_tracking",
                approval_status="pending_user_approval",
                source_evidence_id="evidence.test",
                evaluation_profile_id="evaluation.test.v1",
                benchmark="CANDIDATE_POOL_EQUAL_WEIGHT",
                review_frequency="daily_after_close",
                review_horizons=(5, 20),
            )


if __name__ == "__main__":
    unittest.main()
