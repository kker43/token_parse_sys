"""Tests for steady uptrend breakout research scan job."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workflows.jobs.steady_uptrend_breakout_research_scan import main


class SteadyUptrendBreakoutResearchScanJobTest(unittest.TestCase):
    def test_outputs_recall_pool_separately_from_final_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            kline_path = tmp_path / "kline.tsv"
            output_path = tmp_path / "scan.json"
            rows = _breakout_rows("000001.SZ") + _pre_breakout_rows("000002.SZ")
            kline_path.write_text("\n".join(rows), encoding="utf-8")

            exit_code = main(
                [
                    "--kline-tsv-path",
                    str(kline_path),
                    "--output-path",
                    str(output_path),
                    "--start-date",
                    "20260001",
                    "--candidate-mode",
                    "breakout",
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(0, exit_code)
            self.assertEqual("steady_uptrend_breakout.recall_pool.v1", payload["candidate_pool_policy"]["pool_id"])
            self.assertEqual(2, payload["candidate_pool_count"])
            self.assertEqual(1, payload["breakout_candidate_count"])
            self.assertEqual(2, payload["stage_candidate_pool_counts"]["refined_pool"])
            self.assertEqual(1, payload["stage_candidate_pool_counts"]["signal_pool"])
            self.assertEqual(
                {"000001.SZ", "000002.SZ"},
                {item["asset_id"] for item in payload["candidate_pool"]},
            )
            self.assertEqual(
                {"000001.SZ", "000002.SZ"},
                {item["asset_id"] for item in payload["stage_candidate_pools"]["refined_pool"]},
            )
            self.assertEqual(["000001.SZ"], [item["asset_id"] for item in payload["breakout_candidates"]])

    def test_exposes_candidate_v2_weak_shape_filter_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            kline_path = tmp_path / "kline.tsv"
            output_path = tmp_path / "scan.json"
            kline_path.write_text("\n".join(_weak_shape_rows("000011.SZ")), encoding="utf-8")

            exit_code = main(
                [
                    "--kline-tsv-path",
                    str(kline_path),
                    "--output-path",
                    str(output_path),
                    "--start-date",
                    "20260001",
                    "--candidate-mode",
                    "breakout",
                    "--min-red-k-ratio-20d",
                    "0.35",
                    "--enable-weak-shape-filter",
                    "--max-large-bearish-body-ratio-20d",
                    "0.20",
                    "--max-consecutive-green-k-20d",
                    "4",
                    "--max-single-bull-bar-return-share-20d",
                    "0.55",
                    "--min-impulse-consolidation-days",
                    "5",
                    "--min-ma5-10-20-30-convergence-pct",
                    "0.08",
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(0, exit_code)
            self.assertTrue(payload["policy"]["enable_weak_shape_filter"])
            self.assertEqual(0, payload["candidate_pool_count"])
            self.assertEqual(0, payload["breakout_candidate_count"])


def _breakout_rows(asset_id: str) -> list[str]:
    rows: list[str] = []
    price = 10.0
    for index in range(140):
        if index > 20:
            price += 0.2
        amount = 100.0
        if index == 139:
            price += 5.0
            amount = 300.0
        rows.append(_row(asset_id, index, price, price, price, price, amount))
    return rows


def _pre_breakout_rows(asset_id: str) -> list[str]:
    rows: list[str] = []
    price = 10.0
    for index in range(140):
        if index > 20:
            price += 0.2
        close_price = price
        if index == 139:
            close_price = price - 0.45
        rows.append(_row(asset_id, index, close_price, close_price, close_price, close_price, 120.0))
    return rows


def _weak_shape_rows(asset_id: str) -> list[str]:
    rows: list[str] = []
    close_price = 30.0
    for index in range(140):
        amount = 120.0
        if index < 120:
            close_price += 0.05
            open_price = close_price - 0.02
        elif index < 134:
            close_price += 0.02
            open_price = close_price + 0.95 if index % 2 == 0 else close_price - 0.04
        elif index < 139:
            close_price += 0.03
            open_price = close_price + 0.12
        else:
            previous_close = close_price
            close_price = previous_close + 6.0
            open_price = previous_close + 0.25
            amount = 300.0
        rows.append(
            _row(
                asset_id,
                index,
                open_price,
                max(open_price, close_price) + 0.05,
                min(open_price, close_price) - 0.05,
                close_price,
                amount,
            )
        )
    return rows


def _row(
    asset_id: str,
    index: int,
    open_value: float,
    high: float,
    low: float,
    close: float,
    amount: float,
) -> str:
    return f"{asset_id}\t2026{index + 1:04d}\t{open_value}\t{high}\t{low}\t{close}\t{amount}"


if __name__ == "__main__":
    unittest.main()
