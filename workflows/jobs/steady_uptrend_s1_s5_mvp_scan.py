"""Research-only S1-S5 scan for the mature steady-uptrend MVP."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict, fields
import hashlib
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.research import (
    SteadyUptrendMvpCandidate,
    SteadyUptrendMvpPolicy,
    build_steady_uptrend_mvp_report,
    evaluate_steady_uptrend_mvp,
    read_kline_tsv,
    read_stock_signal_context_tsv,
)
from stock_lobster.research.trend_breakout_scan import KlineBar, StockSignalContext
from workflows.jobs.support import write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build the deterministic research scan CLI."""

    parser = argparse.ArgumentParser(prog="steady_uptrend_s1_s5_mvp_scan")
    parser.add_argument("--kline-tsv-path", required=True)
    parser.add_argument("--weekly-kline-tsv-path", required=True)
    parser.add_argument("--stock-context-tsv-path", required=True)
    parser.add_argument("--kline-manifest-path", required=True)
    parser.add_argument("--stock-context-manifest-path", required=True)
    parser.add_argument("--quality-status-path", required=True)
    parser.add_argument("--strategy-config-path", required=True)
    parser.add_argument("--signal-date", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--markdown-output-path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Evaluate one signal date from supplied read-only fact artifacts."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    config = _read_json_object(args.strategy_config_path)
    strategy_id = _required_string(config, "strategy_id")
    status = _required_strategy_status(config)
    version = _required_string(config, "version")
    policy = _build_policy(config.get("policy"))
    kline_manifest = _read_json_object(args.kline_manifest_path)
    context_manifest = _read_json_object(args.stock_context_manifest_path)
    readiness = _read_json_object(args.quality_status_path)
    validate_scan_input_contracts(
        kline_manifest,
        context_manifest,
        readiness,
        signal_date=args.signal_date,
        daily_kline_path=args.kline_tsv_path,
        weekly_kline_path=args.weekly_kline_tsv_path,
        stock_context_path=args.stock_context_tsv_path,
    )
    dependency_versions = _dependency_versions_from_manifests(
        kline_manifest,
        context_manifest,
    )

    daily_bars = read_kline_tsv(args.kline_tsv_path)
    weekly_bars = read_kline_tsv(args.weekly_kline_tsv_path)
    contexts = read_stock_signal_context_tsv(args.stock_context_tsv_path)
    evaluations = _evaluate_universe(
        daily_bars,
        weekly_bars,
        contexts,
        signal_date=args.signal_date,
        policy=policy,
    )
    payload = build_steady_uptrend_mvp_report(
        evaluations,
        strategy_id=strategy_id,
        run_id=args.run_id,
        signal_date=args.signal_date,
        data_dependency_versions=dependency_versions,
    )
    payload.update(
        {
            "schema_version": 1,
            "scanner": "steady_uptrend_s1_s5_mvp_scan",
            "version": version,
            "status": status,
            "policy": asdict(policy),
            "input_contracts": {
                "kline_manifest_path": args.kline_manifest_path,
                "stock_context_manifest_path": args.stock_context_manifest_path,
                "quality_status_path": args.quality_status_path,
            },
        }
    )
    write_json_payload(args.output_path, payload)
    if args.markdown_output_path:
        markdown_output = Path(args.markdown_output_path)
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(str(payload["markdown"]), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": args.output_path,
                "signal_date": args.signal_date,
                "input_count": len(evaluations),
                "candidate_count": len(payload["candidates"]),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def _evaluate_universe(
    daily_bars: tuple[KlineBar, ...],
    weekly_bars: tuple[KlineBar, ...],
    contexts: tuple[StockSignalContext, ...],
    *,
    signal_date: str,
    policy: SteadyUptrendMvpPolicy,
) -> tuple[SteadyUptrendMvpCandidate, ...]:
    daily_by_asset: dict[str, list[KlineBar]] = defaultdict(list)
    weekly_by_asset: dict[str, list[KlineBar]] = defaultdict(list)
    for bar in daily_bars:
        if bar.trade_date <= signal_date:
            daily_by_asset[bar.asset_id].append(bar)
    for bar in weekly_bars:
        if bar.trade_date <= signal_date:
            weekly_by_asset[bar.asset_id].append(bar)
    context_by_asset: dict[str, StockSignalContext] = {}
    for context in contexts:
        if context.trade_date != signal_date:
            continue
        if context.asset_id in context_by_asset:
            raise ValueError(
                f"duplicate stock context for {context.asset_id}.{signal_date}"
            )
        context_by_asset[context.asset_id] = context
    assets_with_signal_bar = {
        asset_id
        for asset_id, bars in daily_by_asset.items()
        if bars and max(bar.trade_date for bar in bars) == signal_date
    }
    asset_ids = sorted(assets_with_signal_bar | set(context_by_asset))
    return tuple(
        evaluate_steady_uptrend_mvp(
            daily_by_asset.get(asset_id, ()),
            weekly_by_asset.get(asset_id, ()),
            context_by_asset.get(asset_id),
            signal_date=signal_date,
            policy=policy,
        )
        for asset_id in asset_ids
    )


def _build_policy(payload: object) -> SteadyUptrendMvpPolicy:
    if payload is None:
        return SteadyUptrendMvpPolicy()
    if not isinstance(payload, Mapping):
        raise ValueError("policy must be a JSON object")
    allowed = {field.name for field in fields(SteadyUptrendMvpPolicy)}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"unknown policy keys: {', '.join(unknown)}")
    return SteadyUptrendMvpPolicy(**dict(payload))


def _read_json_object(path: str | Path) -> Mapping[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("strategy config must be a JSON object")
    return payload


def _required_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_strategy_status(payload: Mapping[str, object]) -> str:
    status = _required_string(payload, "status")
    if status != "research_only":
        raise ValueError("S1-S5 MVP research scan status must be research_only")
    return status


def validate_scan_input_contracts(
    kline_manifest: Mapping[str, object],
    context_manifest: Mapping[str, object],
    readiness: Mapping[str, object],
    *,
    signal_date: str,
    daily_kline_path: str,
    weekly_kline_path: str,
    stock_context_path: str,
) -> None:
    """Reject scans whose input artifacts do not prove the approved contract."""

    if kline_manifest.get("job_name") != "research_kline_batch_export":
        raise ValueError("kline manifest job_name mismatch")
    if kline_manifest.get("price_basis") != "qfq_asof":
        raise ValueError("kline price basis must be qfq_asof")
    if str(kline_manifest.get("daily_end_date")) != signal_date:
        raise ValueError("daily kline manifest end date mismatch")
    if str(kline_manifest.get("weekly_end_date")) != signal_date:
        raise ValueError("weekly kline manifest end date mismatch")
    kline_units = kline_manifest.get("field_units")
    if not isinstance(kline_units, Mapping) or kline_units.get("amount") != "thousand_cny":
        raise ValueError("kline amount unit mismatch: expected thousand_cny")
    if kline_units.get("vol") != "lot":
        raise ValueError("kline volume unit mismatch: expected lot")

    if context_manifest.get("job_name") != "research_stock_context_batch_export":
        raise ValueError("stock context manifest job_name mismatch")
    trade_dates = context_manifest.get("trade_dates")
    if not isinstance(trade_dates, list) or trade_dates != [signal_date]:
        raise ValueError("stock context manifest must contain only the signal date")
    context_units = context_manifest.get("field_units")
    if (
        not isinstance(context_units, Mapping)
        or context_units.get("avg_amount_20d") != "thousand_cny"
    ):
        raise ValueError("context avg_amount_20d unit mismatch: expected thousand_cny")
    if context_units.get("total_mv") != "ten_thousand_cny":
        raise ValueError("context total_mv unit mismatch: expected ten_thousand_cny")

    statuses = readiness.get("statuses")
    if not isinstance(statuses, list):
        raise ValueError("quality status evidence must contain a statuses array")
    status_by_key: dict[tuple[str, str, str, str], Mapping[str, object]] = {}
    for item in statuses:
        if not isinstance(item, Mapping):
            continue
        key = (
            str(item.get("data_product")),
            str(item.get("data_date")),
            str(item.get("market")),
            str(item.get("asset_type")),
        )
        if key in status_by_key:
            raise ValueError(f"duplicate quality status for {'.'.join(key)}")
        status_by_key[key] = item
    weekly_quality_date = kline_manifest.get("weekly_latest_trade_date")
    if not isinstance(weekly_quality_date, str) or not weekly_quality_date:
        raise ValueError("kline manifest weekly_latest_trade_date is required")
    required_products = (
        "pub_stock_daily_kline",
        "pub_stock_weekly_kline",
        "pub_stock_daily_basic",
        "pub_stock_daily_indicator",
        "pub_stock_asset_basic",
    )
    quality_items: dict[str, Mapping[str, object]] = {}
    for product in required_products:
        expected_date = weekly_quality_date if product == "pub_stock_weekly_kline" else signal_date
        item = status_by_key.get((product, expected_date, "CN_A", "stock"))
        if item is None:
            raise ValueError(f"missing CN_A/stock quality status for {product}")
        if str(item.get("source_end_date")) != expected_date:
            raise ValueError(f"quality source end date mismatch for {product}")
        if item.get("status") != "ready" or item.get("quality_level") != "pass":
            raise ValueError(f"quality readiness gate is not ready for {product}")
        quality_items[product] = item

    kline_versions = kline_manifest.get("data_versions")
    if not isinstance(kline_versions, Mapping):
        raise ValueError("kline manifest data_versions are required")
    context_version = context_manifest.get("data_version")
    expected_versions = {
        "pub_stock_daily_kline": kline_versions.get("daily_kline"),
        "pub_stock_weekly_kline": kline_versions.get("weekly_kline"),
        "pub_stock_daily_basic": context_version,
        "pub_stock_daily_indicator": context_version,
        "pub_stock_asset_basic": context_version,
    }
    for product, expected_version in expected_versions.items():
        if not isinstance(expected_version, str) or not expected_version:
            raise ValueError(f"manifest data version missing for {product}")
        if quality_items[product].get("data_version") != expected_version:
            raise ValueError(f"data version mismatch for {product}")

    _validate_manifest_file(
        path=daily_kline_path,
        manifest_path=kline_manifest.get("daily_output_path"),
        expected_rows=kline_manifest.get("daily_row_count"),
        expected_sha256=kline_manifest.get("daily_sha256"),
        has_header=False,
        label="daily kline",
    )
    _validate_manifest_file(
        path=weekly_kline_path,
        manifest_path=kline_manifest.get("weekly_output_path"),
        expected_rows=kline_manifest.get("weekly_row_count"),
        expected_sha256=kline_manifest.get("weekly_sha256"),
        has_header=False,
        label="weekly kline",
    )
    _validate_manifest_file(
        path=stock_context_path,
        manifest_path=context_manifest.get("output_path"),
        expected_rows=context_manifest.get("row_count"),
        expected_sha256=context_manifest.get("sha256"),
        has_header=True,
        label="stock context",
    )


def _validate_manifest_file(
    *,
    path: str,
    manifest_path: object,
    expected_rows: object,
    expected_sha256: object,
    has_header: bool,
    label: str,
) -> None:
    actual_path = Path(path).resolve()
    if not actual_path.is_file():
        raise ValueError(f"{label} file does not exist")
    if not isinstance(manifest_path, str) or Path(manifest_path).resolve() != actual_path:
        raise ValueError(f"{label} manifest path mismatch")
    with actual_path.open("r", encoding="utf-8") as file_handle:
        line_count = sum(1 for _ in file_handle)
    actual_rows = max(0, line_count - 1) if has_header else line_count
    if not isinstance(expected_rows, int) or expected_rows != actual_rows:
        raise ValueError(f"{label} manifest row count mismatch")
    if not isinstance(expected_sha256, str) or expected_sha256 != _sha256_file(actual_path):
        raise ValueError(f"{label} manifest sha256 mismatch")


def _dependency_versions_from_manifests(
    kline_manifest: Mapping[str, object],
    context_manifest: Mapping[str, object],
) -> dict[str, str]:
    kline_versions = kline_manifest.get("data_versions")
    if not isinstance(kline_versions, Mapping):
        raise ValueError("kline manifest data_versions are required")
    daily_version = kline_versions.get("daily_kline")
    weekly_version = kline_versions.get("weekly_kline")
    context_version = context_manifest.get("data_version")
    values = (daily_version, weekly_version, context_version)
    if any(not isinstance(value, str) or not value for value in values):
        raise ValueError("manifest data versions must be non-empty strings")
    return {
        "daily_kline": f"{daily_version}:{str(kline_manifest['daily_sha256'])[:12]}",
        "weekly_kline": f"{weekly_version}:{str(kline_manifest['weekly_sha256'])[:12]}",
        "stock_context": f"{context_version}:{str(context_manifest['sha256'])[:12]}",
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
