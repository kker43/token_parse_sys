"""Tests for ordered recall and signal-stage decisions."""

from __future__ import annotations

from types import SimpleNamespace
import unittest

from stock_lobster.research.layered_recall_signal import (
    LayeredRecallDecision,
    assess_signal_state,
    build_layered_recall_decision,
)


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

    def test_post_impulse_stall_keeps_recall_but_waits(self) -> None:
        state = assess_signal_state(
            _recall(
                _metric(
                    post_impulse_followthrough_return=-0.0037,
                    volume_decay_after_impulse=0.58,
                )
            )
        )

        self.assertTrue(state.recall_candidate)
        self.assertFalse(state.signal_eligible)
        self.assertIn("post_impulse_no_followthrough", state.waiting_reasons)

    def test_valid_high_volume_breakout_is_not_rejected(self) -> None:
        state = assess_signal_state(
            _recall(
                _metric(
                    volume_ratio_5d_20d=1.51,
                    post_impulse_followthrough_return=None,
                    high_volume_bearish_close=False,
                )
            )
        )

        self.assertEqual((), state.hard_risk_reasons)
        self.assertTrue(state.signal_eligible)

    def test_missing_volume_confirmation_keeps_recall_but_blocks_signal(self) -> None:
        state = assess_signal_state(
            _recall(
                _metric(
                    volume_ratio_5d_20d=None,
                    turnover_ratio_5d_20d=None,
                )
            )
        )

        self.assertTrue(state.recall_candidate)
        self.assertFalse(state.signal_eligible)
        self.assertIn("insufficient_volume_confirmation", state.confirmation_reasons)

    def test_adj_factor_change_uses_turnover_confirmation(self) -> None:
        state = assess_signal_state(
            _recall(
                _metric(
                    adj_factor_changed_20d=True,
                    volume_ratio_5d_20d=1.31,
                    turnover_ratio_5d_20d=1.20,
                )
            )
        )

        self.assertEqual(1.20, state.effective_activity_ratio)
        self.assertTrue(state.signal_eligible)

    def test_noisy_ma30_breakdown_rebound_is_hard_risk(self) -> None:
        state = assess_signal_state(
            _recall(
                _metric(
                    long_shadow_ratio_20d=0.57,
                    large_bearish_body_ratio_20d=0.30,
                    ma30_hold_ratio_30d=0.83,
                    ma30_deviation_pct=0.13,
                )
            )
        )

        self.assertFalse(state.signal_eligible)
        self.assertIn("noisy_ma30_breakdown_rebound", state.hard_risk_reasons)


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
        "turnover_ratio_5d_20d": 1.0,
        "adj_factor_changed_20d": False,
        "long_shadow_ratio_20d": 0.40,
        "large_bearish_body_ratio_20d": 0.10,
        "ma30_deviation_pct": 0.08,
        "ma5_10_20_30_convergence_pct": 0.10,
        "post_impulse_followthrough_return": 0.05,
        "volume_decay_after_impulse": 0.80,
        "high_volume_bearish_close": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _recall(metric: SimpleNamespace) -> LayeredRecallDecision:
    return LayeredRecallDecision(
        metric=metric,
        matched_subpools=("trend_following",),
        recall_candidate=True,
    )


if __name__ == "__main__":
    unittest.main()
