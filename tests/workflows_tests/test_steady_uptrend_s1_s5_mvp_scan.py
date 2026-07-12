"""Contract tests for the steady-uptrend S1-S5 MVP scan job."""

from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
import tempfile
import unittest

from workflows.jobs.steady_uptrend_s1_s5_mvp_scan import build_parser, main


class SteadyUptrendS1S5MvpScanTest(unittest.TestCase):
    def test_parser_requires_all_fact_inputs_and_run_metadata(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args([])

    def test_scan_writes_stage_audit_json_and_grouped_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            daily_path = root / "daily.tsv"
            weekly_path = root / "weekly.tsv"
            context_path = root / "context.tsv"
            config_path = root / "strategy.json"
            output_path = root / "result.json"
            markdown_path = root / "result.md"
            signal_date = _write_inputs(daily_path, weekly_path, context_path)
            config_path.write_text(
                json.dumps(
                    {
                        "strategy_id": "steady_uptrend_s1_s5_mvp_candidate_v1",
                        "version": "candidate_v1",
                        "status": "test_tracking",
                        "policy": {},
                        "data_dependency_versions": {
                            "daily_kline": "fixture-daily-v1",
                            "weekly_kline": "fixture-weekly-v1",
                            "stock_context": "fixture-context-v1",
                        },
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--kline-tsv-path",
                    str(daily_path),
                    "--weekly-kline-tsv-path",
                    str(weekly_path),
                    "--stock-context-tsv-path",
                    str(context_path),
                    "--strategy-config-path",
                    str(config_path),
                    "--signal-date",
                    signal_date,
                    "--run-id",
                    "fixture-run",
                    "--output-path",
                    str(output_path),
                    "--markdown-output-path",
                    str(markdown_path),
                ]
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(0, exit_code)
            self.assertEqual("steady_uptrend_s1_s5_mvp_candidate_v1", payload["strategy_id"])
            self.assertEqual("test_tracking", payload["status"])
            self.assertEqual(2, payload["stage_counts"]["s1_quality_filter"]["passed"])
            self.assertEqual(2, payload["stage_counts"]["s4_stability_refinement"]["passed"])
            self.assertEqual(1, payload["stage_counts"]["s5_entry_selection"]["passed"])
            self.assertEqual(1, payload["stage_counts"]["s5_entry_selection"]["rejected"])
            self.assertEqual(1, payload["blocker_counts"]["context_strength_unavailable"])
            self.assertEqual(["000001.SZ"], [item["asset_id"] for item in payload["candidates"]])
            self.assertEqual(payload["markdown"], markdown_path.read_text(encoding="utf-8"))
            self.assertIn("电子元件：", payload["markdown"])
            self.assertIn("强势样本（偏离", payload["markdown"])
            self.assertNotIn("弱上下文", payload["markdown"])


def _write_inputs(daily_path: Path, weekly_path: Path, context_path: Path) -> str:
    assets = ("000001.SZ", "000002.SZ")
    daily_rows: list[str] = []
    daily_start = date(2023, 1, 2)
    for asset_id in assets:
        for index in range(150):
            close = 30.0 + index * 0.35
            daily_rows.append(
                _kline_row(asset_id, daily_start + timedelta(days=index), close, 300_000.0)
            )
    daily_path.write_text("\n".join(daily_rows), encoding="utf-8")

    weekly_rows: list[str] = []
    weekly_start = date(2020, 1, 3)
    for asset_id in assets:
        for index in range(130):
            close = 30.0 + index
            weekly_rows.append(
                _kline_row(asset_id, weekly_start + timedelta(days=index * 7), close, 300_000.0)
            )
    weekly_path.write_text("\n".join(weekly_rows), encoding="utf-8")

    signal_date = (daily_start + timedelta(days=149)).strftime("%Y%m%d")
    context_path.write_text(
        "\n".join(
            [
                "asset_id\ttrade_date\tname\tindustry\tmarket\tlist_status\ttotal_mv\tturnover_rate\tmax_turnover_rate_20d\tavg_turnover_rate_20d\tavg_amount_20d\tstrong_industry_hit\tstrong_concept_hit\tstrong_industry_names\tstrong_concept_names\tvolume_ratio_5d_20d\tmax_volume_ratio_5d_20d\tturnover_ratio_5d_20d\tadj_factor_changed_20d",
                f"000001.SZ\t{signal_date}\t强势样本\t电子元件\t主板\tL\t1200000\t2\t3\t2\t300000\t1\t0\t电子元件\t先进封装\t1.0\t1.2\t1.0\t0",
                f"000002.SZ\t{signal_date}\t弱上下文\t半导体\t主板\tL\t1200000\t2\t3\t2\t300000\t0\t0\t\t\t1.0\t1.2\t1.0\t0",
            ]
        ),
        encoding="utf-8",
    )
    return signal_date


def _kline_row(asset_id: str, trade_date: date, close: float, amount: float) -> str:
    return "\t".join(
        (
            asset_id,
            trade_date.strftime("%Y%m%d"),
            str(close - 0.2),
            str(close + 0.4),
            str(close - 0.5),
            str(close),
            str(amount),
            "100000",
        )
    )


if __name__ == "__main__":
    unittest.main()
