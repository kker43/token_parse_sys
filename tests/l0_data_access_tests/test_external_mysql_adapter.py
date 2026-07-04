"""Tests for the read-only external MySQL adapter."""

from __future__ import annotations

import unittest

from stock_lobster.l0_data_access.adapters.external_mysql import ExternalMysqlAdapter
from stock_lobster.l0_data_access.contracts import DataAsset


def sample_asset() -> DataAsset:
    return DataAsset(
        asset_id="external_provider.pub_stock_daily_kline",
        data_product="pub_stock_daily_kline",
        table_name="pub_stock_daily_kline",
        source_type="published_product",
        source_name="external_provider",
        field_schema={
            "asset_id": "string",
            "trade_date": "date_yyyymmdd",
            "close": "numeric",
            "amount": "numeric",
        },
        required_fields=("asset_id", "trade_date", "close"),
        primary_key=("asset_id", "trade_date"),
        update_frequency="daily",
        quality_status="pub_data_quality_status",
    )


class FakeCursor:
    def __init__(self) -> None:
        self.sql: str | None = None
        self.params: tuple[object, ...] | None = None
        self.description = (("asset_id",), ("trade_date",), ("close",))

    def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.sql = sql
        self.params = params

    def fetchall(self) -> list[tuple[object, ...]]:
        return [("000001.SZ", "20260704", 12.34)]

    def close(self) -> None:
        return None


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.cursor_instance = cursor

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def close(self) -> None:
        return None


class ExternalMysqlAdapterTest(unittest.TestCase):
    def test_builds_parameterized_select_sql(self) -> None:
        adapter = ExternalMysqlAdapter(connection_name="fixture")

        sql, params = adapter.build_select_sql(
            asset=sample_asset(),
            filters={"asset_id": "000001.SZ", "trade_date": "20260704"},
            fields=("asset_id", "trade_date", "close"),
            limit=1,
        )

        self.assertEqual(
            "SELECT `asset_id`, `trade_date`, `close` FROM `pub_stock_daily_kline` "
            "WHERE `asset_id` = %s AND `trade_date` = %s LIMIT %s",
            sql,
        )
        self.assertEqual(("000001.SZ", "20260704", 1), params)

    def test_rejects_unknown_filter_fields(self) -> None:
        adapter = ExternalMysqlAdapter(connection_name="fixture")

        with self.assertRaisesRegex(ValueError, "unknown filter fields"):
            adapter.build_select_sql(asset=sample_asset(), filters={"bad_field": "x"})

    def test_fetch_rows_maps_tuple_rows_to_dicts(self) -> None:
        cursor = FakeCursor()
        adapter = ExternalMysqlAdapter(
            connection_name="fixture",
            connection_factory=lambda: FakeConnection(cursor),
        )

        rows = adapter.fetch_rows(
            asset=sample_asset(),
            filters={"asset_id": "000001.SZ", "trade_date": "20260704"},
            fields=("asset_id", "trade_date", "close"),
        )

        self.assertEqual(({"asset_id": "000001.SZ", "trade_date": "20260704", "close": 12.34},), rows)
        self.assertIn("FROM `pub_stock_daily_kline`", cursor.sql or "")


if __name__ == "__main__":
    unittest.main()
