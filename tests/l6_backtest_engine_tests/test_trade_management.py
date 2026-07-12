"""Tests for short-horizon trade management backtests."""

from __future__ import annotations

import unittest

from stock_lobster.l6_backtest_engine import BacktestEvent, PriceBar
from stock_lobster.l6_backtest_engine.trade_management import (
    TradeManagementPolicy,
    run_trade_management_backtest,
)


class TradeManagementBacktestTest(unittest.TestCase):
    def test_stop_loss_exits_at_threshold_before_holding_period_end(self) -> None:
        bars = (
            PriceBar("000001.SZ", "20260101", open=10.0, high=10.5, low=9.8, close=10.0),
            PriceBar("000001.SZ", "20260102", open=10.0, high=10.2, low=9.4, close=9.8),
            PriceBar("000001.SZ", "20260103", open=9.7, high=9.9, low=8.9, close=9.2),
            PriceBar("000001.SZ", "20260104", open=9.1, high=9.3, low=8.8, close=9.0),
        )

        report = run_trade_management_backtest(
            bars=bars,
            events=(BacktestEvent("000001.SZ", "20260101", "evt1"),),
            policy=TradeManagementPolicy(
                strategy_id="strategy.test",
                strategy_version="candidate",
                max_holding_days=3,
                stop_loss_pct=-0.10,
            ),
        )

        self.assertEqual(1, report.result.sample_size)
        self.assertEqual("stop_loss", report.trades[0].exit_reason)
        self.assertEqual("20260103", report.trades[0].exit_date)
        self.assertAlmostEqual(9.0, report.trades[0].exit_price)
        self.assertAlmostEqual(-0.10, report.trades[0].holding_return)

    def test_entry_gap_filter_skips_high_open_entry(self) -> None:
        bars = (
            PriceBar("000001.SZ", "20260101", open=10.0, high=10.2, low=9.8, close=10.0),
            PriceBar("000001.SZ", "20260102", open=10.8, high=11.0, low=10.5, close=10.9),
            PriceBar("000001.SZ", "20260103", open=10.9, high=11.2, low=10.7, close=11.0),
        )

        report = run_trade_management_backtest(
            bars=bars,
            events=(BacktestEvent("000001.SZ", "20260101", "evt1"),),
            policy=TradeManagementPolicy(
                strategy_id="strategy.test",
                strategy_version="candidate",
                max_holding_days=2,
                max_entry_gap_up_pct=0.05,
            ),
        )

        self.assertEqual(0, report.result.sample_size)
        self.assertEqual(("evt1: entry_gap_up 0.0800 > 0.0500",), report.skipped_events)


if __name__ == "__main__":
    unittest.main()
