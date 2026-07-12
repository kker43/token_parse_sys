"""Tests for the end-to-end steady-uptrend MVP tracking job."""

from __future__ import annotations

import fcntl
import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from workflows.jobs.daily_steady_uptrend_mvp_tracking import (
    PipelineDependencies,
    TrackingSchedule,
    _fetch_quality_status_rows,
    execute_tracking_job,
    main,
    resolve_readiness,
    resolve_routine_strategy,
)


DAILY_PRODUCTS = (
    "pub_stock_daily_kline",
    "pub_stock_daily_basic",
    "pub_stock_daily_indicator",
    "pub_stock_asset_basic",
)


class DailySteadyUptrendMvpTrackingTest(unittest.TestCase):
    def test_auto_date_uses_latest_complete_daily_gate(self) -> None:
        rows = [
            *(_quality(product, "20260710") for product in DAILY_PRODUCTS),
            _quality("pub_stock_weekly_kline", "20260710"),
            *(
                _quality(product, "20260711")
                for product in DAILY_PRODUCTS[:-1]
            ),
        ]

        resolved = resolve_readiness(rows)

        self.assertEqual("20260710", resolved.trade_date)
        self.assertEqual("20260710", resolved.weekly_trade_date)
        self.assertEqual(5, len(resolved.statuses))

    def test_explicit_date_requires_a_complete_daily_gate(self) -> None:
        rows = [
            *(_quality(product, "20260710") for product in DAILY_PRODUCTS),
            _quality("pub_stock_weekly_kline", "20260710"),
            *(
                _quality(product, "20260711")
                for product in DAILY_PRODUCTS[:-1]
            ),
        ]

        with self.assertRaisesRegex(
            ValueError,
            "quality readiness is incomplete for 20260711",
        ):
            resolve_readiness(rows, requested_date="20260711")

    def test_duplicate_quality_key_is_rejected(self) -> None:
        rows = [
            *(_quality(product, "20260710") for product in DAILY_PRODUCTS),
            _quality("pub_stock_daily_kline", "20260710"),
            _quality("pub_stock_weekly_kline", "20260710"),
        ]

        with self.assertRaisesRegex(ValueError, "duplicate quality status"):
            resolve_readiness(rows)

    def test_weekly_gate_uses_latest_source_date_not_after_signal_date(self) -> None:
        rows = [
            *(_quality(product, "20260709") for product in DAILY_PRODUCTS),
            _quality("pub_stock_weekly_kline", "20260703"),
            _quality("pub_stock_weekly_kline", "20260710"),
        ]

        resolved = resolve_readiness(rows, requested_date="20260709")

        self.assertEqual("20260703", resolved.weekly_trade_date)
        weekly = next(
            item
            for item in resolved.statuses
            if item["data_product"] == "pub_stock_weekly_kline"
        )
        self.assertEqual("20260703", weekly["source_end_date"])

    def test_registry_requires_exactly_one_enabled_strategy(self) -> None:
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            strategy_path = root / "strategy.json"
            _write_strategy(strategy_path)
            registry_path = root / "registry.json"
            registry_path.write_text(
                json.dumps({"strategies": []}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "exactly one"):
                resolve_routine_strategy(registry_path, strategy_path)

            entry = _registry_entry()
            registry_path.write_text(
                json.dumps({"strategies": [entry, entry]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "exactly one"):
                resolve_routine_strategy(registry_path, strategy_path)

    def test_pipeline_exports_scans_and_atomically_publishes_report(self) -> None:
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            schedule = _write_schedule(root)
            events: list[str] = []
            dependencies = _fixture_dependencies(events)

            exit_code, result = execute_tracking_job(
                schedule,
                connection=object(),
                requested_date="20260710",
                dependencies=dependencies,
            )

            self.assertEqual(0, exit_code)
            self.assertEqual(
                ["quality", "kline", "context", "scan"],
                events,
            )
            self.assertEqual("success", result["status"])
            self.assertEqual(1, result["candidate_count"])
            report_dir = schedule.report_root / "20260710"
            self.assertEqual(
                {"report.md", "candidates.json", "job_result.json"},
                {path.name for path in report_dir.iterdir()},
            )
            published = json.loads(
                (report_dir / "candidates.json").read_text(encoding="utf-8")
            )
            self.assertEqual("strategy.steady_uptrend_mvp", published["strategy_id"])
            latest = json.loads(schedule.latest_result_path.read_text(encoding="utf-8"))
            self.assertEqual("20260710", latest["trade_date"])

    def test_scan_failure_does_not_overwrite_existing_success(self) -> None:
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            schedule = _write_schedule(root)
            schedule.latest_result_path.parent.mkdir(parents=True, exist_ok=True)
            schedule.latest_result_path.write_text("old-latest", encoding="utf-8")
            report_dir = schedule.report_root / "20260710"
            report_dir.mkdir(parents=True)
            (report_dir / "report.md").write_text("old-report", encoding="utf-8")
            dependencies = _fixture_dependencies([], fail_scan=True)

            exit_code, result = execute_tracking_job(
                schedule,
                connection=object(),
                requested_date="20260710",
                dependencies=dependencies,
            )

            self.assertEqual(1, exit_code)
            self.assertEqual("failed", result["status"])
            self.assertEqual("scan", result["failed_stage"])
            self.assertEqual("old-latest", schedule.latest_result_path.read_text(encoding="utf-8"))
            self.assertEqual("old-report", (report_dir / "report.md").read_text(encoding="utf-8"))
            failure = json.loads(
                (schedule.job_result_root / "20260710.json").read_text(encoding="utf-8")
            )
            self.assertEqual("RuntimeError", failure["error_type"])

    def test_held_lock_rejects_a_second_run(self) -> None:
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            schedule = _write_schedule(root)
            schedule.lock_path.parent.mkdir(parents=True, exist_ok=True)
            with schedule.lock_path.open("w", encoding="utf-8") as lock_handle:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                exit_code, result = execute_tracking_job(
                    schedule,
                    connection=object(),
                    requested_date="20260710",
                    dependencies=_fixture_dependencies([]),
                )

            self.assertEqual(1, exit_code)
            self.assertEqual("acquire_lock", result["failed_stage"])

    def test_initialization_failure_is_persisted_after_schedule_load(self) -> None:
        with TemporaryDirectory() as tempdir:
            schedule = _write_schedule(Path(tempdir))
            with (
                mock.patch(
                    "workflows.jobs.daily_steady_uptrend_mvp_tracking.TrackingSchedule.load",
                    return_value=schedule,
                ),
                mock.patch(
                    "workflows.jobs.daily_steady_uptrend_mvp_tracking.MysqlConnectionConfig.load_json",
                    side_effect=RuntimeError("database unavailable"),
                ),
            ):
                with redirect_stdout(io.StringIO()):
                    exit_code = main(
                        [
                            "--schedule-config-path",
                            "schedule.json",
                            "--date",
                            "20260710",
                        ]
                    )

            self.assertEqual(1, exit_code)
            failure = json.loads(
                (schedule.job_result_root / "20260710.json").read_text(encoding="utf-8")
            )
            self.assertEqual("initialize", failure["failed_stage"])

    def test_quality_reader_uses_exact_daily_gate_and_bounded_weekly_queries(self) -> None:
        daily_rows = tuple(
            _quality(product, "20260710") for product in DAILY_PRODUCTS
        )
        calls: list[tuple[str, object]] = []

        def fetch_rows(connection: object, sql: str, params: object):
            calls.append((sql, params))
            if "FROM pub_data_quality_status" in sql:
                return daily_rows
            if "MAX(period_end_date)" in sql:
                return ({"weekly_date": "20260710"},)
            if "COUNT(*) AS record_count" in sql:
                return (
                    {
                        "record_count": 5605,
                        "min_data_version": "v1",
                        "max_data_version": "v1",
                        "published_at": "2026-07-10 23:59:59",
                    },
                )
            raise AssertionError(sql)

        with mock.patch(
            "workflows.jobs.daily_steady_uptrend_mvp_tracking._fetch_rows",
            side_effect=fetch_rows,
        ):
            rows = _fetch_quality_status_rows(object(), "20260710")

        self.assertEqual(5, len(rows))
        weekly = rows[-1]
        self.assertEqual("pub_stock_weekly_kline", weekly["data_product"])
        self.assertEqual(5605, weekly["record_count"])
        sql_text = "\n".join(sql for sql, _ in calls)
        self.assertNotIn("data_date <=", sql_text)
        self.assertIn("data_date = %s", sql_text)
        self.assertIn("MAX(period_end_date)", sql_text)
        self.assertIn("period_end_date = %s", sql_text)


def _quality(
    product: str,
    data_date: str,
    *,
    source_end_date: str | None = None,
    status: str = "ready",
    quality_level: str = "pass",
) -> dict[str, object]:
    return {
        "data_product": product,
        "data_date": data_date,
        "market": "CN_A",
        "asset_type": "stock",
        "status": status,
        "quality_level": quality_level,
        "record_count": 100,
        "expected_min_records": 1,
        "source_tables": product,
        "source_end_date": source_end_date or data_date,
        "published_at": "2026-07-12 00:00:00",
        "data_version": "v1",
        "error_message": None,
    }


def _write_strategy(path: Path) -> None:
    path.write_text(
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


def _registry_entry() -> dict[str, object]:
    return {
        "strategy_id": "strategy.steady_uptrend_mvp",
        "version": "v1",
        "status": "test_tracking",
        "role": "routine_primary",
        "routine_selection_enabled": True,
        "config_path": "configs/strategies/steady_uptrend_mvp.json",
        "selection_job": "workflows/jobs/steady_uptrend_s1_s5_mvp_scan.py",
    }


def _write_schedule(root: Path) -> TrackingSchedule:
    strategy_path = root / "strategy.json"
    registry_path = root / "registry.json"
    _write_strategy(strategy_path)
    registry_path.write_text(
        json.dumps({"strategies": [_registry_entry()]}),
        encoding="utf-8",
    )
    return TrackingSchedule(
        mysql_config_path=root / "mysql.json",
        strategy_registry_path=registry_path,
        strategy_config_path=strategy_path,
        run_root=root / "runtime",
        report_root=root / "runtime/reports",
        job_result_root=root / "runtime/job_results",
        latest_result_path=root / "runtime/reports/latest.json",
        lock_path=root / "runtime/tracking.lock",
        daily_lookback_calendar_days=440,
        weekly_lookback_calendar_days=950,
        price_basis="qfq_asof",
    )


def _fixture_dependencies(
    events: list[str],
    *,
    fail_scan: bool = False,
) -> PipelineDependencies:
    def fetch_quality_rows(connection: object, requested_date: str | None):
        events.append("quality")
        return (
            *(_quality(product, "20260710") for product in DAILY_PRODUCTS),
            _quality("pub_stock_weekly_kline", "20260710"),
        )

    def export_kline(**kwargs: object) -> dict[str, object]:
        events.append("kline")
        daily_path = Path(str(kwargs["daily_output_path"]))
        weekly_path = Path(str(kwargs["weekly_output_path"]))
        daily_path.parent.mkdir(parents=True, exist_ok=True)
        daily_path.write_text("000001.SZ\t20260710\t1\t1\t1\t1\t1\t1", encoding="utf-8")
        weekly_path.write_text("000001.SZ\t20260710\t1\t1\t1\t1\t1\t1", encoding="utf-8")
        manifest = {
            "daily_sha256": _sha256(daily_path),
            "weekly_sha256": _sha256(weekly_path),
            "data_versions": {"daily_kline": "v1", "weekly_kline": "v1"},
        }
        Path(str(kwargs["manifest_path"])).write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def export_context(**kwargs: object) -> dict[str, object]:
        events.append("context")
        output_path = Path(str(kwargs["output_path"]))
        output_path.write_text("asset_id\ttrade_date\n000001.SZ\t20260710", encoding="utf-8")
        manifest = {"sha256": _sha256(output_path), "data_version": "v1"}
        Path(str(kwargs["manifest_path"])).write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def run_scanner(arguments: list[str]) -> int:
        events.append("scan")
        if fail_scan:
            raise RuntimeError("fixture scan failed")
        values = dict(zip(arguments[::2], arguments[1::2]))
        payload = {
            "strategy_id": "strategy.steady_uptrend_mvp",
            "version": "v1",
            "status": "test_tracking",
            "data_dependency_versions": {
                "daily_kline": "v1:test",
                "weekly_kline": "v1:test",
                "stock_context": "v1:test",
            },
            "stage_counts": {"s5_entry_selection": {"passed": 1}},
            "candidates": [{"asset_id": "000001.SZ"}],
        }
        Path(values["--output-path"]).write_text(json.dumps(payload), encoding="utf-8")
        Path(values["--markdown-output-path"]).write_text("fixture report", encoding="utf-8")
        return 0

    return PipelineDependencies(
        fetch_quality_rows=fetch_quality_rows,
        export_kline=export_kline,
        export_context=export_context,
        run_scanner=run_scanner,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
