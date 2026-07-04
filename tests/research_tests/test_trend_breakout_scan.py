"""Tests for the steady uptrend breakout scanner."""

from __future__ import annotations

import unittest

from stock_lobster.research import (
    KlineBar,
    TrendBreakoutScanPolicy,
    scan_trend_breakouts,
    summarize_breakout_scan,
)


class TrendBreakoutScanTest(unittest.TestCase):
    def test_detects_breakout_watch_candidate(self) -> None:
        bars: list[KlineBar] = []
        price = 10.0
        for index in range(140):
            if index > 20:
                price += 0.2
            amount = 100.0
            if index == 139:
                price += 5.0
                amount = 300.0
            bars.append(
                KlineBar(
                    asset_id="000001.SZ",
                    trade_date=f"2026{index + 1:04d}",
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    amount=amount,
                )
            )

        metrics = scan_trend_breakouts(
            bars,
            TrendBreakoutScanPolicy(start_date="20260001"),
        )
        candidates = [metric for metric in metrics if metric.breakout_watch]

        self.assertTrue(candidates)
        self.assertEqual("000001.SZ", candidates[-1].asset_id)
        self.assertGreaterEqual(candidates[-1].amount_ratio_20d, 1.5)
        self.assertEqual(1, summarize_breakout_scan(candidates)["000001.SZ"]["breakout_watch_count"])


if __name__ == "__main__":
    unittest.main()
