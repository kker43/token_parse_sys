"""Tests for candidate-pool equal-weight benchmark calculation."""

from __future__ import annotations

import unittest

from stock_lobster.l6_backtest_engine import (
    BacktestEvent,
    EventBacktestPolicy,
    PriceBar,
    run_candidate_pool_equal_weight_benchmark,
)


class CandidatePoolBenchmarkTest(unittest.TestCase):
    def test_runs_equal_weight_benchmark_by_signal_date(self) -> None:
        bars = (
            PriceBar("000001.SZ", "20260101", 10.0, 10.0, 10.0, 10.0),
            PriceBar("000001.SZ", "20260102", 10.0, 11.0, 10.0, 11.0),
            PriceBar("000001.SZ", "20260103", 11.0, 12.0, 11.0, 12.0),
            PriceBar("000002.SZ", "20260101", 20.0, 20.0, 20.0, 20.0),
            PriceBar("000002.SZ", "20260102", 20.0, 20.0, 18.0, 18.0),
            PriceBar("000002.SZ", "20260103", 18.0, 18.0, 16.0, 16.0),
        )
        events = (
            BacktestEvent(asset_id="000001.SZ", signal_date="20260101", event_id="000001.SZ.20260101"),
            BacktestEvent(asset_id="000002.SZ", signal_date="20260101", event_id="000002.SZ.20260101"),
        )

        result = run_candidate_pool_equal_weight_benchmark(
            bars=bars,
            candidate_events=events,
            policy=EventBacktestPolicy(
                strategy_id="strategy.test",
                strategy_version="candidate_v1",
                holding_horizon=2,
                benchmark="CANDIDATE_POOL_EQUAL_WEIGHT",
            ),
        )

        self.assertEqual("candidate_pool_equal_weight_v1", result.benchmark_id)
        self.assertEqual(1, result.signal_date_count)
        self.assertEqual(2, result.candidate_count)
        self.assertEqual(2, result.evaluated_candidate_count)
        self.assertAlmostEqual(0.0, result.signal_date_returns[0].equal_weight_return)
        self.assertEqual([], result.to_mapping()["skipped_events"])


if __name__ == "__main__":
    unittest.main()
