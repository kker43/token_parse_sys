"""Operator CLI for data-foundation registry, export, and readiness tasks."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from data_foundation import (
    check_product_readiness,
    export_data_asset_catalog,
    list_product_summaries,
    load_field_types_by_product,
    load_observed_inputs_by_product,
    load_product_registry_bundle,
    load_quality_statuses,
    readiness_report,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the data-foundation CLI parser."""

    parser = argparse.ArgumentParser(prog="data-foundation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command_name in ("list-products", "export-data-assets", "check-readiness"):
        subparser = subparsers.add_parser(command_name)
        subparser.add_argument("--registry-path", required=True)
        subparser.add_argument("--field-types-path")
        subparser.add_argument("--registry-name", default="data_product_registry")
        subparser.add_argument("--source-commit", default="unknown")
        subparser.add_argument("--source-path", default="/home/ubuntu/token_fetch")
        subparser.add_argument("--producer-name", default="token_fetch")

    export_parser = subparsers.choices["export-data-assets"]
    export_parser.add_argument("--output-path", required=True)

    readiness_parser = subparsers.choices["check-readiness"]
    readiness_parser.add_argument("--quality-path", required=True)
    readiness_parser.add_argument("--date", required=True)
    readiness_parser.add_argument("--observed-inputs-path")
    readiness_parser.add_argument("--product", action="append", dest="products", default=[])

    return parser


def _load_bundle(args: argparse.Namespace):
    field_types = load_field_types_by_product(args.field_types_path)
    return load_product_registry_bundle(
        registry_path=args.registry_path,
        source_commit=args.source_commit,
        source_path=args.source_path,
        registry_name=args.registry_name,
        field_types_by_product=field_types,
    )


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    """Run one deterministic data-foundation operator command."""

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    bundle = _load_bundle(args)

    if args.command == "list-products":
        _print_json(
            {
                "registry_name": bundle.snapshot.registry_name,
                "registry_version": bundle.snapshot.registry_version,
                "source_commit": bundle.snapshot.source_commit,
                "source_path": bundle.snapshot.source_path,
                "products": list_product_summaries(bundle),
            }
        )
        return 0

    if args.command == "export-data-assets":
        payload = export_data_asset_catalog(
            bundle=bundle,
            output_path=args.output_path,
            producer_name=args.producer_name,
        )
        _print_json(
            {
                "output_path": args.output_path,
                "product_count": len(payload["products"]),
                "producer": payload["producer"],
                "source_ref": payload.get("source_ref"),
            }
        )
        return 0

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
    report["requested_date"] = args.date
    _print_json(report)
    return 0 if report["overall_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
