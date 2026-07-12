"""Tests for steady uptrend v3 research scan job."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workflows.jobs.steady_uptrend_v3_research_scan import main


class SteadyUptrendV3ResearchScanJobTest(unittest.TestCase):
    def test_outputs_v3_observation_signal_and_rejection_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            kline_path = tmp_path / "kline.tsv"
            config_path = tmp_path / "v3_config.json"
            output_path = tmp_path / "scan.json"
            kline_path.write_text(
                "\n".join(
                    _breakout_rows("000001.SZ")
                    + _pre_breakout_rows("000002.SZ")
                    + _hot_amount_rows("000003.SZ")
                ),
                encoding="utf-8",
            )
            config_path.write_text(
                json.dumps(
                    {
                        "strategy_id": "strategy.steady_uptrend_pre_breakout_watch",
                        "version": "candidate_v3",
                        "candidate_scan_policy": {
                            "start_date": "20260001",
                            "require_context_strength": False,
                            "require_weekly_uptrend": False,
                            "min_red_k_ratio_20d": 0.45,
                        },
                        "v3_filter_policy": {
                            "require_market_temperature": True,
                            "min_market_temperature_sample_size": 1,
                            "max_market_breadth_ma20": 1.0,
                            "max_market_avg_return_20d": 1.0,
                            "max_market_avg_amount_ratio": 10.0,
                            "max_amount_ratio_20d": 2.5,
                            "max_single_bull_bar_return_share_20d": 0.9,
                            "top_n_per_date": 20,
                            "cooldown_trade_days": 0,
                        },
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--kline-tsv-path",
                    str(kline_path),
                    "--strategy-config-path",
                    str(config_path),
                    "--output-path",
                    str(output_path),
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(0, exit_code)
            self.assertEqual("steady_uptrend_v3_research_scan", payload["scanner"])
            self.assertEqual("candidate_v3", payload["strategy_version"])
            self.assertEqual(3, payload["candidate_pool_count"])
            self.assertEqual(1, payload["observation_candidate_count"])
            self.assertEqual(1, payload["signal_candidate_count"])
            self.assertEqual(1, payload["breakout_candidate_count"])
            self.assertEqual(["000002.SZ"], [item["asset_id"] for item in payload["observation_candidates"]])
            self.assertEqual(["000001.SZ"], [item["asset_id"] for item in payload["breakout_candidates"]])
            self.assertIn("amount_ratio_overheated", payload["v3_rejection_reason_counts"])
            self.assertEqual(["000003.SZ"], [item["asset_id"] for item in payload["v3_rejected_candidates"]])
            self.assertTrue(payload["market_temperature_summary"]["date_count"] > 0)


def _breakout_rows(asset_id: str) -> list[str]:
    rows: list[str] = []
    price = 10.0
    for index in range(140):
        if index > 20:
            price += 0.2
        amount = 100.0
        if index == 139:
            price += 5.0
            amount = 220.0
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
            close_price = price - 1.2
        rows.append(_row(asset_id, index, close_price, close_price, close_price, close_price, 120.0))
    return rows


def _hot_amount_rows(asset_id: str) -> list[str]:
    rows = _breakout_rows(asset_id)
    parts = rows[-1].split("\t")
    parts[-1] = "1000.0"
    rows[-1] = "\t".join(parts)
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
