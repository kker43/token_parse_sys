"""Routine job for producing daily strategy signal reports."""

from __future__ import annotations

import argparse
import csv
from dataclasses import fields
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.core.ids import new_run_id
from stock_lobster.l0_data_access.adapters.external_mysql import (
    ExternalMysqlAdapter,
    MysqlConnectionConfig,
)
from stock_lobster.research import (
    TrendBreakoutScanPolicy,
    read_kline_tsv,
    read_stock_signal_context_tsv,
    scan_trend_breakouts,
    select_candidates,
    summarize_breakout_scan,
)
from workflows.jobs.support import utc_now_iso, write_json_payload

DEFAULT_LOOKBACK_DAILY_TRADE_DAYS = 280
DEFAULT_LOOKBACK_WEEKLY_TRADE_DAYS = 120


def build_parser() -> argparse.ArgumentParser:
    """Build parser for the routine strategy signal production job."""

    parser = argparse.ArgumentParser(prog="daily_strategy_signal_production")
    parser.add_argument("--schedule-config-path")
    parser.add_argument("--mysql-config-path")
    parser.add_argument("--strategy-config-path")
    parser.add_argument("--output-root")
    parser.add_argument("--date")
    parser.add_argument("--job-result-path")
    parser.add_argument("--price-basis", choices=("raw", "qfq_asof"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Produce one deterministic daily strategy signal package."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    run_id = str(new_run_id(prefix="job"))
    started_at = utc_now_iso()
    settings: dict[str, object] = {}
    try:
        settings = _resolve_settings(args)
        connection_config = MysqlConnectionConfig.load_json(str(settings["mysql_config_path"]))
        adapter = ExternalMysqlAdapter.from_config(connection_config)
        if adapter.connection_factory is None:
            raise ValueError("mysql connection factory is required")

        connection = adapter.connection_factory()
        try:
            trade_date = str(settings["date"] or _latest_trade_date(connection))
            day_dir = Path(str(settings["output_root"])) / trade_date
            input_dir = day_dir / "input"
            input_dir.mkdir(parents=True, exist_ok=True)

            daily_path = input_dir / "kline.tsv"
            weekly_path = input_dir / "weekly_kline.tsv"
            context_path = input_dir / "stock_context.tsv"
            _export_daily_kline(
                connection=connection,
                trade_date=trade_date,
                lookback_trade_days=int(settings["lookback_daily_trade_days"]),
                price_basis=str(settings["price_basis"]),
                output_path=daily_path,
            )
            _export_weekly_kline(
                connection=connection,
                trade_date=trade_date,
                lookback_trade_days=int(settings["lookback_weekly_trade_days"]),
                price_basis=str(settings["price_basis"]),
                output_path=weekly_path,
            )
            _export_stock_context(connection=connection, trade_date=trade_date, output_path=context_path)

            strategy_payload = _read_json_object(str(settings["strategy_config_path"]))
            scan_policy = _policy_from_strategy_payload(strategy_payload, trade_date)
            scan_config = strategy_payload.get("candidate_scan_policy", {})
            if not isinstance(scan_config, Mapping):
                raise ValueError("strategy candidate_scan_policy must be a JSON object")
            candidate_mode = str(scan_config.get("candidate_mode", "pre_breakout"))
            top_n_raw = scan_config.get("top_n_per_date")
            top_n_per_date = int(top_n_raw) if top_n_raw is not None else None

            metrics = scan_trend_breakouts(
                bars=read_kline_tsv(daily_path),
                policy=scan_policy,
                weekly_bars=read_kline_tsv(weekly_path),
                stock_contexts=read_stock_signal_context_tsv(context_path),
            )
            candidates = select_candidates(metrics, mode=candidate_mode, top_n_per_date=top_n_per_date)
            candidate_payloads = [candidate.to_mapping() for candidate in candidates]
            summary = summarize_breakout_scan(metrics)

            candidates_json_path = day_dir / "candidates.json"
            candidates_csv_path = day_dir / "candidates.csv"
            report_path = day_dir / "report.md"
            result_path = Path(str(settings["job_result_path"]))
            payload = {
                "schema_version": 1,
                "job_name": "daily_strategy_signal_production",
                "run_id": run_id,
                "status": "success",
                "started_at": started_at,
                "finished_at": utc_now_iso(),
                "trade_date": trade_date,
                "strategy_id": strategy_payload.get("strategy_id"),
                "strategy_version": strategy_payload.get("version"),
                "candidate_mode": candidate_mode,
                "price_basis": settings["price_basis"],
                "top_n_per_date": top_n_per_date,
                "candidate_count": len(candidate_payloads),
                "metric_count": len(metrics),
                "input_paths": {
                    "daily_kline_tsv": str(daily_path),
                    "weekly_kline_tsv": str(weekly_path),
                    "stock_context_tsv": str(context_path),
                },
                "output_paths": {
                    "candidates_json": str(candidates_json_path),
                    "candidates_csv": str(candidates_csv_path),
                    "report_md": str(report_path),
                    "job_result": str(result_path),
                },
                "policy": _policy_to_mapping(scan_policy),
                "summary": summary,
                "candidates": candidate_payloads,
            }
            write_json_payload(candidates_json_path, payload)
            _write_candidates_csv(candidates_csv_path, candidate_payloads)
            _write_markdown_report(report_path, payload)
            write_json_payload(result_path, payload)
            _print_json(
                {
                    "status": "success",
                    "trade_date": trade_date,
                    "candidate_count": len(candidate_payloads),
                    "report_path": str(report_path),
                }
            )
            return 0
        finally:
            close_connection = getattr(connection, "close", None)
            if callable(close_connection):
                close_connection()
    except Exception as exc:  # pragma: no cover - integration failure branch
        result = {
            "schema_version": 1,
            "job_name": "daily_strategy_signal_production",
            "run_id": run_id,
            "status": "failed",
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "error_message": str(exc),
            "settings": settings,
        }
        result_path = str(settings.get("job_result_path") or args.job_result_path or "")
        if result_path:
            write_json_payload(result_path, result)
        _print_json(result)
        return 1


def _resolve_settings(args: argparse.Namespace) -> dict[str, object]:
    config: dict[str, object] = {}
    config_dir = PROJECT_ROOT
    if args.schedule_config_path:
        config_path = Path(args.schedule_config_path).resolve()
        config = _read_json_object(config_path)
        if config.get("enabled") is False:
            raise ValueError("daily strategy signal production schedule is disabled")
        config_dir = config_path.parent

    mysql_config_path = args.mysql_config_path or _resolve_path(config.get("mysql_config_path"), config_dir)
    strategy_config_path = args.strategy_config_path or _resolve_path(config.get("strategy_config_path"), config_dir)
    output_root = args.output_root or _resolve_path(config.get("output_root"), config_dir)
    job_result_path = args.job_result_path or _resolve_path(config.get("job_result_path"), config_dir)
    price_basis = args.price_basis or str(config.get("price_basis", "raw"))
    if price_basis not in {"raw", "qfq_asof"}:
        raise ValueError("price_basis must be raw or qfq_asof")
    if mysql_config_path is None:
        raise ValueError("mysql_config_path must be provided")
    if strategy_config_path is None:
        raise ValueError("strategy_config_path must be provided")
    if output_root is None:
        raise ValueError("output_root must be provided")
    if job_result_path is None:
        job_result_path = str(Path(output_root) / "latest_result.json")

    return {
        "schedule_config_path": str(Path(args.schedule_config_path).resolve()) if args.schedule_config_path else None,
        "mysql_config_path": mysql_config_path,
        "strategy_config_path": strategy_config_path,
        "output_root": output_root,
        "date": args.date or config.get("date"),
        "job_result_path": job_result_path,
        "price_basis": price_basis,
        "lookback_daily_trade_days": int(
            config.get("lookback_daily_trade_days", DEFAULT_LOOKBACK_DAILY_TRADE_DAYS)
        ),
        "lookback_weekly_trade_days": int(
            config.get("lookback_weekly_trade_days", DEFAULT_LOOKBACK_WEEKLY_TRADE_DAYS)
        ),
    }


def _resolve_path(value: object, base_dir: Path) -> str | None:
    if value is None:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return str(path)


def _read_json_object(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return dict(payload)


def _policy_from_strategy_payload(
    strategy_payload: Mapping[str, object],
    trade_date: str,
) -> TrendBreakoutScanPolicy:
    raw_policy = strategy_payload.get("candidate_scan_policy", {})
    if not isinstance(raw_policy, Mapping):
        raise ValueError("strategy candidate_scan_policy must be a JSON object")
    allowed_fields = {field.name for field in fields(TrendBreakoutScanPolicy)}
    policy_values = {key: value for key, value in raw_policy.items() if key in allowed_fields}
    policy_values["start_date"] = trade_date
    return TrendBreakoutScanPolicy(**policy_values)


def _policy_to_mapping(policy: TrendBreakoutScanPolicy) -> dict[str, object]:
    return {field.name: getattr(policy, field.name) for field in fields(TrendBreakoutScanPolicy)}


def _latest_trade_date(connection: Any) -> str:
    rows = _fetch_rows(connection, "SELECT MAX(trade_date) AS trade_date FROM token_daily_details", ())
    if not rows or rows[0].get("trade_date") is None:
        raise ValueError("cannot resolve latest trade_date from token_daily_details")
    return str(rows[0]["trade_date"])


def _trade_day_bounds(connection: Any, table_name: str, trade_date: str, limit: int) -> tuple[str, str]:
    sql = (
        f"SELECT trade_date FROM {table_name} "
        "WHERE trade_date <= %s GROUP BY trade_date ORDER BY trade_date DESC LIMIT %s"
    )
    rows = _fetch_rows(connection, sql, (trade_date, limit))
    if not rows:
        raise ValueError(f"cannot resolve trade days from {table_name} before {trade_date}")
    dates = sorted(str(row["trade_date"]) for row in rows)
    return dates[0], dates[-1]


def _export_daily_kline(
    *,
    connection: Any,
    trade_date: str,
    lookback_trade_days: int,
    price_basis: str,
    output_path: Path,
) -> None:
    start_date, end_date = _trade_day_bounds(
        connection,
        "token_daily_details",
        trade_date,
        lookback_trade_days,
    )
    rows = _fetch_kline_rows(
        connection=connection,
        table_name="token_daily_details",
        signal_date=trade_date,
        start_date=start_date,
        end_date=end_date,
        price_basis=price_basis,
    )
    _write_tsv(output_path, rows, header=None)


def _export_weekly_kline(
    *,
    connection: Any,
    trade_date: str,
    lookback_trade_days: int,
    price_basis: str,
    output_path: Path,
) -> None:
    start_date, end_date = _trade_day_bounds(
        connection,
        "token_weekly_details",
        trade_date,
        lookback_trade_days,
    )
    rows = _fetch_kline_rows(
        connection=connection,
        table_name="token_weekly_details",
        signal_date=trade_date,
        start_date=start_date,
        end_date=end_date,
        price_basis=price_basis,
    )
    _write_tsv(output_path, rows, header=None)


def _fetch_kline_rows(
    *,
    connection: Any,
    table_name: str,
    signal_date: str,
    start_date: str,
    end_date: str,
    price_basis: str,
) -> tuple[Mapping[str, object], ...]:
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
    return _fetch_rows(
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
        ORDER BY k.ts_code, k.trade_date
        """,
        (signal_date, start_date, end_date),
    )


def _export_stock_context(*, connection: Any, trade_date: str, output_path: Path) -> None:
    rows = _fetch_rows(connection, _stock_context_sql(), {"signal_date": trade_date})
    _write_tsv(
        output_path,
        rows,
        header=(
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
            "volume_ratio_5d_20d",
            "max_volume_ratio_5d_20d",
            "turnover_ratio_5d_20d",
            "adj_factor_changed_20d",
        ),
    )


def _stock_context_sql() -> str:
    signal_expr = "CAST(%(signal_date)s AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci"
    return f"""
WITH
trade_days AS (
  SELECT trade_date
  FROM token_daily_details
  WHERE trade_date <= {signal_expr}
  GROUP BY trade_date
  ORDER BY trade_date DESC
  LIMIT 80
),
ranked_days AS (
  SELECT trade_date, ROW_NUMBER() OVER (ORDER BY trade_date DESC) AS rn
  FROM trade_days
),
signal_days AS (
  SELECT trade_date FROM ranked_days WHERE rn <= 20
),
recent5_days AS (
  SELECT trade_date FROM ranked_days WHERE rn <= 5
),
index_series AS (
  SELECT d.ts_code, d.trade_date, d.close
  FROM ths_daily_daily d
  JOIN ths_index_daily i
    ON i.trade_date = {signal_expr}
   AND i.ts_code = d.ts_code
   AND i.exchange = 'A'
   AND i.type IN ('I','N')
  WHERE d.trade_date IN (SELECT trade_date FROM ranked_days)
),
index_signal AS (
  SELECT
    i.type,
    i.ts_code,
    i.name,
    MAX(CASE WHEN s.trade_date = {signal_expr} THEN s.close END) AS close_now,
    AVG(CASE WHEN rd.rn BETWEEN 1 AND 20 THEN s.close END) AS ma20,
    AVG(CASE WHEN rd.rn BETWEEN 1 AND 60 THEN s.close END) AS ma60,
    MAX(CASE WHEN rd.rn = 21 THEN s.close END) AS close_20d_ago
  FROM ths_index_daily i
  JOIN index_series s ON s.ts_code = i.ts_code
  JOIN ranked_days rd ON rd.trade_date = s.trade_date
  WHERE i.trade_date = {signal_expr}
    AND i.exchange = 'A'
    AND i.type IN ('I','N')
  GROUP BY i.type, i.ts_code, i.name
  HAVING close_now IS NOT NULL AND close_20d_ago IS NOT NULL AND ma20 IS NOT NULL AND ma60 IS NOT NULL
),
trend_ranked AS (
  SELECT
    index_signal.*,
    close_now / close_20d_ago - 1 AS return_20d,
    PERCENT_RANK() OVER (PARTITION BY type ORDER BY close_now / close_20d_ago - 1 DESC) AS return_rank_pct
  FROM index_signal
),
trend_strong AS (
  SELECT type, ts_code, name
  FROM trend_ranked
  WHERE return_rank_pct <= 0.30
    AND close_now > ma20
    AND close_now > ma60
),
top200_gainers AS (
  SELECT trade_date, ts_code
  FROM (
    SELECT
      d.trade_date,
      d.ts_code,
      d.pct_chg,
      ROW_NUMBER() OVER (PARTITION BY d.trade_date ORDER BY d.pct_chg DESC) AS rn
    FROM token_daily_details d
    JOIN token_stock_basic b
      ON b.ts_code = d.ts_code
     AND b.update_date = {signal_expr}
     AND b.list_status = 'L'
    WHERE d.trade_date IN (SELECT trade_date FROM signal_days)
      AND d.pct_chg IS NOT NULL
      AND b.exchange IN ('SSE', 'SZSE', 'BSE')
      AND b.name NOT LIKE '%%ST%%'
  ) ranked
  WHERE rn <= 200
),
heat_daily_counts AS (
  SELECT
    g.trade_date,
    i.type,
    m.ts_code,
    i.name,
    COUNT(*) AS member_hits,
    COUNT(*) / NULLIF(i.count, 0) AS member_hit_ratio
  FROM top200_gainers g
  JOIN ths_member_daily m
    ON m.trade_date = g.trade_date
   AND m.con_code = g.ts_code
  JOIN ths_index_daily i
    ON i.trade_date = g.trade_date
   AND i.ts_code = m.ts_code
   AND i.exchange = 'A'
   AND i.type IN ('I','N')
  GROUP BY g.trade_date, i.type, m.ts_code, i.name, i.count
),
heat_daily_ranked AS (
  SELECT
    heat_daily_counts.*,
    ROW_NUMBER() OVER (PARTITION BY trade_date, type ORDER BY member_hit_ratio DESC, member_hits DESC, ts_code) AS heat_rank
  FROM heat_daily_counts
),
heat_top5 AS (
  SELECT trade_date, type, ts_code, name
  FROM heat_daily_ranked
  WHERE heat_rank <= 5
),
heat_strong AS (
  SELECT
    h.type,
    h.ts_code,
    MAX(h.name) AS name,
    COUNT(*) AS hit_count_20d,
    SUM(CASE WHEN h.trade_date IN (SELECT trade_date FROM recent5_days) THEN 1 ELSE 0 END) AS hit_count_5d
  FROM heat_top5 h
  GROUP BY h.type, h.ts_code
  HAVING hit_count_20d >= 3 AND hit_count_5d >= 1
),
strong_index AS (
  SELECT type, ts_code, name, 'trend' AS reason FROM trend_strong
  UNION ALL
  SELECT type, ts_code, name, 'heat' AS reason FROM heat_strong
),
strong_index_dedup AS (
  SELECT type, ts_code, MAX(name) AS name
  FROM strong_index
  GROUP BY type, ts_code
),
member_hit AS (
  SELECT
    m.con_code AS ts_code,
    MAX(CASE WHEN s.type = 'I' THEN 1 ELSE 0 END) AS strong_industry_hit,
    MAX(CASE WHEN s.type = 'N' THEN 1 ELSE 0 END) AS strong_concept_hit,
    GROUP_CONCAT(DISTINCT CASE WHEN s.type = 'I' THEN s.name END ORDER BY s.name SEPARATOR ',') AS strong_industry_names,
    GROUP_CONCAT(DISTINCT CASE WHEN s.type = 'N' THEN s.name END ORDER BY s.name SEPARATOR ',') AS strong_concept_names
  FROM ths_member_daily m
  JOIN strong_index_dedup s ON s.ts_code = m.ts_code
  WHERE m.trade_date = {signal_expr}
  GROUP BY m.con_code
),
turnover_20d AS (
  SELECT
    db.ts_code,
    MAX(db.turnover_rate) AS max_turnover_rate_20d,
    AVG(db.turnover_rate) AS avg_turnover_rate_20d
  FROM ranked_days dday
  JOIN token_daily_basic db ON db.trade_date = dday.trade_date
  WHERE dday.rn <= 20
  GROUP BY db.ts_code
),
amount_20d AS (
  SELECT d.ts_code, AVG(d.amount) AS avg_amount_20d
  FROM ranked_days dday
  JOIN token_daily_details d ON d.trade_date = dday.trade_date
  WHERE dday.rn <= 20
  GROUP BY d.ts_code
),
published_volume_ratio AS (
  SELECT
    asset_id,
    MAX(CASE WHEN indicator_name = 'volume_ratio_5d_20d' THEN indicator_value END) AS volume_ratio_5d_20d,
    MAX(CASE WHEN indicator_name = 'max_volume_ratio_5d_20d' THEN indicator_value END) AS max_volume_ratio_5d_20d,
    MAX(CASE WHEN indicator_name = 'turnover_ratio_5d_20d' THEN indicator_value END) AS turnover_ratio_5d_20d,
    MAX(CASE WHEN indicator_name = 'adj_factor_changed_20d' THEN indicator_value END) AS adj_factor_changed_20d
  FROM pub_stock_daily_indicator
  WHERE trade_date = {signal_expr}
    AND indicator_name IN (
      'volume_ratio_5d_20d',
      'max_volume_ratio_5d_20d',
      'turnover_ratio_5d_20d',
      'adj_factor_changed_20d'
    )
    AND indicator_version = 'legacy_v1'
    AND params_hash = 'default'
  GROUP BY asset_id
)
SELECT
  db.ts_code AS asset_id,
  {signal_expr} AS trade_date,
  b.name,
  b.industry,
  b.market,
  b.list_status,
  db.total_mv,
  db.turnover_rate,
  t.max_turnover_rate_20d,
  t.avg_turnover_rate_20d,
  a.avg_amount_20d,
  COALESCE(m.strong_industry_hit, 0) AS strong_industry_hit,
  COALESCE(m.strong_concept_hit, 0) AS strong_concept_hit,
  COALESCE(m.strong_industry_names, '') AS strong_industry_names,
  COALESCE(m.strong_concept_names, '') AS strong_concept_names,
  vr.volume_ratio_5d_20d,
  vr.max_volume_ratio_5d_20d,
  vr.turnover_ratio_5d_20d,
  COALESCE(vr.adj_factor_changed_20d, 0) AS adj_factor_changed_20d
FROM token_daily_basic db
JOIN token_stock_basic b ON b.ts_code = db.ts_code AND b.update_date = {signal_expr}
LEFT JOIN turnover_20d t ON t.ts_code = db.ts_code
LEFT JOIN amount_20d a ON a.ts_code = db.ts_code
LEFT JOIN member_hit m ON m.ts_code = db.ts_code
LEFT JOIN published_volume_ratio vr ON vr.asset_id = db.ts_code
WHERE db.trade_date = {signal_expr}
ORDER BY db.ts_code
"""


def _fetch_rows(connection: Any, sql: str, params: object) -> tuple[Mapping[str, object], ...]:
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        if not rows:
            return ()
        if isinstance(rows[0], Mapping):
            return tuple(dict(row) for row in rows)
        column_names = tuple(column[0] for column in (cursor.description or ()))
        return tuple(dict(zip(column_names, row)) for row in rows)
    finally:
        close = getattr(cursor, "close", None)
        if callable(close):
            close()


def _write_tsv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    header: Sequence[str] | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj, delimiter="\t", lineterminator="\n")
        if header is not None:
            writer.writerow(header)
            columns = tuple(header)
        elif rows:
            columns = tuple(rows[0].keys())
        else:
            columns = ()
        for row in rows:
            writer.writerow([_cell(row.get(column)) for column in columns])


def _write_candidates_csv(path: Path, candidates: Sequence[Mapping[str, object]]) -> None:
    columns = (
        "trade_date",
        "asset_id",
        "name",
        "industry",
        "close",
        "setup_score",
        "close_to_high_60d_pct",
        "ma30_deviation_pct",
        "ma30_hold_ratio_90d",
        "red_k_ratio_20d",
        "long_shadow_ratio_20d",
        "large_bearish_body_ratio_20d",
        "max_consecutive_green_k_20d",
        "single_bull_bar_return_share_20d",
        "impulse_consolidation_days",
        "ma5_10_20_30_convergence_pct",
        "weak_shape_pass",
        "volume_ratio_5d_20d",
        "amount_ratio_20d",
        "max_turnover_rate_20d",
        "strong_industry_hit",
        "strong_concept_hit",
        "strong_industry_names",
        "strong_concept_names",
        "weekly_asof_trade_date",
        "weekly_trend_pass",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for candidate in candidates:
            writer.writerow({column: _csv_cell(candidate.get(column)) for column in columns})


def _write_markdown_report(path: Path, payload: Mapping[str, object]) -> None:
    candidates = payload.get("candidates", ())
    if not isinstance(candidates, Sequence):
        candidates = ()
    lines = [
        f"# 每日策略候选报告 {payload.get('trade_date')}",
        "",
        "## 运行摘要",
        "",
        f"- 策略: `{payload.get('strategy_id')}` / `{payload.get('strategy_version')}`",
        f"- 候选模式: `{payload.get('candidate_mode')}`",
        f"- 扫描样本数: {payload.get('metric_count')}",
        f"- 候选数量: {payload.get('candidate_count')}",
        "",
        "## 当前筛选口径",
        "",
        "- 基础生产逻辑由 `token_fetch` 的 `daily_master_scheduler.py` 保持一致。",
        "- 本报告只消费基础事实数据和已注册上下文口径，不直接生产事实数据。",
        "- 过滤包含正常上市、总市值、20 日均成交额、20 日换手率、周级别趋势、强行业/强概念、MA30 稳健性、接近 60 日高点，以及可选的弱形态过滤。",
        "",
        "## 候选列表",
        "",
    ]
    if not candidates:
        lines.append("本次没有命中候选。")
    else:
        lines.append(
            "| 股票 | 名称 | 行业 | 收盘 | 分数 | 距60日高点 | MA30乖离 | MA30站上90日 | 红K比 | 大阴柱比 | 单阳主导 | 盘整天数 | 5/20日成交量比 | 强上下文 |"
        )
        lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
        for item in candidates:
            if not isinstance(item, Mapping):
                continue
            strong_context = ",".join(
                str(name)
                for name in (
                    list(item.get("strong_industry_names") or ())
                    + list(item.get("strong_concept_names") or ())
                )
            )
            lines.append(
                "| {asset_id} | {name} | {industry} | {close:.2f} | {score:.2f} | {high_gap:.2%} | {ma30_dev:.2%} | {ma30_hold:.2%} | {red_ratio:.2%} | {bearish_ratio:.2%} | {single_bull_share:.2%} | {consolidation_days} | {volume_ratio:.2f} | {strong_context} |".format(
                    asset_id=item.get("asset_id", ""),
                    name=item.get("name", ""),
                    industry=item.get("industry", ""),
                    close=float(item.get("close") or 0),
                    score=float(item.get("setup_score") or 0),
                    high_gap=float(item.get("close_to_high_60d_pct") or 0),
                    ma30_dev=float(item.get("ma30_deviation_pct") or 0),
                    ma30_hold=float(item.get("ma30_hold_ratio_90d") or 0),
                    red_ratio=float(item.get("red_k_ratio_20d") or 0),
                    bearish_ratio=float(item.get("large_bearish_body_ratio_20d") or 0),
                    single_bull_share=float(item.get("single_bull_bar_return_share_20d") or 0),
                    consolidation_days=int(item.get("impulse_consolidation_days") or 0),
                    volume_ratio=float(item.get("volume_ratio_5d_20d") or 0),
                    strong_context=strong_context,
                )
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cell(value: object) -> object:
    if value is None:
        return ""
    return value


def _csv_cell(value: object) -> object:
    if isinstance(value, (list, tuple)):
        return ";".join(str(item) for item in value)
    return _cell(value)


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
