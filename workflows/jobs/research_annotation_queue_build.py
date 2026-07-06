"""Build a proposed annotation queue from scan and backtest results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.research.annotation_queue import (
    AnnotationSuggestionPolicy,
    build_annotation_queue,
)
from workflows.jobs.support import write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build parser for annotation queue generation."""

    parser = argparse.ArgumentParser(prog="research_annotation_queue_build")
    parser.add_argument("--scan-result-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--event-backtest-path")
    parser.add_argument("--policy-path")
    parser.add_argument("--candidate-key", default="breakout_candidates")
    parser.add_argument("--holding-horizon", type=int)
    parser.add_argument("--source-lane", default="scan_candidate_review")
    parser.add_argument("--queue-id", default="research_annotation_queue.steady_uptrend_breakout.v1")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Build and write a proposed annotation queue."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    scan_payload = _load_json(args.scan_result_path)
    event_backtest_payload = _load_json(args.event_backtest_path) if args.event_backtest_path else None
    policy = _load_policy(args.policy_path)
    queue = build_annotation_queue(
        scan_payload=scan_payload,
        event_backtest_payload=event_backtest_payload,
        policy=policy,
        candidate_key=args.candidate_key,
        holding_horizon=args.holding_horizon,
        source_lane=args.source_lane,
        queue_id=args.queue_id,
        source_scan_result_path=args.scan_result_path,
        source_event_backtest_path=args.event_backtest_path,
    )
    payload = queue.to_mapping()
    write_json_payload(args.output_path, payload)
    print(
        json.dumps(
            {
                "output_path": args.output_path,
                "queue_id": queue.queue_id,
                "item_count": len(queue.items),
                "summary": payload["summary"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _load_json(path: str | None) -> dict[str, object]:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _load_policy(path: str | None) -> AnnotationSuggestionPolicy:
    if not path:
        return AnnotationSuggestionPolicy()
    payload = _load_json(path)
    return AnnotationSuggestionPolicy.from_mapping(payload.get("annotation_suggestion_policy", payload))


if __name__ == "__main__":
    raise SystemExit(main())
