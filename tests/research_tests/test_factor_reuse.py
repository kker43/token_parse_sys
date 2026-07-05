"""Tests for research factor reuse audit helpers."""

from __future__ import annotations

import unittest

from stock_lobster.research.factor_reuse import FactorRequirement, audit_factor_reuse


class FactorReuseAuditTest(unittest.TestCase):
    def test_reuses_exact_indicator_when_available(self) -> None:
        decisions = audit_factor_reuse(
            (
                FactorRequirement(
                    name="weekly_max_drawdown_26w",
                    meaning="26-week rolling max drawdown",
                    timeframe="weekly",
                    window=26,
                    reuse_family="rolling_max_drawdown(close, window)",
                ),
            ),
            (
                {
                    "name": "weekly_max_drawdown_26w",
                    "reuse_family": "rolling_max_drawdown(close, window)",
                },
            ),
        )

        self.assertEqual("reuse_existing", decisions[0].decision)
        self.assertEqual("weekly_max_drawdown_26w", decisions[0].matched_indicator)

    def test_reuses_same_family_for_window_variant(self) -> None:
        decisions = audit_factor_reuse(
            (
                FactorRequirement(
                    name="weekly_max_drawdown_13w",
                    meaning="13-week rolling max drawdown",
                    timeframe="weekly",
                    window=13,
                    reuse_family="rolling_max_drawdown(close, window)",
                ),
            ),
            (
                {
                    "name": "max_drawdown_60d",
                    "reuse_family": "rolling_max_drawdown(close, window)",
                },
                {
                    "name": "max_drawdown_120d",
                    "reuse_family": "rolling_max_drawdown(close, window)",
                },
            ),
        )

        self.assertEqual("reuse_with_window_param", decisions[0].decision)
        self.assertEqual(("max_drawdown_60d", "max_drawdown_120d"), decisions[0].similar_indicators)


if __name__ == "__main__":
    unittest.main()
