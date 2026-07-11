"""Extract wide-recall research candidates from steady-uptrend v3 rejections."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.research.annotation_queue import DEFAULT_REVIEW_LABEL_OPTIONS
from workflows.jobs.support import write_json_payload

RESEARCH_BUCKET_REVIEW_CODES = {
    "near_pre_breakout": 4,
    "risk_context_rejected": 3,
    "market_temperature_rejected": 4,
}


def build_parser() -> argparse.ArgumentParser:
    """Build parser for wide-recall research pool extraction."""

    parser = argparse.ArgumentParser(prog="steady_uptrend_wide_recall_pool")
    parser.add_argument("--scan-result-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--source-key", default="v3_rejected_candidates")
    parser.add_argument("--max-items-per-bucket-per-date", type=int, default=3)
    parser.add_argument("--max-items", type=int, default=300)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Extract a deterministic wide-recall pool."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    scan_payload = _load_json_object(args.scan_result_path)
    candidates = extract_wide_recall_candidates(
        scan_payload,
        source_key=args.source_key,
        max_items_per_bucket_per_date=args.max_items_per_bucket_per_date,
        max_items=args.max_items,
    )
    payload = {
        "schema_version": 1,
        "job_name": "steady_uptrend_wide_recall_pool",
        "source_scan_result_path": args.scan_result_path,
        "source_key": args.source_key,
        "pool_semantics": "research_only_wide_recall_not_trade_signal",
        "candidate_count": len(candidates),
        "review_input_format": "review_idx<TAB>review_code",
        "review_label_options": [option.to_mapping() for option in DEFAULT_REVIEW_LABEL_OPTIONS],
        "summary": _summary(candidates),
        "wide_recall_candidates": candidates,
    }
    write_json_payload(args.output_path, payload)
    print(
        json.dumps(
            {
                "output_path": args.output_path,
                "candidate_count": len(candidates),
                "summary": payload["summary"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def extract_wide_recall_candidates(
    scan_payload: Mapping[str, object],
    *,
    source_key: str = "v3_rejected_candidates",
    max_items_per_bucket_per_date: int = 3,
    max_items: int = 300,
) -> list[dict[str, object]]:
    """Extract rejected but research-useful candidates from one scan payload."""

    if max_items_per_bucket_per_date <= 0:
        raise ValueError("max_items_per_bucket_per_date must be positive")
    if max_items <= 0:
        raise ValueError("max_items must be positive")
    source_rows = scan_payload.get(source_key, ())
    if not isinstance(source_rows, Sequence) or isinstance(source_rows, (str, bytes)):
        raise ValueError(f"{source_key} must be a JSON array")

    selected: list[dict[str, object]] = []
    counts_by_date_bucket: Counter[tuple[str, str]] = Counter()
    sorted_rows = sorted(
        (row for row in source_rows if isinstance(row, Mapping)),
        key=lambda row: (
            str(row.get("trade_date", "")),
            -float(row.get("v3_score") or row.get("setup_score") or 0),
            str(row.get("asset_id", "")),
        ),
    )
    for row in sorted_rows:
        bucket = _research_bucket(row)
        if bucket is None:
            continue
        trade_date = str(row.get("trade_date", ""))
        key = (trade_date, bucket)
        if counts_by_date_bucket[key] >= max_items_per_bucket_per_date:
            continue
        selected.append(_wide_recall_mapping(row, research_bucket=bucket))
        counts_by_date_bucket[key] += 1
        if len(selected) >= max_items:
            break
    for review_idx, candidate in enumerate(selected, start=1):
        candidate["review_idx"] = review_idx
    return selected


def _research_bucket(candidate: Mapping[str, object]) -> str | None:
    reasons = {str(reason) for reason in candidate.get("v3_rejection_reasons", ()) or ()}
    if "pre_breakout_too_far_from_high" in reasons or "pre_breakout_too_close_to_high" in reasons:
        return "near_pre_breakout"
    if "blocked_risk_context" in reasons or "fading_context_without_preferred_rotation" in reasons:
        return "risk_context_rejected"
    if any(reason.startswith("market_") for reason in reasons):
        return "market_temperature_rejected"
    return None


def _wide_recall_mapping(
    candidate: Mapping[str, object],
    *,
    research_bucket: str,
) -> dict[str, object]:
    payload = dict(candidate)
    payload["research_bucket"] = research_bucket
    payload["label_status"] = "proposed"
    payload["suggested_review_code"] = RESEARCH_BUCKET_REVIEW_CODES[research_bucket]
    payload["review_code_prompt"] = "填写数字 code；该池只用于研究打标，不是交易观察池。"
    return payload


def _summary(candidates: Sequence[Mapping[str, object]]) -> dict[str, object]:
    by_bucket: Counter[str] = Counter(str(item.get("research_bucket")) for item in candidates)
    by_date: Counter[str] = Counter(str(item.get("trade_date")) for item in candidates)
    return {
        "candidate_count": len(candidates),
        "by_research_bucket": dict(sorted(by_bucket.items())),
        "trade_date_count": len(by_date),
        "min_trade_date": min(by_date) if by_date else None,
        "max_trade_date": max(by_date) if by_date else None,
    }


def _load_json_object(path: str | Path) -> Mapping[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
