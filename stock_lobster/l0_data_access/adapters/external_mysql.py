"""Read-only MySQL adapter for external factual data assets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from stock_lobster.l0_data_access.contracts import DataAsset

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_identifier(value: str) -> str:
    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"unsafe SQL identifier: {value}")
    return f"`{value}`"


@dataclass(frozen=True, slots=True)
class MysqlConnectionConfig:
    """Connection settings for a read-only external MySQL source."""

    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "MysqlConnectionConfig":
        """Build config from a JSON-friendly mapping."""

        return cls(
            host=str(payload.get("host", "127.0.0.1")),
            port=int(payload.get("port", 3306)),
            user=str(payload["user"]),
            password=str(payload.get("password", "")),
            database=str(payload["database"]),
            charset=str(payload.get("charset", "utf8mb4")),
        )

    @classmethod
    def load_json(cls, path: str | Path) -> "MysqlConnectionConfig":
        """Load connection settings from a JSON file."""

        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("mysql config must contain a JSON object")
        return cls.from_mapping(payload)


@dataclass(frozen=True, slots=True)
class ExternalMysqlAdapter:
    """Read-only adapter for external MySQL data assets."""

    connection_name: str
    connection_factory: Callable[[], Any] | None = None

    def describe_asset(self, asset: DataAsset) -> DataAsset:
        """Return the supplied contract without touching factual data."""

        return asset

    @classmethod
    def from_config(cls, config: MysqlConnectionConfig, connection_name: str = "external_mysql") -> "ExternalMysqlAdapter":
        """Create an adapter from MySQL connection settings."""

        def connection_factory() -> Any:
            import pymysql

            return pymysql.connect(
                host=config.host,
                port=config.port,
                user=config.user,
                password=config.password,
                database=config.database,
                charset=config.charset,
                cursorclass=pymysql.cursors.DictCursor,
            )

        return cls(connection_name=connection_name, connection_factory=connection_factory)

    @classmethod
    def from_config_path(
        cls,
        path: str | Path,
        connection_name: str = "external_mysql",
    ) -> "ExternalMysqlAdapter":
        """Create an adapter from a JSON config file."""

        return cls.from_config(MysqlConnectionConfig.load_json(path), connection_name=connection_name)

    def fetch_rows(
        self,
        asset: DataAsset,
        filters: Mapping[str, object],
        fields: tuple[str, ...] | None = None,
        limit: int | None = None,
    ) -> tuple[Mapping[str, object], ...]:
        """Fetch rows with exact-match filters from one registered data asset."""

        if self.connection_factory is None:
            raise ValueError("connection_factory is required to fetch rows")

        sql, params = self.build_select_sql(asset=asset, filters=filters, fields=fields, limit=limit)
        connection = self.connection_factory()
        cursor = connection.cursor()
        try:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            if rows and isinstance(rows[0], Mapping):
                return tuple(dict(row) for row in rows)
            column_names = tuple(column[0] for column in (cursor.description or ()))
            return tuple(dict(zip(column_names, row)) for row in rows)
        finally:
            close = getattr(cursor, "close", None)
            if callable(close):
                close()
            close_connection = getattr(connection, "close", None)
            if callable(close_connection):
                close_connection()

    def build_select_sql(
        self,
        asset: DataAsset,
        filters: Mapping[str, object],
        fields: tuple[str, ...] | None = None,
        limit: int | None = None,
    ) -> tuple[str, tuple[object, ...]]:
        """Build a parameterized SELECT statement for one data asset."""

        table_name = asset.table_name or asset.data_product
        if table_name is None:
            raise ValueError(f"{asset.asset_id} does not define table_name or data_product")

        selected_fields = fields or tuple(asset.field_schema.keys())
        if not selected_fields:
            raise ValueError(f"{asset.asset_id} has no selectable fields")
        unknown_fields = [field for field in selected_fields if field not in asset.field_schema]
        if unknown_fields:
            raise ValueError(f"{asset.asset_id} unknown fields: {', '.join(unknown_fields)}")

        unknown_filters = [field for field in filters if field not in asset.field_schema]
        if unknown_filters:
            raise ValueError(f"{asset.asset_id} unknown filter fields: {', '.join(unknown_filters)}")

        select_clause = ", ".join(_safe_identifier(field) for field in selected_fields)
        where_clause = " AND ".join(f"{_safe_identifier(field)} = %s" for field in filters)
        sql = f"SELECT {select_clause} FROM {_safe_identifier(table_name)}"
        params: list[object] = list(filters.values())
        if where_clause:
            sql = f"{sql} WHERE {where_clause}"
        if limit is not None:
            if limit <= 0:
                raise ValueError("limit must be positive")
            sql = f"{sql} LIMIT %s"
            params.append(limit)
        return sql, tuple(params)
