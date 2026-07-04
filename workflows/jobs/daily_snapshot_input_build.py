"""Routine job for building L1 snapshot input from L0 MySQL assets."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.l0_data_access import DataAssetCatalogLoader
from stock_lobster.l0_data_access.adapters.external_mysql import ExternalMysqlAdapter
from stock_lobster.l1_analysis_snapshot import SnapshotInputBuilder, SnapshotSourceRequest
from workflows.jobs.support import utc_now_iso, write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build parser for snapshot input production."""

    parser = argparse.ArgumentParser(prog="daily_snapshot_input_build")
    parser.add_argument("--schedule-config-path")
    parser.add_argument("--catalog-path")
    parser.add_argument("--mysql-config-path")
    parser.add_argument("--request-path")
    parser.add_argument("--output-path")
    parser.add_argument("--job-result-path")
    parser.add_argument("--date")
    parser.add_argument("--stock-code", action="append", dest="stock_codes", default=[])
    return parser


def _read_json_object(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return dict(payload)


def _resolve_path(value: object, base_dir: Path) -> str | None:
    if value is None:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return str(path)


def _resolve_settings(args: argparse.Namespace) -> dict[str, object]:
    config: dict[str, object] = {}
    config_dir = PROJECT_ROOT
    schedule_config_path: str | None = None
    if args.schedule_config_path:
        config_path = Path(args.schedule_config_path).resolve()
        config = _read_json_object(config_path)
        config_dir = config_path.parent
        schedule_config_path = str(config_path)

    settings = {
        "schedule_config_path": schedule_config_path,
        "catalog_path": args.catalog_path or _resolve_path(config.get("catalog_path"), config_dir),
        "mysql_config_path": args.mysql_config_path or _resolve_path(config.get("mysql_config_path"), config_dir),
        "request_path": args.request_path or _resolve_path(config.get("request_path"), config_dir),
        "output_path": args.output_path or _resolve_path(config.get("output_path"), config_dir),
        "job_result_path": args.job_result_path or _resolve_path(config.get("job_result_path"), config_dir),
        "date": args.date or config.get("date"),
        "stock_codes": tuple(args.stock_codes or config.get("stock_codes", ())),
    }
    missing = [key for key in ("catalog_path", "mysql_config_path", "request_path", "output_path") if settings[key] is None]
    if missing:
        raise ValueError(f"missing required snapshot input settings: {', '.join(missing)}")
    return settings


def _source_requests(payload: Mapping[str, object]) -> tuple[SnapshotSourceRequest, ...]:
    sources = payload.get("source_assets", ())
    if not isinstance(sources, Sequence) or isinstance(sources, (str, bytes)):
        raise ValueError("source_assets must be a JSON array")

    requests: list[SnapshotSourceRequest] = []
    for source in sources:
        if not isinstance(source, Mapping):
            raise ValueError("each source asset request must be a JSON object")
        fields = source.get("fields")
        if fields is not None and (not isinstance(fields, Sequence) or isinstance(fields, (str, bytes))):
            raise ValueError("source fields must be a JSON array")
        extra_filters = source.get("extra_filters", {})
        if extra_filters and not isinstance(extra_filters, Mapping):
            raise ValueError("extra_filters must be a JSON object")
        requests.append(
            SnapshotSourceRequest(
                asset_id=str(source["asset_id"]),
                fields=tuple(str(field) for field in fields) if fields is not None else None,
                extra_filters=dict(extra_filters),
                date_field=str(source["date_field"]) if source.get("date_field") is not None else None,
                query_version=str(source.get("query_version", "l0_mysql_v1")),
                limit=int(source["limit"]) if source.get("limit") is not None else None,
            )
        )
    return tuple(requests)


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    """Build snapshot input from MySQL-backed L0 assets."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    started_at = utc_now_iso()
    settings: dict[str, object] | None = None
    try:
        settings = _resolve_settings(args)
        request_payload = _read_json_object(str(settings["request_path"]))
        stock_codes = tuple(str(code) for code in (settings["stock_codes"] or request_payload.get("stock_codes", ())))
        snapshot_date = str(settings["date"] or request_payload["snapshot_date"])
        analysis_version = str(request_payload.get("analysis_version", "analysis_v1"))
        if not stock_codes:
            raise ValueError("stock_codes must not be empty")

        catalog_snapshot = DataAssetCatalogLoader().load_json(str(settings["catalog_path"]))
        row_reader = ExternalMysqlAdapter.from_config_path(str(settings["mysql_config_path"]))
        input_builder = SnapshotInputBuilder(catalog=catalog_snapshot.catalog, row_reader=row_reader)
        output_payload = input_builder.build_input(
            stock_codes=stock_codes,
            snapshot_date=snapshot_date,
            source_requests=_source_requests(request_payload),
            analysis_version=analysis_version,
        )
        write_json_payload(str(settings["output_path"]), output_payload)

        result = {
            "job_name": "daily_snapshot_input_build",
            "status": "success",
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "schedule_config_path": settings["schedule_config_path"],
            "catalog_path": settings["catalog_path"],
            "request_path": settings["request_path"],
            "output_path": settings["output_path"],
            "snapshot_date": snapshot_date,
            "stock_count": len(stock_codes),
            "source_asset_count": len(request_payload.get("source_assets", ())),
        }
        if settings["job_result_path"]:
            write_json_payload(str(settings["job_result_path"]), result)
        _print_json(result)
        return 0
    except Exception as exc:  # pragma: no cover - operational failure branch
        result = {
            "job_name": "daily_snapshot_input_build",
            "status": "failed",
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "error_message": str(exc),
        }
        result_path = settings["job_result_path"] if settings is not None else args.job_result_path
        if result_path:
            write_json_payload(str(result_path), result)
        _print_json(result)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
