"""Tests for event-driven holding-period backtests."""

from __future__ import annotations

import unittest

from stock_lobster.l6_backtest_engine import (
    BacktestEvent,
    EventBacktestPolicy,
    PriceBar,
    run_event_backtest,
)


class EventBacktestTest(unittest.TestCase):
    def test_runs_holding_period_backtest(self) -> None:
        bars = tuple(
            PriceBar(
                asset_id="000001.SZ",
                trade_date=f"202601{index + 1:02d}",
                open=10 + index,
                high=11 + index,
                low=9 + index,
                close=10.5 + index,
            )
            for index in range(8)
        )
        report = run_event_backtest(
            bars=bars,
            events=(
                BacktestEvent(
                    asset_id="000001.SZ",
                    signal_date="20260101",
                    event_id="evt1",
                ),
            ),
            policy=EventBacktestPolicy(
                strategy_id="strategy.test",
                strategy_version="candidate_v1",
                holding_horizon=3,
            ),
        )

        self.assertEqual(1, report.result.sample_size)
        self.assertEqual("20260102", report.trades[0].entry_date)
        self.assertEqual("20260104", report.trades[0].exit_date)
        self.assertGreater(report.trades[0].holding_return, 0)
        self.assertEqual(1.0, report.result.win_rate)

    def test_skips_events_without_future_bars(self) -> None:
        bars = (
            PriceBar(
                asset_id="000001.SZ",
                trade_date="20260101",
                open=10,
                high=10,
                low=10,
                close=10,
            ),
        )
        report = run_event_backtest(
            bars=bars,
            events=(BacktestEvent(asset_id="000001.SZ", signal_date="20260101", event_id="evt1"),),
            policy=EventBacktestPolicy(
                strategy_id="strategy.test",
                strategy_version="candidate_v1",
                holding_horizon=3,
            ),
        )

        self.assertEqual(0, report.result.sample_size)
        self.assertEqual(("evt1: insufficient future bars",), report.skipped_events)


if __name__ == "__main__":
    unittest.main()
