"""Tests for ordered recall and signal-stage decisions."""

from __future__ import annotations

from types import SimpleNamespace
import unittest

from stock_lobster.research.layered_recall_signal import build_layered_recall_decision


class LayeredRecallSignalTest(unittest.TestCase):
    def test_low_volume_pullback_can_enter_recall(self) -> None:
        metric = _metric(
            volume_ratio_5d_20d=0.84,
            close_to_high_60d_pct=0.0,
            ma30_hold_ratio_30d=1.0,
            ma30_hold_ratio_60d=0.78,
        )

        decision = build_layered_recall_decision(metric)

        self.assertTrue(decision.recall_candidate)
        self.assertIn("pullback_reacceleration", decision.matched_subpools)

    def test_basic_liquidity_failure_blocks_recall_union(self) -> None:
        decision = build_layered_recall_decision(
            _metric(market_cap_liquidity_pass=False)
        )

        self.assertFalse(decision.recall_candidate)
        self.assertEqual((), decision.matched_subpools)


def _metric(**overrides: object) -> SimpleNamespace:
    values = {
        "market_cap_liquidity_pass": True,
        "close_new_high_60d_flag": True,
        "close_to_high_60d_pct": 0.0,
        "ma5": 12.0,
        "ma10": 11.5,
        "ma20": 11.0,
        "ma20_slope_20d": 0.05,
        "ma30_hold_ratio_30d": 0.90,
        "ma30_hold_ratio_60d": 0.80,
        "ma30_hold_ratio_90d": 0.80,
        "return_20d": 0.15,
        "amount_ratio_prev_20d": 1.1,
        "single_bull_bar_return_share_20d": 0.20,
        "impulse_consolidation_days": 8,
        "steady_uptrend": True,
        "volume_ratio_5d_20d": 1.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


if __name__ == "__main__":
    unittest.main()
