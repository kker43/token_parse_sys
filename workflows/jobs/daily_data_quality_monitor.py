"""Routine job for published-product readiness monitoring."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_foundation import (
    check_product_readiness,
    load_field_types_by_product,
    load_observed_inputs_by_product,
    load_product_registry_bundle,
    load_quality_statuses,
    readiness_report,
)
from stock_lobster.core.ids import new_run_id
from workflows.jobs.support import utc_now_iso, write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build the routine quality monitor parser."""

    parser = argparse.ArgumentParser(prog="daily_data_quality_monitor")
    parser.add_argument("--registry-path", required=True)
    parser.add_argument("--quality-path", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--job-result-path")
    parser.add_argument("--field-types-path")
    parser.add_argument("--observed-inputs-path")
    parser.add_argument("--registry-name", default="data_product_registry")
    parser.add_argument("--source-commit", default="unknown")
    parser.add_argument("--source-path", default="unknown")
    parser.add_argument("--product", action="append", dest="products", default=[])
    return parser


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the routine quality monitoring job."""

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
        quality_statuses = load_quality_statuses(args.quality_path)
        observed_inputs = load_observed_inputs_by_product(args.observed_inputs_path)
        results = check_product_readiness(
            bundle=bundle,
            quality_statuses=quality_statuses,
            requested_date=args.date,
            observed_inputs_by_product=observed_inputs,
            selected_products=args.products,
        )
        report = readiness_report(bundle=bundle, results=results)
        result = {
            "job_name": "daily_data_quality_monitor",
            "run_id": run_id,
            "status": "success" if report["overall_ready"] else "failed",
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "requested_date": args.date,
            **report,
        }
        if args.job_result_path:
            write_json_payload(args.job_result_path, result)
        _print_json(result)
        return 0 if report["overall_ready"] else 1
    except Exception as exc:  # pragma: no cover - failure branch is integration-oriented
        result = {
            "job_name": "daily_data_quality_monitor",
            "run_id": run_id,
            "status": "failed",
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "requested_date": args.date,
            "error_message": str(exc),
        }
        if args.job_result_path:
            write_json_payload(args.job_result_path, result)
        _print_json(result)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
