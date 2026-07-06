"""Tests for proposed research annotation queues."""

from __future__ import annotations

import unittest

from stock_lobster.research.annotation_queue import (
    AnnotationSuggestionPolicy,
    build_annotation_queue,
)


class AnnotationQueueTest(unittest.TestCase):
    def test_builds_proposed_queue_from_scan_and_backtest(self) -> None:
        queue = build_annotation_queue(
            scan_payload={
                "breakout_candidates": [
                    _candidate("000001.SZ", "20260101", setup_score=80.0),
                    _candidate("000002.SZ", "20260101", setup_score=62.0),
                    _candidate("000003.SZ", "20260101", setup_score=40.0, daily_quality_pass=False),
                ]
            },
            event_backtest_payload={
                "reports": [
                    {
                        "result": {"holding_horizon": 20},
                        "trades": [
                            {
                                "event_id": "000001.SZ.20260101",
                                "holding_return": 0.22,
                                "max_drawdown": -0.08,
                            },
                            {
                                "event_id": "000002.SZ.20260101",
                                "holding_return": -0.12,
                                "max_drawdown": -0.10,
                            },
                        ],
                    }
                ]
            },
            policy=AnnotationSuggestionPolicy(max_review_items=10),
            holding_horizon=20,
        )

        self.assertEqual(3, len(queue.items))
        self.assertTrue(all(item.label_status == "proposed" for item in queue.items))
        self.assertEqual("positive_attention_high_value", queue.items[0].suggested_event_class)
        self.assertEqual(1, queue.items[0].suggested_review_code)
        self.assertEqual("negative_after_close_recall", queue.items[1].suggested_event_class)
        self.assertEqual(5, queue.items[1].suggested_review_code)
        self.assertEqual("hard_negative_recall", queue.items[2].suggested_event_class)
        self.assertEqual(6, queue.items[2].suggested_review_code)
        self.assertTrue(queue.to_mapping()["requires_human_confirmation"])
        self.assertEqual(
            list(range(1, 9)),
            [option["code"] for option in queue.to_mapping()["review_label_options"]],
        )

    def test_uses_scan_metrics_when_backtest_is_missing(self) -> None:
        queue = build_annotation_queue(
            scan_payload={
                "breakout_candidates": [
                    _candidate(
                        "000001.SZ",
                        "20260101",
                        setup_score=80.0,
                        ma30_deviation_pct=0.20,
                        ma30_hold_ratio_90d=0.85,
                    )
                ]
            }
        )

        self.assertEqual("positive_attention_high_value", queue.items[0].suggested_event_class)
        self.assertEqual(1, queue.items[0].suggested_review_code)
        self.assertEqual("low", queue.items[0].suggestion_confidence)


def _candidate(
    asset_id: str,
    trade_date: str,
    *,
    setup_score: float,
    daily_quality_pass: bool = True,
    ma30_deviation_pct: float = 0.30,
    ma30_hold_ratio_90d: float = 0.75,
) -> dict[str, object]:
    return {
        "asset_id": asset_id,
        "trade_date": trade_date,
        "name": f"测试{asset_id}",
        "setup_score": setup_score,
        "daily_quality_pass": daily_quality_pass,
        "trend_stability_pass": daily_quality_pass,
        "breakout_watch": True,
        "close_new_high_60d_flag": True,
        "ma30_deviation_pct": ma30_deviation_pct,
        "ma30_hold_ratio_90d": ma30_hold_ratio_90d,
        "red_k_ratio_20d": 0.60,
        "long_shadow_ratio_20d": 0.30,
    }


if __name__ == "__main__":
    unittest.main()
