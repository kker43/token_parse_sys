from types import SimpleNamespace
import unittest

from stock_lobster.research.trend_recall_subpools import classify_recall_subpools


class TrendRecallSubpoolsTest(unittest.TestCase):
    def test_reacceleration_uses_recent_ma30_support_without_volume_hard_gate(self) -> None:
        metric = _metric(
            ma30_hold_ratio_30d=0.96,
            ma30_hold_ratio_60d=0.60,
            ma30_hold_ratio_90d=0.54,
            amount_ratio_prev_20d=1.05,
            close_new_high_60d_flag=True,
        )

        result = classify_recall_subpools(metric)

        self.assertTrue(result["pullback_reacceleration"].matched)
        self.assertNotIn("amount_ratio_below_1_5", result["pullback_reacceleration"].reasons)

    def test_mature_trend_uses_90d_support_as_score_not_universal_gate(self) -> None:
        metric = _metric(ma30_hold_ratio_90d=0.82, amount_ratio_prev_20d=0.95)

        result = classify_recall_subpools(metric)

        self.assertTrue(result["trend_following"].matched)
        self.assertGreater(result["trend_following"].score_adjustment, 0)

    def test_early_reversal_does_not_require_90d_ma30_support(self) -> None:
        metric = _metric(
            ma30_hold_ratio_30d=0.60,
            ma30_hold_ratio_60d=0.40,
            ma30_hold_ratio_90d=0.20,
            ma20_slope_20d=0.08,
            return_20d=0.12,
            close_new_high_60d_flag=False,
        )

        result = classify_recall_subpools(metric)

        self.assertTrue(result["early_reversal"].matched)

    def test_basic_liquidity_blocks_every_subpool(self) -> None:
        result = classify_recall_subpools(_metric(market_cap_liquidity_pass=False))

        self.assertTrue(all(not match.matched for match in result.values()))
        self.assertTrue(all("basic_liquidity_failed" in match.reasons for match in result.values()))


def _metric(**overrides: object) -> SimpleNamespace:
    values = {
        "market_cap_liquidity_pass": True,
        "close_new_high_60d_flag": True,
        "close_to_high_60d_pct": 0.0,
        "ma5": 12.0,
        "ma10": 11.5,
        "ma20": 11.0,
        "ma30": 10.5,
        "close": 12.0,
        "ma20_slope_20d": 0.05,
        "ma30_hold_ratio_30d": 0.90,
        "ma30_hold_ratio_60d": 0.80,
        "ma30_hold_ratio_90d": 0.80,
        "return_20d": 0.15,
        "amount_ratio_prev_20d": 1.1,
        "red_k_ratio_20d": 0.60,
        "large_bearish_body_ratio_20d": 0.05,
        "single_bull_bar_return_share_20d": 0.20,
        "impulse_consolidation_days": 8,
        "steady_uptrend": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


if __name__ == "__main__":
    unittest.main()
