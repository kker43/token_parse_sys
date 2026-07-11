import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from stock_lobster.research.sample_library import SampleEventRecord
from workflows.jobs.sample_strategy_replay import _read_filtered_kline, classify_target, ordered_blockers


class SampleStrategyReplayTest(unittest.TestCase):
    def test_classifies_approved_sample_targets(self) -> None:
        positive = _event("positive_attention_high_value", "high")
        hard_negative = _event("hard_negative_recall", "hard_negative")
        waiting = _event("borderline_negative_recall", "borderline_negative")
        excluded = _event("weak_or_excluded_attention", "low_or_exclude")

        self.assertEqual("positive_recall", classify_target(positive))
        self.assertEqual("hard_negative_reject", classify_target(hard_negative))
        self.assertEqual("wait_or_observe_only", classify_target(waiting))
        self.assertEqual("exclude_or_low", classify_target(excluded))

    def test_orders_quality_before_trigger_blockers(self) -> None:
        metric = {
            "daily_quality_pass": False,
            "steady_uptrend": False,
            "quality_failure_reasons": ["avg_amount_20d_below_threshold"],
            "close_new_high_60d_flag": True,
            "amount_ratio_20d": 2.0,
        }

        self.assertEqual(
            ("avg_amount_20d_below_threshold",),
            ordered_blockers(metric, mode="breakout", min_amount_ratio_20d=1.5),
        )

    def test_reports_breakout_volume_only_after_quality_passes(self) -> None:
        metric = {
            "daily_quality_pass": True,
            "steady_uptrend": True,
            "quality_failure_reasons": [],
            "close_new_high_60d_flag": True,
            "amount_ratio_20d": 1.2,
        }

        self.assertEqual(
            ("amount_ratio_below_1.5",),
            ordered_blockers(metric, mode="breakout", min_amount_ratio_20d=1.5),
        )

    def test_kline_reader_skips_blank_lines(self) -> None:
        with TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "kline.tsv"
            path.write_text("000001.SZ\t20260710\t1\t2\t1\t2\t100\n\n", encoding="utf-8")

            bars = _read_filtered_kline(path, {"000001.SZ"})

        self.assertEqual(1, len(bars))


def _event(event_class: str, value_tier: str) -> SampleEventRecord:
    return SampleEventRecord(
        sample_id="sample",
        asset_id="000001.SZ",
        asset_name="样本",
        sample_class="sample_class",
        event_id="event",
        trade_date="20260710",
        timeframe="daily",
        event_class=event_class,
        value_tier=value_tier,
    )


if __name__ == "__main__":
    unittest.main()
