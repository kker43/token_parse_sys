"""Tests for production-promotion review rules."""

from __future__ import annotations

import unittest

from data_foundation.quality import (
    PromotionEvidence,
    PromotionPolicy,
    PromotionThresholds,
    review_promotion,
)


class ProductionPromotionReviewTest(unittest.TestCase):
    def test_rejects_approved_production_when_evidence_is_insufficient(self) -> None:
        result = review_promotion(
            evidence=PromotionEvidence(
                artifact_id="strategy.test",
                artifact_type="strategy",
                current_status="draft",
                target_status="approved_production",
                owner="stock_lobster",
                description="fixture",
                positive_sample_count=23,
                negative_sample_count=0,
                backtest_sample_size=17,
                backtest_win_rate=0.88,
                backtest_annual_return=1.0,
                backtest_max_drawdown=-0.3047,
                no_future_data_check_ready=True,
            ),
            policy=_policy(),
        )

        self.assertFalse(result.passed)
        self.assertEqual("keep_current_status", result.recommendation)
        self.assertTrue(any("backtest_sample_size" in item for item in result.failed_conditions))
        self.assertTrue(any("backtest_max_drawdown" in item for item in result.failed_conditions))

    def test_approves_candidate_with_minimum_research_evidence(self) -> None:
        result = review_promotion(
            evidence=PromotionEvidence(
                artifact_id="indicator.ma60",
                artifact_type="technical_indicator",
                current_status="research_only",
                target_status="candidate",
                owner="stock_lobster",
                description="fixture",
                positive_sample_count=2,
            ),
            policy=_policy(),
        )

        self.assertTrue(result.passed)
        self.assertEqual("promote_to_candidate", result.recommendation)


def _policy() -> PromotionPolicy:
    return PromotionPolicy(
        policy_id="fixture",
        thresholds={
            "candidate": PromotionThresholds(min_positive_sample_count=2),
            "approved_production": PromotionThresholds(
                min_positive_sample_count=30,
                min_negative_sample_count=20,
                min_backtest_sample_size=30,
                min_backtest_win_rate=0.55,
                min_backtest_annual_return=0.0,
                max_abs_backtest_drawdown=0.25,
                require_quality_monitoring_ready=True,
                require_missing_data_policy_ready=True,
                require_no_future_data_check_ready=True,
            ),
        },
    )


if __name__ == "__main__":
    unittest.main()
