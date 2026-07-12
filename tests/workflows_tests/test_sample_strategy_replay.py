import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from stock_lobster.research.layered_recall_signal import (
    LayeredCandidate,
    LayeredRecallDecision,
    SignalStateAssessment,
)
from stock_lobster.research.sample_library import SampleEventRecord
from workflows.jobs.sample_strategy_replay import (
    _read_filtered_kline,
    classify_target,
    evaluate_layered_event,
    ordered_blockers,
)


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
            ordered_blockers(metric, mode="breakout", min_volume_ratio_5d_20d=1.2),
        )

    def test_reports_breakout_volume_only_after_quality_passes(self) -> None:
        metric = {
            "daily_quality_pass": True,
            "steady_uptrend": True,
            "quality_failure_reasons": [],
            "close_new_high_60d_flag": True,
            "volume_ratio_5d_20d": 1.19,
        }

        self.assertEqual(
            ("volume_ratio_5d_20d_below_1.2",),
            ordered_blockers(metric, mode="breakout", min_volume_ratio_5d_20d=1.2),
        )

    def test_reports_missing_5d_20d_volume_ratio(self) -> None:
        metric = {
            "daily_quality_pass": True,
            "steady_uptrend": True,
            "quality_failure_reasons": [],
            "close_new_high_60d_flag": True,
            "volume_ratio_5d_20d": None,
        }

        self.assertEqual(
            ("volume_ratio_5d_20d_missing",),
            ordered_blockers(metric, mode="breakout", min_volume_ratio_5d_20d=1.2),
        )

    def test_kline_reader_skips_blank_lines(self) -> None:
        with TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "kline.tsv"
            path.write_text("000001.SZ\t20260710\t1\t2\t1\t2\t100\n\n", encoding="utf-8")

            bars = _read_filtered_kline(path, {"000001.SZ"})

        self.assertEqual(1, len(bars))

    def test_kline_reader_preserves_optional_volume(self) -> None:
        with TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "kline.tsv"
            path.write_text("000001.SZ\t20260710\t1\t2\t1\t2\t100\t3000\n", encoding="utf-8")

            bar = _read_filtered_kline(path, {"000001.SZ"})[0]

        self.assertEqual(3000.0, bar.volume)

    def test_sample_report_separates_recall_and_signal_results(self) -> None:
        metric = SimpleNamespace(asset_id="000001.SZ", trade_date="20260710")
        candidate = LayeredCandidate(
            decision=LayeredRecallDecision(
                metric=metric,
                matched_subpools=("pullback_reacceleration",),
                recall_candidate=True,
            ),
            state=SignalStateAssessment(
                recall_candidate=True,
                waiting_reasons=("post_impulse_no_followthrough",),
                hard_risk_reasons=(),
                confirmation_reasons=(),
                effective_activity_ratio=0.84,
                signal_eligible=False,
            ),
            score=72.0,
        )

        row = evaluate_layered_event(_event("positive_attention_high_value", "high"), candidate)

        self.assertTrue(row["candidate_v4.recall_candidate"])
        self.assertFalse(row["candidate_v4.signal_eligible"])
        self.assertEqual(
            "post_impulse_no_followthrough",
            row["candidate_v4.waiting_reasons"],
        )


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
