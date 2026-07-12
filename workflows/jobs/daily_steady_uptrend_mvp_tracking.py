"""End-to-end routine orchestration for steady-uptrend MVP tracking."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import fcntl
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
from workflows.jobs.daily_strategy_signal_production import (
    _fetch_rows,
    _stock_context_sql,
)
from workflows.jobs.research_kline_batch_export import (
    _fetch_kline_rows,
    export_kline_batch,
)
from workflows.jobs.research_stock_context_batch_export import (
    export_stock_context_batch,
)
from workflows.jobs.steady_uptrend_s1_s5_mvp_scan import main as scanner_main
from workflows.jobs.support import utc_now_iso


DAILY_QUALITY_PRODUCTS = (
    "pub_stock_daily_kline",
    "pub_stock_daily_basic",
    "pub_stock_daily_indicator",
    "pub_stock_asset_basic",
)
WEEKLY_QUALITY_PRODUCT = "pub_stock_weekly_kline"


@dataclass(frozen=True, slots=True)
class ResolvedReadiness:
    """The selected signal date and its exact external quality evidence."""

    trade_date: str
    weekly_trade_date: str
    statuses: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class TrackingSchedule:
    """Filesystem and lookback settings for one routine tracking job."""

    mysql_config_path: Path
    strategy_registry_path: Path
    strategy_config_path: Path
    run_root: Path
    report_root: Path
    job_result_root: Path
    latest_result_path: Path
    lock_path: Path
    daily_lookback_calendar_days: int
    weekly_lookback_calendar_days: int
    price_basis: str

    @classmethod
    def load(cls, path: str | Path) -> "TrackingSchedule":
        payload = _read_json_object(path)
        if payload.get("enabled") is not True:
            raise ValueError("MVP tracking schedule must be enabled")
        if payload.get("status") != "test_tracking":
            raise ValueError("MVP tracking schedule status must be test_tracking")
        if payload.get("job") != "workflows/jobs/daily_steady_uptrend_mvp_tracking.py":
            raise ValueError("MVP tracking schedule job path is invalid")
        price_basis = str(payload.get("price_basis") or "")
        if price_basis != "qfq_asof":
            raise ValueError("MVP tracking price_basis must be qfq_asof")
        return cls(
            mysql_config_path=Path(_required_string(payload, "mysql_config_path")),
            strategy_registry_path=Path(
                _required_string(payload, "strategy_registry_path")
            ),
            strategy_config_path=Path(
                _required_string(payload, "strategy_config_path")
            ),
            run_root=Path(_required_string(payload, "run_root")),
            report_root=Path(_required_string(payload, "report_root")),
            job_result_root=Path(_required_string(payload, "job_result_root")),
            latest_result_path=Path(
                _required_string(payload, "latest_result_path")
            ),
            lock_path=Path(_required_string(payload, "lock_path")),
            daily_lookback_calendar_days=_positive_int(
                payload, "daily_lookback_calendar_days"
            ),
            weekly_lookback_calendar_days=_positive_int(
                payload, "weekly_lookback_calendar_days"
            ),
            price_basis=price_basis,
        )


@dataclass(frozen=True, slots=True)
class PipelineDependencies:
    """Injectable technical stage functions used by the routine orchestrator."""

    fetch_quality_rows: Callable[[Any, str | None], Sequence[Mapping[str, object]]]
    export_kline: Callable[..., Mapping[str, object]]
    export_context: Callable[..., Mapping[str, object]]
    run_scanner: Callable[[list[str]], int]


@dataclass(frozen=True, slots=True)
class RoutineStrategy:
    strategy_id: str
    version: str
    status: str
    selection_job: str


class PipelineStageError(RuntimeError):
    """Failure tagged with the technical stage and known trade date."""

    def __init__(
        self,
        stage: str,
        cause: Exception,
        *,
        trade_date: str | None = None,
    ) -> None:
        super().__init__(str(cause))
        self.stage = stage
        self.cause = cause
        self.trade_date = trade_date


def resolve_readiness(
    rows: Sequence[Mapping[str, object]],
    requested_date: str | None = None,
) -> ResolvedReadiness:
    """Select the newest complete daily gate and compatible weekly gate."""

    by_key: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for raw in rows:
        item = dict(raw)
        key = (
            str(item.get("data_product") or ""),
            str(item.get("data_date") or ""),
            str(item.get("market") or ""),
            str(item.get("asset_type") or ""),
        )
        if key in by_key:
            raise ValueError(
                "duplicate quality status for "
                f"{key[0]}.{key[1]}.{key[2]}.{key[3]}"
            )
        by_key[key] = item

    target_rows = tuple(
        item
        for key, item in by_key.items()
        if key[2:] == ("CN_A", "stock")
    )
    available_dates = sorted(
        {
            str(item["data_date"])
            for item in target_rows
            if item.get("data_product") in DAILY_QUALITY_PRODUCTS
        },
        reverse=True,
    )
    candidate_dates = (
        (requested_date,)
        if requested_date is not None
        else tuple(available_dates)
    )

    selected_daily: tuple[dict[str, object], ...] | None = None
    trade_date = ""
    for candidate_date in candidate_dates:
        candidates = {
            str(item["data_product"]): item
            for item in target_rows
            if str(item.get("data_date")) == candidate_date
            and item.get("data_product") in DAILY_QUALITY_PRODUCTS
            and _is_ready(item)
            and str(item.get("source_end_date") or "") == candidate_date
            and str(item.get("data_version") or "")
        }
        if set(candidates) == set(DAILY_QUALITY_PRODUCTS):
            trade_date = candidate_date
            selected_daily = tuple(
                candidates[product] for product in DAILY_QUALITY_PRODUCTS
            )
            break

    if selected_daily is None:
        label = requested_date or "available dates"
        raise ValueError(f"quality readiness is incomplete for {label}")

    weekly_candidates = [
        item
        for item in target_rows
        if item.get("data_product") == WEEKLY_QUALITY_PRODUCT
        and _is_ready(item)
        and str(item.get("data_version") or "")
        and str(item.get("source_end_date") or "") <= trade_date
        and str(item.get("data_date") or "")
        == str(item.get("source_end_date") or "")
    ]
    if not weekly_candidates:
        raise ValueError(f"weekly quality readiness is missing for {trade_date}")
    weekly = max(
        weekly_candidates,
        key=lambda item: (
            str(item["source_end_date"]),
            str(item["data_date"]),
        ),
    )
    weekly_trade_date = str(weekly["source_end_date"])
    return ResolvedReadiness(
        trade_date=trade_date,
        weekly_trade_date=weekly_trade_date,
        statuses=(*selected_daily, weekly),
    )


def _is_ready(item: Mapping[str, object]) -> bool:
    return item.get("status") == "ready" and item.get("quality_level") == "pass"


def resolve_routine_strategy(
    registry_path: str | Path,
    strategy_config_path: str | Path,
) -> RoutineStrategy:
    """Resolve and validate the sole enabled business strategy binding."""

    registry = _read_json_object(registry_path)
    entries = registry.get("strategies")
    if not isinstance(entries, list):
        raise ValueError("strategy registry strategies must be a JSON array")
    enabled = [
        entry
        for entry in entries
        if isinstance(entry, Mapping)
        and entry.get("routine_selection_enabled") is True
    ]
    if len(enabled) != 1:
        raise ValueError("strategy registry must enable exactly one routine strategy")
    entry = enabled[0]
    config = _read_json_object(strategy_config_path)
    values = {
        "strategy_id": _required_string(entry, "strategy_id"),
        "version": _required_string(entry, "version"),
        "status": _required_string(entry, "status"),
    }
    if values["status"] != "test_tracking":
        raise ValueError("routine strategy status must be test_tracking")
    for key, value in values.items():
        if config.get(key) != value:
            raise ValueError(f"strategy registry/config {key} mismatch")
    selection_job = _required_string(entry, "selection_job")
    if selection_job != "workflows/jobs/steady_uptrend_s1_s5_mvp_scan.py":
        raise ValueError("routine strategy selection_job is not approved")
    return RoutineStrategy(selection_job=selection_job, **values)


def execute_tracking_job(
    schedule: TrackingSchedule,
    *,
    connection: Any,
    requested_date: str | None = None,
    dependencies: PipelineDependencies | None = None,
) -> tuple[int, dict[str, object]]:
    """Run one locked job and persist success or failure status."""

    deps = dependencies or _default_dependencies()
    schedule.lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = schedule.lock_path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            result = _failure_result(
                stage="acquire_lock",
                cause=exc,
                trade_date=requested_date,
            )
            _write_job_result(schedule, requested_date, result)
            return 1, result

        try:
            result = run_tracking_pipeline(
                schedule,
                connection=connection,
                requested_date=requested_date,
                dependencies=deps,
            )
            return 0, result
        except PipelineStageError as exc:
            result = _failure_result(
                stage=exc.stage,
                cause=exc.cause,
                trade_date=exc.trade_date or requested_date,
            )
            _write_job_result(
                schedule,
                exc.trade_date or requested_date,
                result,
            )
            return 1, result
    finally:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        finally:
            lock_handle.close()


def run_tracking_pipeline(
    schedule: TrackingSchedule,
    *,
    connection: Any,
    requested_date: str | None,
    dependencies: PipelineDependencies,
) -> dict[str, object]:
    """Build inputs, run the selected strategy, and publish its report."""

    stage = "resolve_strategy"
    trade_date: str | None = requested_date
    try:
        strategy = resolve_routine_strategy(
            schedule.strategy_registry_path,
            schedule.strategy_config_path,
        )
        stage = "resolve_readiness"
        readiness = resolve_readiness(
            dependencies.fetch_quality_rows(connection, requested_date),
            requested_date=requested_date,
        )
        trade_date = readiness.trade_date
        run_dir = (
            schedule.run_root
            / "runs"
            / trade_date
            / strategy.strategy_id
            / strategy.version
        )
        input_dir = run_dir / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        quality_path = input_dir / "quality_status.json"
        _write_json(quality_path, {"statuses": list(readiness.statuses)})

        signal_day = datetime.strptime(trade_date, "%Y%m%d").date()
        daily_start = (
            signal_day - timedelta(days=schedule.daily_lookback_calendar_days)
        ).strftime("%Y%m%d")
        weekly_start = (
            signal_day - timedelta(days=schedule.weekly_lookback_calendar_days)
        ).strftime("%Y%m%d")

        daily_path = input_dir / "kline.tsv"
        weekly_path = input_dir / "weekly_kline.tsv"
        kline_manifest_path = input_dir / "kline_manifest.json"
        stage = "export_kline"
        kline_manifest = dict(
            dependencies.export_kline(
                connection=connection,
                daily_start_date=daily_start,
                daily_end_date=trade_date,
                weekly_start_date=weekly_start,
                weekly_end_date=trade_date,
                daily_output_path=daily_path,
                weekly_output_path=weekly_path,
                manifest_path=kline_manifest_path,
                price_basis=schedule.price_basis,
            )
        )

        context_path = input_dir / "stock_context.tsv"
        context_manifest_path = input_dir / "stock_context_manifest.json"
        stage = "export_context"
        context_manifest = dict(
            dependencies.export_context(
                connection=connection,
                trade_dates=(trade_date,),
                output_path=context_path,
                manifest_path=context_manifest_path,
            )
        )

        run_id = _deterministic_run_id(
            strategy,
            trade_date,
            kline_manifest,
            context_manifest,
        )
        result_path = run_dir / "result.json"
        markdown_path = run_dir / "report.md"
        stage = "scan"
        exit_code = dependencies.run_scanner(
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
                str(quality_path),
                "--strategy-config-path",
                str(schedule.strategy_config_path),
                "--signal-date",
                trade_date,
                "--run-id",
                run_id,
                "--output-path",
                str(result_path),
                "--markdown-output-path",
                str(markdown_path),
            ]
        )
        if exit_code != 0:
            raise RuntimeError(f"MVP scanner exited with code {exit_code}")
        scan_payload = _read_json_object(result_path)
        candidates = scan_payload.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("MVP scan result candidates must be a JSON array")

        stage = "publish"
        job_result: dict[str, object] = {
            "schema_version": 1,
            "job_name": "daily_steady_uptrend_mvp_tracking",
            "status": "success",
            "finished_at": utc_now_iso(),
            "trade_date": trade_date,
            "strategy_id": strategy.strategy_id,
            "strategy_version": strategy.version,
            "strategy_status": strategy.status,
            "run_id": run_id,
            "candidate_count": len(candidates),
            "stage_counts": scan_payload.get("stage_counts", {}),
            "data_dependency_versions": scan_payload.get(
                "data_dependency_versions", {}
            ),
            "run_dir": str(run_dir),
            "report_dir": str(schedule.report_root / trade_date),
        }
        _publish_success(
            schedule,
            trade_date=trade_date,
            result_path=result_path,
            markdown_path=markdown_path,
            job_result=job_result,
        )
        _write_job_result(schedule, trade_date, job_result)
        _write_json(run_dir / "job_result.json", job_result)
        return job_result
    except PipelineStageError:
        raise
    except Exception as exc:
        raise PipelineStageError(stage, exc, trade_date=trade_date) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="daily_steady_uptrend_mvp_tracking")
    parser.add_argument("--schedule-config-path", required=True)
    parser.add_argument("--date")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    connection: Any | None = None
    schedule: TrackingSchedule | None = None
    try:
        schedule = TrackingSchedule.load(args.schedule_config_path)
        config = MysqlConnectionConfig.load_json(schedule.mysql_config_path)
        adapter = ExternalMysqlAdapter.from_config(config)
        if adapter.connection_factory is None:
            raise ValueError("mysql connection factory is required")
        connection = adapter.connection_factory()
        exit_code, result = execute_tracking_job(
            schedule,
            connection=connection,
            requested_date=args.date,
        )
    except Exception as exc:
        exit_code = 1
        result = _failure_result(
            stage="initialize",
            cause=exc,
            trade_date=args.date,
        )
        if schedule is not None:
            _write_job_result(schedule, args.date, result)
    finally:
        if connection is not None:
            close = getattr(connection, "close", None)
            if callable(close):
                close()
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return exit_code


def _default_dependencies() -> PipelineDependencies:
    return PipelineDependencies(
        fetch_quality_rows=_fetch_quality_status_rows,
        export_kline=_export_kline_inputs,
        export_context=_export_context_input,
        run_scanner=lambda arguments: scanner_main(arguments),
    )


def _fetch_quality_status_rows(
    connection: Any,
    requested_date: str | None,
) -> tuple[Mapping[str, object], ...]:
    sql = """
