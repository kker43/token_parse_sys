"""Contract tests for the steady-uptrend S1-S5 MVP scan job."""

from __future__ import annotations

from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from workflows.jobs.steady_uptrend_s1_s5_mvp_scan import (
    _evaluate_universe,
    _required_strategy_status,
    build_parser,
    main,
    validate_scan_input_contracts,
)
from stock_lobster.research import SteadyUptrendMvpPolicy
from stock_lobster.research.trend_breakout_scan import StockSignalContext


class SteadyUptrendS1S5MvpScanTest(unittest.TestCase):
    def test_parser_requires_all_fact_inputs_and_run_metadata(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args([])

    def test_scanner_accepts_research_and_test_tracking_statuses(self) -> None:
        self.assertEqual(
            "research_only",
            _required_strategy_status({"status": "research_only"}),
        )
        self.assertEqual(
            "test_tracking",
            _required_strategy_status({"status": "test_tracking"}),
        )

    def test_scanner_rejects_active_production_status(self) -> None:
        with self.assertRaisesRegex(ValueError, "research_only or test_tracking"):
            _required_strategy_status({"status": "active_production"})

    def test_scan_writes_stage_audit_json_and_grouped_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            daily_path = root / "daily.tsv"
            weekly_path = root / "weekly.tsv"
            context_path = root / "context.tsv"
            kline_manifest_path = root / "kline_manifest.json"
            context_manifest_path = root / "context_manifest.json"
            quality_status_path = root / "quality_status.json"
            config_path = root / "strategy.json"
            output_path = root / "result.json"
            markdown_path = root / "result.md"
            signal_date = _write_inputs(daily_path, weekly_path, context_path)
            _write_contract_evidence(
                kline_manifest_path,
                context_manifest_path,
                quality_status_path,
                signal_date,
            )
            config_path.write_text(
                json.dumps(
                    {
                        "strategy_id": "strategy.steady_uptrend_mvp",
                        "version": "v1",
                        "status": "test_tracking",
                        "policy": {},
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
                    "--kline-manifest-path",
                    str(kline_manifest_path),
                    "--stock-context-manifest-path",
                    str(context_manifest_path),
                    "--quality-status-path",
                    str(quality_status_path),
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
            self.assertEqual("strategy.steady_uptrend_mvp", payload["strategy_id"])
            self.assertEqual("test_tracking", payload["status"])
            self.assertEqual(
                "test_tracking_observation_candidates",
                payload["output_kind"],
            )
            self.assertTrue(payload["data_dependency_versions"]["daily_kline"].startswith("v1:"))
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

    def test_rejects_wrong_amount_unit_and_blocked_quality(self) -> None:
        kline_manifest = {
            "job_name": "research_kline_batch_export",
            "price_basis": "qfq_asof",
            "daily_end_date": "20260710",
            "weekly_end_date": "20260710",
            "field_units": {"amount": "cny", "vol": "lot"},
        }
        context_manifest = {
            "job_name": "research_stock_context_batch_export",
            "trade_dates": ["20260710"],
            "field_units": {
                "total_mv": "ten_thousand_cny",
                "avg_amount_20d": "thousand_cny",
            },
        }
        readiness = {
            "statuses": [
                {
                    "data_product": "pub_stock_daily_kline",
                    "data_date": "20260710",
                    "status": "failed",
                    "quality_level": "failed",
                    "source_end_date": "20260710",
                }
            ]
        }

        with self.assertRaisesRegex(ValueError, "amount unit mismatch"):
            validate_scan_input_contracts(
                kline_manifest,
                context_manifest,
                readiness,
                signal_date="20260710",
                daily_kline_path="daily.tsv",
                weekly_kline_path="weekly.tsv",
                stock_context_path="context.tsv",
            )

    def test_rejects_ready_status_from_the_wrong_market(self) -> None:
        statuses = []
        for product in _required_quality_products():
            statuses.extend(
                [
                    _quality_status(product, market="CN_A", status="failed", quality_level="failed"),
                    _quality_status(product, market="US", status="ready", quality_level="pass"),
                ]
            )

        with self.assertRaisesRegex(ValueError, "not ready for pub_stock_daily_kline"):
            validate_scan_input_contracts(
                _kline_manifest("daily.tsv", "weekly.tsv", "20260710"),
                _context_manifest("context.tsv", "20260710"),
                {"statuses": statuses},
                signal_date="20260710",
                daily_kline_path="daily.tsv",
                weekly_kline_path="weekly.tsv",
                stock_context_path="context.tsv",
            )

    def test_duplicate_context_rows_abort_the_scan(self) -> None:
        context = StockSignalContext(asset_id="000001.SZ", trade_date="20260710")

        with self.assertRaisesRegex(ValueError, "duplicate stock context"):
            _evaluate_universe(
                (),
                (),
                (context, context),
                signal_date="20260710",
                policy=SteadyUptrendMvpPolicy(),
            )

    def test_duplicate_quality_status_key_aborts_validation(self) -> None:
        statuses = [
            _quality_status(product)
            for product in _required_quality_products()
        ]
        statuses.append(_quality_status("pub_stock_daily_kline"))

        with self.assertRaisesRegex(ValueError, "duplicate quality status"):
            validate_scan_input_contracts(
                _kline_manifest("daily.tsv", "weekly.tsv", "20260710"),
                _context_manifest("context.tsv", "20260710"),
                {"statuses": statuses},
                signal_date="20260710",
                daily_kline_path="daily.tsv",
                weekly_kline_path="weekly.tsv",
                stock_context_path="context.tsv",
            )

    def test_manifest_version_must_match_quality_status(self) -> None:
        kline_manifest = _kline_manifest("daily.tsv", "weekly.tsv", "20260710")
        kline_manifest["data_versions"] = {
            "daily_kline": "v999",
            "weekly_kline": "v1",
        }
        statuses = [
            _quality_status(product)
            for product in _required_quality_products()
        ]

        with self.assertRaisesRegex(ValueError, "data version mismatch"):
            validate_scan_input_contracts(
                kline_manifest,
                _context_manifest("context.tsv", "20260710"),
                {"statuses": statuses},
                signal_date="20260710",
                daily_kline_path="daily.tsv",
                weekly_kline_path="weekly.tsv",
                stock_context_path="context.tsv",
            )


def _write_inputs(daily_path: Path, weekly_path: Path, context_path: Path) -> str:
    assets = ("000001.SZ", "000002.SZ")
    daily_rows: list[str] = []
    daily_start = date(2023, 1, 2)
    signal = daily_start + timedelta(days=149)
    signal_date = signal.strftime("%Y%m%d")
    for asset_id in assets:
        for index in range(150):
            close = 30.0 + index * 0.35
            daily_rows.append(
                _kline_row(asset_id, daily_start + timedelta(days=index), close, 300_000.0)
            )
    daily_path.write_text("\n".join(daily_rows), encoding="utf-8")

    weekly_rows: list[str] = []
    previous_friday = signal - timedelta(days=(signal.weekday() - 4) % 7 or 7)
    weekly_start = previous_friday - timedelta(weeks=129)
    for asset_id in assets:
        for index in range(130):
            close = 30.0 + index
            weekly_rows.append(
                _kline_row(asset_id, weekly_start + timedelta(days=index * 7), close, 300_000.0)
            )
    weekly_path.write_text("\n".join(weekly_rows), encoding="utf-8")

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


def _write_contract_evidence(
    kline_manifest_path: Path,
    context_manifest_path: Path,
    quality_status_path: Path,
    signal_date: str,
) -> None:
    kline_manifest = _kline_manifest(
        str(kline_manifest_path.parent / "daily.tsv"),
        str(kline_manifest_path.parent / "weekly.tsv"),
        signal_date,
    )
    kline_manifest_path.write_text(
        json.dumps(kline_manifest),
        encoding="utf-8",
    )
    context_manifest_path.write_text(
        json.dumps(
            _context_manifest(
                str(context_manifest_path.parent / "context.tsv"),
                signal_date,
            )
        ),
        encoding="utf-8",
    )
    quality_status_path.write_text(
        json.dumps(
            {
                "statuses": [
                    _quality_status(
                        product,
                        data_date=(
                            str(kline_manifest["weekly_latest_trade_date"])
                            if product == "pub_stock_weekly_kline"
                            else signal_date
                        ),
                    )
                    for product in _required_quality_products()
                ]
            }
        ),
        encoding="utf-8",
    )


def _kline_manifest(daily_path: str, weekly_path: str, signal_date: str) -> dict[str, object]:
    daily = Path(daily_path)
    weekly = Path(weekly_path)
    return {
        "job_name": "research_kline_batch_export",
        "price_basis": "qfq_asof",
        "daily_end_date": signal_date,
        "weekly_end_date": signal_date,
        "daily_output_path": str(daily),
        "weekly_output_path": str(weekly),
        "daily_row_count": _line_count(daily),
        "weekly_row_count": _line_count(weekly),
        "weekly_latest_trade_date": _latest_trade_date(weekly),
        "daily_sha256": _sha256(daily),
        "weekly_sha256": _sha256(weekly),
        "data_versions": {"daily_kline": "v1", "weekly_kline": "v1"},
        "field_units": {"amount": "thousand_cny", "vol": "lot"},
    }


def _context_manifest(path: str, signal_date: str) -> dict[str, object]:
    context = Path(path)
    return {
        "job_name": "research_stock_context_batch_export",
        "trade_dates": [signal_date],
        "output_path": str(context),
        "row_count": max(0, _line_count(context) - 1),
        "sha256": _sha256(context),
        "data_version": "v1",
        "field_units": {
            "total_mv": "ten_thousand_cny",
            "avg_amount_20d": "thousand_cny",
        },
    }


def _quality_status(
    product: str,
    *,
    data_date: str = "20260710",
    market: str = "CN_A",
    status: str = "ready",
    quality_level: str = "pass",
) -> dict[str, object]:
    return {
        "data_product": product,
        "data_date": data_date,
        "market": market,
        "asset_type": "stock",
        "status": status,
        "quality_level": quality_level,
        "source_end_date": data_date,
        "data_version": "v1",
    }


def _required_quality_products() -> tuple[str, ...]:
    return (
        "pub_stock_daily_kline",
        "pub_stock_weekly_kline",
        "pub_stock_daily_basic",
        "pub_stock_daily_indicator",
        "pub_stock_asset_basic",
    )


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8").splitlines())


def _sha256(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest_trade_date(path: Path) -> str:
    if not path.exists():
        return "20260710"
    dates = [line.split("\t", 2)[1] for line in path.read_text(encoding="utf-8").splitlines()]
    return max(dates) if dates else "20260710"


if __name__ == "__main__":
    unittest.main()
