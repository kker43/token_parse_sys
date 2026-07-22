"""Tests for batch kline export used by research backtests."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from workflows.jobs.research_kline_batch_export import _fetch_kline_rows, export_kline_batch


class ResearchKlineBatchExportTest(unittest.TestCase):
    def test_fetches_qfq_rows_in_bounded_symbol_batches(self) -> None:
        symbols = [f"{index:06d}.SZ" for index in range(201)]
        connection = _ScriptedConnection(symbols)

        rows = _fetch_kline_rows(
            connection=connection,
            table_name="token_daily_details",
            start_date="20250101",
            end_date="20260721",
            price_basis="qfq_asof",
        )

        self.assertEqual(3, len(connection.calls))
        self.assertIn("FROM stock_adj_factor_daily", connection.calls[0][0])
        self.assertEqual(("20260721",), connection.calls[0][1])
        self.assertEqual(203, len(connection.calls[1][1]))
        self.assertEqual(4, len(connection.calls[2][1]))
        self.assertEqual(
            [symbols[0], symbols[-1]],
            [row["ts_code"] for row in rows],
        )

    def test_exports_daily_and_weekly_kline_with_manifest(self) -> None:
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            daily_path = root / "kline.tsv"
            weekly_path = root / "weekly_kline.tsv"
            manifest_path = root / "kline_manifest.json"
            calls: list[tuple[str, str, str]] = []

            def fetch_rows(table_name: str, start_date: str, end_date: str) -> tuple[dict[str, object], ...]:
                calls.append((table_name, start_date, end_date))
                if table_name == "token_daily_details":
                    return (
                        {
                            "ts_code": "000001.SZ",
                            "trade_date": "20250102",
                            "open": 10,
                            "high": 11,
                            "low": 9,
                            "close": 10.5,
                            "amount": 100,
                            "vol": 3000,
                        },
                    )
                return (
                    {
                        "ts_code": "000001.SZ",
                        "trade_date": "20240105",
                        "open": 8,
                        "high": 12,
                        "low": 7,
                        "close": 10,
                        "amount": 500,
                        "vol": 12000,
                    },
                    {
                        "ts_code": "000001.SZ",
                        "trade_date": "20240112",
                        "open": 10,
                        "high": 13,
                        "low": 9,
                        "close": 12,
                        "amount": 600,
                        "vol": 13000,
                    },
                )

            manifest = export_kline_batch(
                fetch_rows=fetch_rows,
                daily_start_date="20250102",
                daily_end_date="20250103",
                weekly_start_date="20240101",
                weekly_end_date="20250103",
                daily_output_path=daily_path,
                weekly_output_path=weekly_path,
                manifest_path=manifest_path,
            )

            self.assertEqual(
                [
                    ("token_daily_details", "20250102", "20250103"),
                    ("token_weekly_details", "20240101", "20250103"),
                ],
                calls,
            )
            self.assertEqual(
                "000001.SZ\t20250102\t10\t11\t9\t10.5\t100\t3000",
                daily_path.read_text(encoding="utf-8").strip(),
            )
            self.assertEqual(2, len(weekly_path.read_text(encoding="utf-8").splitlines()))
            self.assertEqual(1, manifest["daily_row_count"])
            self.assertEqual(2, manifest["weekly_row_count"])
            self.assertEqual("20240101", manifest["weekly_start_date"])
            self.assertEqual("qfq_asof", manifest["price_basis"])
            self.assertEqual(
                {"amount": "thousand_cny", "vol": "lot"},
                manifest["field_units"],
            )
            self.assertEqual(
                {"daily_kline": "v1", "weekly_kline": "v1"},
                manifest["data_versions"],
            )
            self.assertEqual(64, len(manifest["daily_sha256"]))
            self.assertEqual(64, len(manifest["weekly_sha256"]))
            self.assertEqual("20240112", manifest["weekly_latest_trade_date"])
            self.assertEqual("vol", manifest["columns"][-1])
            self.assertEqual(manifest, json.loads(manifest_path.read_text(encoding="utf-8")))


class _ScriptedConnection:
    def __init__(self, symbols: list[str]) -> None:
        self.symbols = symbols
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def cursor(self) -> "_ScriptedCursor":
        return _ScriptedCursor(self)


class _ScriptedCursor:
    def __init__(self, connection: _ScriptedConnection) -> None:
        self.connection = connection
        self.rows: list[dict[str, object]] = []

    def execute(self, sql: str, params: object) -> None:
        if not isinstance(params, tuple):
            raise TypeError("expected tuple query parameters")
        normalized_params = params
        self.connection.calls.append((sql, normalized_params))
        if "FROM stock_adj_factor_daily" in sql and "JOIN" not in sql:
            self.rows = [{"ts_code": symbol} for symbol in self.connection.symbols]
            return
        batch_symbols = normalized_params[3:]
        self.rows = [{"ts_code": batch_symbols[0], "trade_date": "20260721"}]

    def fetchall(self) -> list[dict[str, object]]:
        return self.rows

    def close(self) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
