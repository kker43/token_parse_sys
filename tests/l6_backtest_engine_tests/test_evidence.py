"""Tests for L6 backtest evidence gates."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from stock_lobster.l6_backtest_engine import (
    BacktestAcceptancePolicy,
    BacktestResult,
    build_promotion_evidence_mapping,
    load_evaluation_profile,
    review_backtest_result,
)


class BacktestEvidenceTest(unittest.TestCase):
    def test_reviews_backtest_result_against_acceptance_policy(self) -> None:
        result = BacktestResult(
            strategy_id="strategy.test",
            strategy_version="candidate_v1",
            backtest_period=("20260101", "20260131"),
            benchmark="000905.SH",
            holding_horizon=20,
            return_metrics={"annual_return": 0.12},
            drawdown_metrics={"max_drawdown": -0.31},
            win_rate=0.60,
            sample_size=20,
        )

        review = review_backtest_result(
            result=result,
            acceptance_policy=BacktestAcceptancePolicy(
                min_sample_size=30,
                min_win_rate=0.55,
                min_return_metric=0.0,
                max_abs_drawdown=0.25,
            ),
        )

        self.assertFalse(review.passed)
        self.assertIn("sample_size 20 < 30", review.failed_conditions)
        self.assertIn("abs(max_drawdown) 0.3100 > 0.2500", review.failed_conditions)

    def test_loads_profile_and_builds_promotion_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_path = Path(tmpdir) / "profile.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "profile_id": "evaluation.test.v1",
                        "strategy_id": "strategy.test",
                        "strategy_version": "candidate_v1",
                        "benchmark": "CANDIDATE_POOL_EQUAL_WEIGHT",
                        "comparison_benchmarks": [
                            "CN_A_EQUAL_WEIGHT",
                            "000905.SH",
                            "000852.SH",
                            "000300.SH",
                            "000698.SH",
                        ],
                        "benchmark_definition": {
                            "benchmark_id": "candidate_pool_equal_weight_v1",
                            "universe": "same CandidatePoolPolicy candidates",
                            "weighting": "equal weight per signal_date",
                            "rebalance": "independent per signal_date",
                            "entry_rule": "T+1 open",
                            "exit_rule": "holding_horizon close",
                            "missing_price_policy": "skip and record",
                            "suspended_or_untradable_entry_policy": "skip and record",
                            "limit_up_entry_policy": "not simulated in v1",
                        },
                        "holding_horizons": [5, 10, 20],
                        "primary_holding_horizon": 10,
                        "selection_frequency": "daily_after_close",
                        "acceptance_policy": {
                            "min_sample_size": 30,
                            "max_abs_drawdown": 0.25
                        },
                        "lifecycle_gates": {
                            "test_tracking": {
                                "min_sample_size": 20,
                                "min_win_rate": 0.52,
                                "min_excess_avg_return": 0.0,
                                "max_abs_drawdown": 0.30
                            },
                            "active_production": {
                                "min_sample_size": 50,
                                "min_win_rate": 0.55,
                                "min_excess_avg_return": 0.0,
                                "max_abs_drawdown": 0.25,
                                "require_failure_cases_reviewed": True
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            profile = load_evaluation_profile(profile_path)
            result = BacktestResult(
                strategy_id="strategy.test",
                strategy_version="candidate_v1",
                backtest_period=("20260101", "20260131"),
                benchmark="CANDIDATE_POOL_EQUAL_WEIGHT",
                holding_horizon=10,
                return_metrics={"annual_return": 0.12},
                drawdown_metrics={"max_drawdown": -0.10},
                win_rate=0.60,
                sample_size=30,
                failure_cases=("000001.SZ.20260101",),
            )
            evidence = build_promotion_evidence_mapping(
                result=result,
                profile=profile,
                target_status="test_tracking",
                owner="stock_lobster",
                description="fixture",
            )

            self.assertEqual(10, profile.primary_holding_horizon)
            self.assertIsNotNone(profile.benchmark_definition)
            self.assertEqual("candidate_pool_equal_weight_v1", profile.benchmark_definition.benchmark_id)
            self.assertEqual(20, profile.acceptance_policy_for("test_tracking").min_sample_size)
            self.assertEqual(50, profile.acceptance_policy_for("active_production").min_sample_size)
            self.assertIn("CN_A_EQUAL_WEIGHT", profile.comparison_benchmarks)
            self.assertIn("000698.SH", profile.comparison_benchmarks)
            self.assertEqual("test_tracking", evidence["target_status"])
            self.assertEqual("CANDIDATE_POOL_EQUAL_WEIGHT", evidence["primary_benchmark"])
            self.assertEqual(
                "candidate_pool_equal_weight_v1",
                evidence["benchmark_definition"]["benchmark_id"],
            )
            self.assertEqual(1, evidence["failure_case_count"])


if __name__ == "__main__":
    unittest.main()
