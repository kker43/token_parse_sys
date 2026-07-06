"""Tests for steady uptrend breakout closed-loop workflow."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workflows.jobs.steady_uptrend_breakout_closed_loop import main


class SteadyUptrendBreakoutClosedLoopJobTest(unittest.TestCase):
    def test_runs_closed_loop_from_existing_scan_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            kline_path = tmp_path / "kline.tsv"
            scan_path = tmp_path / "scan.json"
            profile_path = tmp_path / "profile.json"
            output_root = tmp_path / "out"
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
            scan_path.write_text(
                json.dumps(
                    {
                        "candidate_pool": [
                            {"asset_id": "000001.SZ", "trade_date": "20260101"},
                            {"asset_id": "000002.SZ", "trade_date": "20260101"},
                        ],
                        "breakout_candidates": [
                            {"asset_id": "000001.SZ", "trade_date": "20260101"},
                            {"asset_id": "000002.SZ", "trade_date": "20260101"},
                        ],
                        "stage_candidate_pools": {
                            "quality_pool": [
                                {"asset_id": "000001.SZ", "trade_date": "20260101"},
                                {"asset_id": "000002.SZ", "trade_date": "20260101"},
                            ],
                            "trend_pool": [
                                {"asset_id": "000001.SZ", "trade_date": "20260101"},
                                {"asset_id": "000002.SZ", "trade_date": "20260101"},
                            ],
                            "refined_pool": [
                                {"asset_id": "000001.SZ", "trade_date": "20260101"},
                                {"asset_id": "000002.SZ", "trade_date": "20260101"},
                            ],
                            "signal_pool": [
                                {"asset_id": "000001.SZ", "trade_date": "20260101"}
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            profile_path.write_text(
                json.dumps(
                    {
                        "profile_id": "evaluation.test.v1",
                        "strategy_id": "strategy.test",
                        "strategy_version": "candidate_v1",
                        "benchmark": "CANDIDATE_POOL_EQUAL_WEIGHT",
                        "comparison_benchmarks": ["CN_A_EQUAL_WEIGHT", "000698.SH"],
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
                        "holding_horizons": [2],
                        "primary_holding_horizon": 2,
                        "selection_frequency": "daily_after_close",
                        "acceptance_policy": {
                            "min_sample_size": 3,
                            "min_win_rate": 0.55,
                            "max_abs_drawdown": 0.25
                        },
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--evaluation-profile-path",
                    str(profile_path),
                    "--output-root",
                    str(output_root),
                    "--kline-tsv-path",
                    str(kline_path),
                    "--scan-result-path",
                    str(scan_path),
                ]
            )

            summary = json.loads((output_root / "closed_loop_summary.json").read_text(encoding="utf-8"))
            review = json.loads((output_root / "closed_loop_review.json").read_text(encoding="utf-8"))
            benchmark = json.loads((output_root / "candidate_pool_benchmark.json").read_text(encoding="utf-8"))
            self.assertEqual(1, exit_code)
            self.assertEqual(1, summary["review_exit_code"])
            self.assertTrue(Path(summary["output_paths"]["event_backtest"]).exists())
            self.assertEqual(2, benchmark["event_count"])
            self.assertEqual(
                {"quality_pool", "trend_pool", "refined_pool", "signal_pool"},
                set(summary["output_paths"]["stage_benchmarks"]),
            )
            self.assertTrue(Path(summary["output_paths"]["stage_benchmarks"]["signal_pool"]).exists())
            self.assertEqual("keep_current_status_and_expand_samples", review["recommendation"])
            self.assertIn("benchmark_relative_metrics", review)


if __name__ == "__main__":
    unittest.main()