SELECT
  data_product, data_date, market, asset_type, status, quality_level,
  record_count, expected_min_records, source_tables, source_end_date,
  published_at, data_version, error_message
FROM pub_data_quality_status
WHERE market = %s
  AND asset_type = %s
  AND data_product IN (%s, %s, %s, %s, %s)
"""
    params: list[object] = [
        "CN_A",
        "stock",
        *DAILY_QUALITY_PRODUCTS,
        WEEKLY_QUALITY_PRODUCT,
    ]
    if requested_date is not None:
        sql += " AND data_date <= %s"
        params.append(requested_date)
    sql += " ORDER BY data_date DESC, data_product"
    rows = _fetch_rows(connection, sql, tuple(params))
    return tuple(_json_safe_mapping(row) for row in rows)


def _export_kline_inputs(**kwargs: object) -> Mapping[str, object]:
    connection = kwargs.pop("connection")
    price_basis = str(kwargs["price_basis"])
    return export_kline_batch(
        fetch_rows=lambda table_name, start_date, end_date: _fetch_kline_rows(
            connection=connection,
            table_name=table_name,
            start_date=start_date,
            end_date=end_date,
            price_basis=price_basis,
        ),
        **kwargs,
    )


def _export_context_input(**kwargs: object) -> Mapping[str, object]:
    connection = kwargs.pop("connection")
    return export_stock_context_batch(
        fetch_rows_for_date=lambda trade_date: _fetch_rows(
            connection,
            _stock_context_sql(),
            {"signal_date": trade_date},
        ),
        **kwargs,
    )


def _publish_success(
    schedule: TrackingSchedule,
    *,
    trade_date: str,
    result_path: Path,
    markdown_path: Path,
    job_result: Mapping[str, object],
) -> None:
    report_dir = schedule.report_root / trade_date
    report_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(
        report_dir / "candidates.json",
        result_path.read_text(encoding="utf-8"),
    )
    _atomic_write_text(
        report_dir / "report.md",
        markdown_path.read_text(encoding="utf-8"),
    )
    _atomic_write_json(report_dir / "job_result.json", job_result)
    latest = {
        "schema_version": 1,
        "trade_date": trade_date,
        "strategy_id": job_result["strategy_id"],
        "strategy_version": job_result["strategy_version"],
        "report_dir": str(report_dir),
        "job_result_path": str(report_dir / "job_result.json"),
    }
    _atomic_write_json(schedule.latest_result_path, latest)


def _write_job_result(
    schedule: TrackingSchedule,
    trade_date: str | None,
    payload: Mapping[str, object],
) -> None:
    result_date = trade_date or date.today().strftime("%Y%m%d")
    _atomic_write_json(schedule.job_result_root / f"{result_date}.json", payload)


def _failure_result(
    *,
    stage: str,
    cause: Exception,
    trade_date: str | None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "job_name": "daily_steady_uptrend_mvp_tracking",
        "status": "failed",
        "finished_at": utc_now_iso(),
        "trade_date": trade_date,
        "failed_stage": stage,
        "error_type": type(cause).__name__,
        "error_message": str(cause),
    }


def _deterministic_run_id(
    strategy: RoutineStrategy,
    trade_date: str,
    kline_manifest: Mapping[str, object],
    context_manifest: Mapping[str, object],
) -> str:
    identity = "|".join(
        (
            strategy.strategy_id,
            strategy.version,
            trade_date,
            str(kline_manifest.get("daily_sha256") or ""),
            str(kline_manifest.get("weekly_sha256") or ""),
            str(context_manifest.get("sha256") or ""),
        )
    )
    return f"steady-uptrend-mvp-{hashlib.sha256(identity.encode()).hexdigest()[:16]}"


def _read_json_object(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return dict(payload)


def _required_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _positive_int(payload: Mapping[str, object], key: str) -> int:
    value = int(payload.get(key, 0))
    if value <= 0:
        raise ValueError(f"{key} must be positive")
    return value


def _json_safe_mapping(payload: Mapping[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key, value in payload.items():
        if isinstance(value, datetime):
            normalized[key] = value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, date):
            normalized[key] = value.strftime("%Y%m%d")
        else:
            normalized[key] = value
    return normalized


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    _atomic_write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
    )


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
