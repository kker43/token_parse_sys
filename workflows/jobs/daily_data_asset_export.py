"""Routine job for exporting published data-asset configs."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from data_foundation import export_data_asset_catalog, load_field_types_by_product, load_product_registry_bundle
from stock_lobster.core.ids import new_run_id
from workflows.jobs.support import utc_now_iso, write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build the routine export job parser."""

    parser = argparse.ArgumentParser(prog="daily_data_asset_export")
    parser.add_argument("--registry-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--job-result-path")
    parser.add_argument("--field-types-path")
    parser.add_argument("--registry-name", default="data_product_registry")
    parser.add_argument("--source-commit", default="unknown")
    parser.add_argument("--source-path", default="/home/ubuntu/token_fetch")
    parser.add_argument("--producer-name", default="token_fetch")
    return parser


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the routine data-asset export job."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    run_id = str(new_run_id(prefix="job"))
    started_at = utc_now_iso()

    try:
        field_types = load_field_types_by_product(args.field_types_path)
        bundle = load_product_registry_bundle(
            registry_path=args.registry_path,
            source_commit=args.source_commit,
            source_path=args.source_path,
            registry_name=args.registry_name,
            field_types_by_product=field_types,
        )
        payload = export_data_asset_catalog(
            bundle=bundle,
            output_path=args.output_path,
            producer_name=args.producer_name,
        )
        result = {
            "job_name": "daily_data_asset_export",
            "run_id": run_id,
            "status": "success",
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "output_path": args.output_path,
            "product_count": len(payload["products"]),
            "producer": payload["producer"],
            "source_ref": payload.get("source_ref"),
        }
        if args.job_result_path:
            write_json_payload(args.job_result_path, result)
        _print_json(result)
        return 0
    except Exception as exc:  # pragma: no cover - failure branch is integration-oriented
        result = {
            "job_name": "daily_data_asset_export",
            "run_id": run_id,
            "status": "failed",
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "error_message": str(exc),
        }
        if args.job_result_path:
            write_json_payload(args.job_result_path, result)
        _print_json(result)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
