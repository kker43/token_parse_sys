"""Tests for the daily strategy signal production workflow job."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from stock_lobster.research import TrendBreakoutScanPolicy
from workflows.jobs.daily_strategy_signal_production import (
    _fetch_kline_rows,
    _policy_from_strategy_payload,
    _resolve_settings,
    _stock_context_sql,
    _write_candidates_csv,
    build_parser,
)


class DailyStrategySignalProductionJobTest(unittest.TestCase):
    def test_resolve_settings_reads_schedule_config(self) -> None:
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            schedule_path = root / "schedule.json"
            schedule_path.write_text(
                json.dumps(
                    {
                        "mysql_config_path": "mysql.json",
                        "strategy_config_path": "strategy.json",
                        "output_root": "runtime/signals",
                        "lookback_daily_trade_days": 120,
                        "lookback_weekly_trade_days": 60,
                        "price_basis": "qfq_asof",
                    }
                ),
                encoding="utf-8",
            )
            args = build_parser().parse_args(["--schedule-config-path", str(schedule_path), "--date", "20260703"])

            settings = _resolve_settings(args)

        self.assertEqual(str((root / "mysql.json").resolve()), settings["mysql_config_path"])
        self.assertEqual(str((root / "strategy.json").resolve()), settings["strategy_config_path"])
        self.assertEqual(str((root / "runtime/signals").resolve()), settings["output_root"])
        self.assertEqual("20260703", settings["date"])
        self.assertEqual(120, settings["lookback_daily_trade_days"])
        self.assertEqual(60, settings["lookback_weekly_trade_days"])
        self.assertEqual("qfq_asof", settings["price_basis"])

    def test_fetch_kline_rows_uses_qfq_anchor_factor(self) -> None:
        connection = _FakeConnection(
            [
                {
                    "ts_code": "002768.SZ",
                    "trade_date": "20260618",
                    "open": 54.5,
                    "high": 55.0,
                    "low": 53.0,
                    "close": 54.8,
                    "amount": 100.0,
                }
            ]
        )

        rows = _fetch_kline_rows(
            connection=connection,
            table_name="token_daily_details",
            signal_date="20260708",
            start_date="20260601",
            end_date="20260708",
            price_basis="qfq_asof",
        )

        self.assertEqual("002768.SZ", rows[0]["ts_code"])
        self.assertIn("JOIN stock_adj_factor_daily f", connection.cursor_obj.executed_sql)
        self.assertIn("anchor.trade_date = %s", connection.cursor_obj.executed_sql)
        self.assertEqual(("20260708", "20260601", "20260708"), connection.cursor_obj.executed_params)

    def test_policy_from_strategy_payload_keeps_only_scanner_fields(self) -> None:
        policy = _policy_from_strategy_payload(
            {
                "candidate_scan_policy": {
                    "candidate_mode": "pre_breakout",
                    "top_n_per_date": None,
                    "require_weekly_uptrend": True,
                    "require_context_strength": True,
                    "min_avg_amount_20d": 200_000,
                    "unknown_field": "ignored",
                }
            },
            "20260703",
        )

        self.assertIsInstance(policy, TrendBreakoutScanPolicy)
        self.assertEqual("20260703", policy.start_date)
        self.assertTrue(policy.require_weekly_uptrend)
        self.assertTrue(policy.require_context_strength)
        self.assertEqual(200_000, policy.min_avg_amount_20d)

    def test_stock_context_sql_consumes_published_5d_20d_volume_ratio(self) -> None:
        sql = _stock_context_sql()

        self.assertIn("pub_stock_daily_indicator", sql)
        self.assertIn("indicator_name = 'volume_ratio_5d_20d'", sql)
        self.assertIn("indicator_version = 'legacy_v1'", sql)
        self.assertIn("params_hash = 'default'", sql)
        self.assertIn("volume_ratio_5d_20d", sql)
        self.assertIn("published_volume_ratio AS (", sql)
        self.assertIn("GROUP BY asset_id", sql)

    def test_write_candidates_csv_renders_list_fields(self) -> None:
        with TemporaryDirectory() as tempdir:
            output_path = Path(tempdir) / "candidates.csv"

            _write_candidates_csv(
                output_path,
                [
                    {
                        "trade_date": "20260703",
                        "asset_id": "000001.SZ",
                        "name": "sample",
                        "strong_concept_names": ["概念A", "概念B"],
                    }
                ],
            )

            text = output_path.read_text(encoding="utf-8")

        self.assertIn("000001.SZ", text)
        self.assertIn("概念A;概念B", text)

    def test_job_script_exposes_help_as_direct_file_entrypoint(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        script_path = repo_root / "workflows" / "jobs" / "daily_strategy_signal_production.py"

        completed = subprocess.run(
            (sys.executable, str(script_path), "--help"),
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, msg=completed.stderr)
        self.assertIn("daily_strategy_signal_production", completed.stdout)


class _FakeConnection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.cursor_obj = _FakeCursor(rows)

    def cursor(self) -> "_FakeCursor":
        return self.cursor_obj


class _FakeCursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.executed_sql = ""
        self.executed_params: object = None

    def execute(self, sql: str, params: object) -> None:
        self.executed_sql = sql
        self.executed_params = params

    def fetchall(self) -> list[dict[str, object]]:
        return self.rows

    def close(self) -> None:
        return None
