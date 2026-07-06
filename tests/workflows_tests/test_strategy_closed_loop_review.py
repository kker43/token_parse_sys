"""Tests for strategy closed-loop review job."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workflows.jobs.strategy_closed_loop_review import main


class StrategyClosedLoopReviewJobTest(unittest.TestCase):
    def test_writes_failed_closed_loop_review_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            profile_path = tmp_path / "profile.json"
            backtest_path = tmp_path / "backtest.json"
            benchmark_path = tmp_path / "benchmark.json"
            output_path = tmp_path / "closed_loop.json"
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
                            "min_win_rate": 0.55,
                            "return_metric_name": "annual_return",
                            "min_return_metric": 0.0,
                            "drawdown_metric_name": "max_drawdown",
                            "max_abs_drawdown": 0.25
                        },
                        "lifecycle_gates": {
                            "test_tracking": {
                                "min_sample_size": 20,
                                "min_win_rate": 0.52,
                                "min_excess_avg_return": 0.0,
                                "drawdown_metric_name": "max_drawdown",
                                "max_abs_drawdown": 0.30
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            backtest_path.write_text(
                json.dumps(
                    {
                        "reports": [
                            {
                                "result": {
                                    "strategy_id": "strategy.test",
                                    "strategy_version": "candidate_v1",
                                    "backtest_period": ["20260101", "20260131"],
                                    "benchmark": "CANDIDATE_POOL_EQUAL_WEIGHT",
                                    "holding_horizon": 10,
                                    "return_metrics": {"annual_return": 0.20},
                                    "drawdown_metrics": {"max_drawdown": -0.30},
                                    "win_rate": 0.60,
                                    "sample_size": 17,
                                    "failure_cases": []
                                }
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            benchmark_path.write_text(
                json.dumps(
                    {
                        "benchmark_results": [
                            {
                                "benchmark_id": "candidate_pool_equal_weight_v1",
                                "holding_horizon": 10,
                                "benchmark_period": ["20260101", "20260131"],
                                "return_metrics": {
                                    "annual_return": 0.10,
                                    "avg_signal_date_return": 0.04
                                },
                                "drawdown_metrics": {
                                    "max_signal_date_drawdown": -0.20
                                },
                                "signal_date_count": 1,
                                "candidate_count": 50,
                                "evaluated_candidate_count": 49,
                                "skipped_events": ["000003.SZ.20260101: missing bars"]
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--evaluation-profile-path",
                    str(profile_path),
                    "--backtest-report-path",
                    str(backtest_path),
                    "--benchmark-report-path",
                    str(benchmark_path),
                    "--output-path",
                    str(output_path),
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(1, exit_code)
            self.assertFalse(payload["primary_gate_passed"])
            self.assertEqual(
                "candidate_pool_equal_weight_v1",
                payload["promotion_evidence"]["benchmark_definition"]["benchmark_id"],
            )
            self.assertEqual("test_tracking", payload["target_status"])
            self.assertEqual(20, payload["acceptance_policy"]["min_sample_size"])
            self.assertAlmostEqual(0.10, payload["benchmark_relative_metrics"]["excess_annual_return"])
            self.assertEqual(
                payload["benchmark_relative_metrics"],
                payload["promotion_evidence"]["benchmark_relative_metrics"],
            )
            self.assertEqual("keep_current_status_and_expand_samples", payload["recommendation"])
            self.assertEqual(
                "pending_user_approval",
                payload["proposed_observation_record"]["approval_status"],
            )
            self.assertIn(
                "CN_A_EQUAL_WEIGHT",
                payload["proposed_observation_record"]["comparison_benchmarks"],
            )
            self.assertIn(
                "000698.SH",
                payload["proposed_observation_record"]["comparison_benchmarks"],
            )
            self.assertIn(
                "sample_size 17 < 20",
                payload["proposed_observation_record"]["promotion_blockers"],
            )

    def test_uses_stricter_active_production_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            profile_path = tmp_path / "profile.json"
            backtest_path = tmp_path / "backtest.json"
            benchmark_path = tmp_path / "benchmark.json"
            output_path = tmp_path / "closed_loop.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "profile_id": "evaluation.test.v1",
                        "strategy_id": "strategy.test",
                        "strategy_version": "candidate_v1",
                        "benchmark": "CANDIDATE_POOL_EQUAL_WEIGHT",
                        "holding_horizons": [10],
                        "primary_holding_horizon": 10,
                        "selection_frequency": "daily_after_close",
                        "acceptance_policy": {"min_sample_size": 20},
                        "lifecycle_gates": {
                            "active_production": {
                                "min_sample_size": 50,
                                "min_tracking_days": 20,
                                "min_win_rate": 0.55,
                                "min_avg_return": 0.0,
                                "min_median_return": 0.0,
                                "min_excess_avg_return": 0.0,
                                "max_abs_drawdown": 0.25,
                                "require_failure_cases_reviewed": True,
                                "require_user_approval": True
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            backtest_path.write_text(
                json.dumps(
                    {
                        "reports": [
                            {
                                "result": {
                                    "strategy_id": "strategy.test",
                                    "strategy_version": "candidate_v1",
                                    "backtest_period": ["20260101", "20260131"],
                                    "benchmark": "CANDIDATE_POOL_EQUAL_WEIGHT",
                                    "holding_horizon": 10,
                                    "return_metrics": {
                                        "annual_return": 0.20,
                                        "avg_return": 0.05,
                                        "median_return": 0.02
                                    },
                                    "drawdown_metrics": {"max_drawdown": -0.10},
                                    "win_rate": 0.60,
                                    "sample_size": 30,
                                    "failure_cases": ["000001.SZ.20260101"]
                                }
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            benchmark_path.write_text(
                json.dumps(
                    {
                        "benchmark_results": [
                            {
                                "benchmark_id": "candidate_pool_equal_weight_v1",
                                "holding_horizon": 10,
                                "return_metrics": {
                                    "annual_return": 0.10,
                                    "avg_signal_date_return": 0.01
                                },
                                "drawdown_metrics": {"max_signal_date_drawdown": -0.08}
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--evaluation-profile-path",
                    str(profile_path),
                    "--backtest-report-path",
                    str(backtest_path),
                    "--benchmark-report-path",
                    str(benchmark_path),
                    "--output-path",
                    str(output_path),
                    "--target-status",
                    "active_production",
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(1, exit_code)
            self.assertEqual("active_production", payload["target_status"])
            self.assertEqual(50, payload["acceptance_policy"]["min_sample_size"])
            self.assertIn("sample_size 30 < 50", payload["gate_reviews"][0]["failed_conditions"])


if __name__ == "__main__":
    unittest.main()
