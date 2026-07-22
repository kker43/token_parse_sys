"""Batch export kline TSV inputs for research backtests."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.l0_data_access.adapters.external_mysql import (
    ExternalMysqlAdapter,
    MysqlConnectionConfig,
)
from workflows.jobs.daily_strategy_signal_production import _fetch_rows, _write_tsv
from workflows.jobs.support import write_json_payload

KLINE_COLUMNS = ("ts_code", "trade_date", "open", "high", "low", "close", "amount", "vol")
QFQ_SYMBOL_BATCH_SIZE = 200


def build_parser() -> argparse.ArgumentParser:
    """Build parser for the batch kline research export job."""

    parser = argparse.ArgumentParser(prog="research_kline_batch_export")
    parser.add_argument("--mysql-config-path", required=True)
    parser.add_argument("--daily-start-date", required=True)
    parser.add_argument("--daily-end-date", required=True)
    parser.add_argument("--weekly-start-date")
    parser.add_argument("--weekly-end-date")
    parser.add_argument("--daily-output-path", required=True)
    parser.add_argument("--weekly-output-path", required=True)
    parser.add_argument("--manifest-path")
    parser.add_argument(
        "--price-basis",
        choices=("raw", "qfq_asof"),
        default="qfq_asof",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Export daily and weekly kline TSVs for research scans."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    connection_config = MysqlConnectionConfig.load_json(args.mysql_config_path)
    adapter = ExternalMysqlAdapter.from_config(connection_config)
    if adapter.connection_factory is None:
        raise ValueError("mysql connection factory is required")

    connection = adapter.connection_factory()
    try:
        manifest = export_kline_batch(
            fetch_rows=lambda table_name, start_date, end_date: _fetch_kline_rows(
                connection=connection,
                table_name=table_name,
                start_date=start_date,
                end_date=end_date,
                price_basis=args.price_basis,
            ),
            daily_start_date=args.daily_start_date,
            daily_end_date=args.daily_end_date,
            weekly_start_date=args.weekly_start_date or args.daily_start_date,
            weekly_end_date=args.weekly_end_date or args.daily_end_date,
            daily_output_path=Path(args.daily_output_path),
            weekly_output_path=Path(args.weekly_output_path),
            manifest_path=Path(args.manifest_path) if args.manifest_path else None,
            price_basis=args.price_basis,
        )
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()

    print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def export_kline_batch(
    *,
    fetch_rows: Callable[[str, str, str], Sequence[Mapping[str, object]]],
    daily_start_date: str,
    daily_end_date: str,
    weekly_start_date: str,
    weekly_end_date: str,
    daily_output_path: Path,
    weekly_output_path: Path,
    manifest_path: Path | None = None,
    price_basis: str = "qfq_asof",
) -> dict[str, object]:
    """Export deterministic daily and weekly kline TSVs plus a manifest."""

    daily_rows = tuple(_normalize_kline_rows(fetch_rows("token_daily_details", daily_start_date, daily_end_date)))
    weekly_rows = tuple(_normalize_kline_rows(fetch_rows("token_weekly_details", weekly_start_date, weekly_end_date)))
    _write_tsv(daily_output_path, daily_rows, header=None)
    _write_tsv(weekly_output_path, weekly_rows, header=None)
    manifest = {
        "schema_version": 1,
        "job_name": "research_kline_batch_export",
        "source_tables": {
            "daily": "token_daily_details",
            "weekly": "token_weekly_details",
        },
        "daily_output_path": str(daily_output_path),
        "weekly_output_path": str(weekly_output_path),
        "daily_start_date": daily_start_date,
        "daily_end_date": daily_end_date,
        "weekly_start_date": weekly_start_date,
        "weekly_end_date": weekly_end_date,
        "price_basis": price_basis,
        "field_units": {
            "amount": "thousand_cny",
            "vol": "lot",
        },
        "data_versions": {
            "daily_kline": "v1",
            "weekly_kline": "v1",
        },
        "daily_sha256": _sha256_file(daily_output_path),
        "weekly_sha256": _sha256_file(weekly_output_path),
        "daily_row_count": len(daily_rows),
        "weekly_row_count": len(weekly_rows),
        "weekly_latest_trade_date": max(
            (str(row["trade_date"] or "") for row in weekly_rows),
            default="",
        ),
        "columns": list(KLINE_COLUMNS),
    }
    if manifest_path is not None:
        write_json_payload(manifest_path, manifest)
    return manifest


def _fetch_kline_rows(
    *,
    connection: Any,
    table_name: str,
    start_date: str,
    end_date: str,
    price_basis: str = "qfq_asof",
) -> tuple[Mapping[str, object], ...]:
    if table_name not in {"token_daily_details", "token_weekly_details"}:
        raise ValueError(f"unsupported kline table: {table_name}")
    if price_basis == "raw":
        return _fetch_rows(
            connection,
            f"""
            SELECT ts_code, trade_date, open, high, low, close, amount, vol
            FROM {table_name}
            WHERE trade_date BETWEEN %s AND %s
            ORDER BY ts_code, trade_date
            """,
            (start_date, end_date),
        )
    if price_basis != "qfq_asof":
        raise ValueError("price_basis must be raw or qfq_asof")
    anchor_rows = _fetch_rows(
        connection,
        """
        SELECT ts_code
        FROM stock_adj_factor_daily
        WHERE trade_date = %s
        ORDER BY ts_code
        """,
        (end_date,),
    )
    symbols = tuple(str(row["ts_code"]) for row in anchor_rows)
    rows: list[Mapping[str, object]] = []
    for offset in range(0, len(symbols), QFQ_SYMBOL_BATCH_SIZE):
        symbol_batch = symbols[offset : offset + QFQ_SYMBOL_BATCH_SIZE]
        placeholders = ", ".join("%s" for _ in symbol_batch)
        rows.extend(
            _fetch_rows(
                connection,
                f"""
                SELECT
                  k.ts_code,
                  k.trade_date,
                  k.open * f.adj_factor / anchor.adj_factor AS open,
                  k.high * f.adj_factor / anchor.adj_factor AS high,
                  k.low * f.adj_factor / anchor.adj_factor AS low,
                  k.close * f.adj_factor / anchor.adj_factor AS close,
                  k.amount,
                  k.vol
                FROM {table_name} k
                JOIN stock_adj_factor_daily f
                  ON f.ts_code = k.ts_code
                 AND f.trade_date = k.trade_date
                JOIN stock_adj_factor_daily anchor
                  ON anchor.ts_code = k.ts_code
                 AND anchor.trade_date = %s
                WHERE k.trade_date BETWEEN %s AND %s
                  AND k.ts_code IN ({placeholders})
                ORDER BY k.ts_code, k.trade_date
                """,
                (end_date, start_date, end_date, *symbol_batch),
            )
        )
    return tuple(rows)


def _normalize_kline_rows(rows: Sequence[Mapping[str, object]]) -> tuple[dict[str, object], ...]:
    return tuple({column: row.get(column) for column in KLINE_COLUMNS} for row in rows)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
