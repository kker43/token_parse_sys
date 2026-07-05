"""Tests for reusable rolling technical indicator calculations."""

from __future__ import annotations

import unittest

from stock_lobster.technical_indicators import (
    moving_average_at,
    relative_slope_at,
    rolling_max_drawdown_at,
)


class RollingIndicatorTest(unittest.TestCase):
    def test_rolling_max_drawdown_reuses_same_window_semantics(self) -> None:
        values = [10.0, 12.0, 11.0, 15.0, 9.0, 10.0]

        drawdown = rolling_max_drawdown_at(values, window=5, index=5)

        self.assertAlmostEqual(-0.4, drawdown)

    def test_moving_average_and_relative_slope(self) -> None:
        values = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0]

        self.assertAlmostEqual(18.0, moving_average_at(values, window=3, index=5))
        self.assertAlmostEqual(18.0 / 14.0 - 1, relative_slope_at(values, window=3, lookback=2, index=5))


if __name__ == "__main__":
    unittest.main()
