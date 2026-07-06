"""Tests for research sample library coverage gates."""

from __future__ import annotations

import unittest

from stock_lobster.research.sample_library import (
    SampleLibraryGatePolicy,
    evaluate_sample_library,
    extract_sample_events,
    summarize_sample_library,
)


class SampleLibraryTest(unittest.TestCase):
    def test_extracts_and_classifies_sample_events(self) -> None:
        library = _sample_library()

        events = extract_sample_events(library)
        coverage = summarize_sample_library(library)

        self.assertEqual(4, len(events))
        self.assertEqual(3, coverage.dated_event_count)
        self.assertEqual(2, coverage.positive_event_count)
        self.assertEqual(1, coverage.high_value_positive_event_count)
        self.assertEqual(2, coverage.negative_event_count)
        self.assertEqual(1, coverage.hard_negative_event_count)
        self.assertEqual(1, coverage.borderline_negative_event_count)
        self.assertEqual(("evt_missing_date",), coverage.missing_trade_date_events)

    def test_evaluates_gate_gaps_and_next_actions(self) -> None:
        result = evaluate_sample_library(
            _sample_library(),
            policy=SampleLibraryGatePolicy(
                min_total_events=4,
                min_dated_events=4,
                min_positive_events=3,
                min_high_value_positive_events=2,
                min_negative_events=2,
                min_hard_negative_events=1,
                min_borderline_negative_events=1,
            ),
        )

        self.assertFalse(result.passed)
        self.assertIn("dated_events: current=3, required=4, gap=1", result.gaps)
        self.assertIn("positive_events: current=2, required=3, gap=1", result.gaps)
        self.assertIn(
            "high_value_positive_events: current=1, required=2, gap=1",
            result.gaps,
        )
        self.assertTrue(any("精确 daily trade_date" in action for action in result.next_actions))


def _sample_library() -> dict[str, object]:
    return {
        "sample_library_id": "research_samples.test",
        "family_id": "test_family",
        "family_name": "测试形态",
        "samples": [
            {
                "sample_id": "sample_a",
                "asset_id": "000001.SZ",
                "asset_name": "测试一",
                "sample_class": "positive",
                "events": [
                    {
                        "event_id": "evt_high",
                        "trade_date": "2026-01-05",
                        "timeframe": "daily",
                        "event_class": "positive_attention_high_value",
                        "value_tier": "high",
                    },
                    {
                        "event_id": "evt_missing_date",
                        "trade_date": None,
                        "timeframe": "daily",
                        "event_class": "positive_attention_mid_value",
                        "value_tier": "mid",
                    },
                ],
            },
            {
                "sample_id": "sample_b",
                "asset_id": "000002.SZ",
                "asset_name": "测试二",
                "sample_class": "negative",
                "events": [
                    {
                        "event_id": "evt_borderline",
                        "trade_date": "2026-01-06",
                        "timeframe": "daily",
                        "event_class": "borderline_negative_recall",
                        "value_tier": "borderline_negative",
                    },
                    {
                        "event_id": "evt_hard",
                        "trade_date": "2026-01-07",
                        "timeframe": "daily",
                        "event_class": "hard_negative_recall",
                        "value_tier": "hard_negative",
                    },
                ],
            },
        ],
    }


if __name__ == "__main__":
    unittest.main()
