"""Batch export stock context TSV for research backtests."""

from __future__ import annotations

import argparse
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
from workflows.jobs.daily_strategy_signal_production import (
    _fetch_rows,
    _stock_context_sql,
    _write_tsv,
)
from workflows.jobs.support import write_json_payload

STOCK_CONTEXT_HEADER = (
    "asset_id",
    "trade_date",
    "name",
    "industry",
    "market",
    "list_status",
    "total_mv",
    "turnover_rate",
    "max_turnover_rate_20d",
    "avg_turnover_rate_20d",
    "avg_amount_20d",
    "strong_industry_hit",
    "strong_concept_hit",
    "strong_industry_names",
    "strong_concept_names",
)


def build_parser() -> argparse.ArgumentParser:
    """Build parser for the batch stock-context research export job."""

    parser = argparse.ArgumentParser(prog="research_stock_context_batch_export")
    parser.add_argument("--mysql-config-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--manifest-path")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--trade-date", action="append", dest="trade_dates")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Export stock context rows for many trade dates into one TSV."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    connection_config = MysqlConnectionConfig.load_json(args.mysql_config_path)
    adapter = ExternalMysqlAdapter.from_config(connection_config)
    if adapter.connection_factory is None:
        raise ValueError("mysql connection factory is required")

    connection = adapter.connection_factory()
    try:
        trade_dates = _resolve_trade_dates(
            connection=connection,
            explicit_trade_dates=args.trade_dates or (),
            start_date=args.start_date,
            end_date=args.end_date,
        )
        manifest = export_stock_context_batch(
            fetch_rows_for_date=lambda trade_date: _fetch_rows(
                connection,
                _stock_context_sql(),
                {"signal_date": trade_date},
            ),
            trade_dates=trade_dates,
            output_path=Path(args.output_path),
            manifest_path=Path(args.manifest_path) if args.manifest_path else None,
        )
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()

    print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def export_stock_context_batch(
    *,
    fetch_rows_for_date: Callable[[str], Sequence[Mapping[str, object]]],
    trade_dates: Sequence[str],
    output_path: Path,
    manifest_path: Path | None = None,
) -> dict[str, object]:
    """Export stock context rows for sorted unique trade dates."""

    normalized_trade_dates = _normalize_trade_dates(trade_dates)
    rows: list[Mapping[str, object]] = []
    rows_by_trade_date: dict[str, int] = {}
    for trade_date in normalized_trade_dates:
        date_rows = tuple(fetch_rows_for_date(trade_date))
        rows.extend(date_rows)
        rows_by_trade_date[trade_date] = len(date_rows)

    _write_tsv(output_path, rows, header=STOCK_CONTEXT_HEADER)
    manifest = {
        "schema_version": 1,
        "job_name": "research_stock_context_batch_export",
        "source_query_owner": "workflows/jobs/daily_strategy_signal_production.py::_stock_context_sql",
        "output_path": str(output_path),
        "trade_dates": list(normalized_trade_dates),
        "trade_date_count": len(normalized_trade_dates),
        "row_count": len(rows),
        "rows_by_trade_date": rows_by_trade_date,
        "columns": list(STOCK_CONTEXT_HEADER),
    }
    if manifest_path is not None:
        write_json_payload(manifest_path, manifest)
    return manifest


def _resolve_trade_dates(
    *,
    connection: Any,
    explicit_trade_dates: Sequence[str],
    start_date: str | None,
    end_date: str | None,
) -> tuple[str, ...]:
    if explicit_trade_dates:
        return _normalize_trade_dates(explicit_trade_dates)
    if not start_date or not end_date:
        raise ValueError("either --trade-date or both --start-date and --end-date must be provided")
    rows = _fetch_rows(
        connection,
        """
        SELECT trade_date
        FROM token_daily_details
        WHERE trade_date BETWEEN %s AND %s
        GROUP BY trade_date
        ORDER BY trade_date
        """,
        (start_date, end_date),
    )
    trade_dates = tuple(str(row["trade_date"]) for row in rows)
    if not trade_dates:
        raise ValueError(f"cannot resolve trade dates between {start_date} and {end_date}")
    return trade_dates


def _normalize_trade_dates(trade_dates: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(sorted(dict.fromkeys(str(trade_date) for trade_date in trade_dates if str(trade_date))))
    if not normalized:
        raise ValueError("at least one trade date is required")
    return normalized


if __name__ == "__main__":
    raise SystemExit(main())
