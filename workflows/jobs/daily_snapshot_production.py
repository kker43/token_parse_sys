"""Routine job for deterministic L1 analysis snapshot production."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.core.ids import new_run_id
from stock_lobster.l0_data_access import DataAssetCatalogLoader
from stock_lobster.l1_analysis_snapshot import (
    DeterministicAnalysisSnapshotBuilder,
    SourceRows,
)
from workflows.jobs.support import utc_now_iso, write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build the routine snapshot-production parser."""

    parser = argparse.ArgumentParser(prog="daily_snapshot_production")
    parser.add_argument("--schedule-config-path")
    parser.add_argument("--catalog-path")
    parser.add_argument("--snapshot-input-path")
    parser.add_argument("--output-path")
    parser.add_argument("--job-result-path")
    parser.add_argument("--analysis-version")
    return parser


def _read_json_object(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return dict(payload)


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


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
        "snapshot_input_path": args.snapshot_input_path or _resolve_path(config.get("snapshot_input_path"), config_dir),
        "output_path": args.output_path or _resolve_path(config.get("output_path"), config_dir),
        "job_result_path": args.job_result_path or _resolve_path(config.get("job_result_path"), config_dir),
        "analysis_version": args.analysis_version or config.get("analysis_version"),
    }
    missing = [key for key in ("catalog_path", "snapshot_input_path", "output_path") if settings[key] is None]
    if missing:
        raise ValueError(f"missing required snapshot settings: {', '.join(missing)}")
    return settings


def _source_rows_from_payload(source_payload: Mapping[str, object]) -> SourceRows:
    rows = source_payload.get("rows", ())
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("source rows must be a JSON array")
    normalized_rows: list[Mapping[str, object]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("each source row must be a JSON object")
        normalized_rows.append(dict(row))
    query_params = source_payload.get("query_params", {})
    if query_params and not isinstance(query_params, Mapping):
        raise ValueError("query_params must be a JSON object")
    return SourceRows(
        asset_id=str(source_payload["asset_id"]),
        rows=tuple(normalized_rows),
        query_version=str(source_payload.get("query_version", "manual_v1")),
        query_params={str(key): str(value) for key, value in dict(query_params).items()},
    )


def _sources_from_snapshot(snapshot_payload: Mapping[str, object]) -> tuple[SourceRows, ...]:
    sources = snapshot_payload.get("sources", ())
    if not isinstance(sources, Sequence) or isinstance(sources, (str, bytes)):
        raise ValueError("snapshot sources must be a JSON array")
    normalized_sources: list[SourceRows] = []
    for source in sources:
        if not isinstance(source, Mapping):
            raise ValueError("each snapshot source must be a JSON object")
        normalized_sources.append(_source_rows_from_payload(source))
    return tuple(normalized_sources)


def main(argv: Sequence[str] | None = None) -> int:
    """Run one deterministic L1 snapshot-production job."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    run_id = new_run_id(prefix="snapshot_job")
    started_at = utc_now_iso()
    settings: dict[str, object] | None = None

    try:
        settings = _resolve_settings(args)
        catalog_snapshot = DataAssetCatalogLoader().load_json(str(settings["catalog_path"]))
        input_payload = _read_json_object(str(settings["snapshot_input_path"]))
        analysis_version = str(settings["analysis_version"] or input_payload.get("analysis_version", "analysis_v1"))
        snapshot_date = str(input_payload["snapshot_date"])
        snapshots_payload = input_payload.get("snapshots", ())
        if not isinstance(snapshots_payload, Sequence) or isinstance(snapshots_payload, (str, bytes)):
            raise ValueError("snapshots must be a JSON array")

        builder = DeterministicAnalysisSnapshotBuilder(
            catalog=catalog_snapshot.catalog,
            analysis_version=analysis_version,
        )
        snapshots = []
        for snapshot_payload in snapshots_payload:
            if not isinstance(snapshot_payload, Mapping):
                raise ValueError("each snapshot entry must be a JSON object")
            snapshot = builder.build_from_sources(
                stock_code=str(snapshot_payload["stock_code"]),
                snapshot_date=str(snapshot_payload.get("snapshot_date", snapshot_date)),
                sources=_sources_from_snapshot(snapshot_payload),
                run_id=run_id,
            )
            snapshots.append(snapshot.to_mapping())

        output_payload = {
            "schema_version": 1,
            "analysis_version": analysis_version,
            "snapshot_date": snapshot_date,
            "run_id": str(run_id),
            "snapshots": snapshots,
        }
        write_json_payload(str(settings["output_path"]), output_payload)

        result = {
            "job_name": "daily_snapshot_production",
            "run_id": str(run_id),
            "status": "success",
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "schedule_config_path": settings["schedule_config_path"],
            "catalog_path": settings["catalog_path"],
            "snapshot_input_path": settings["snapshot_input_path"],
            "output_path": settings["output_path"],
            "snapshot_count": len(snapshots),
        }
        if settings["job_result_path"]:
            write_json_payload(str(settings["job_result_path"]), result)
        _print_json(result)
        return 0
    except Exception as exc:  # pragma: no cover - failure branch is integration-oriented
        result = {
            "job_name": "daily_snapshot_production",
            "run_id": str(run_id),
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
