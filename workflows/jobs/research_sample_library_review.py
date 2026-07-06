"""Job for reviewing research sample library coverage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.research.sample_library import (
    SampleLibraryGatePolicy,
    evaluate_sample_library,
    load_sample_library,
)
from workflows.jobs.support import write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build parser for sample library review."""

    parser = argparse.ArgumentParser(prog="research_sample_library_review")
    parser.add_argument("--sample-library-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--policy-path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Review one research sample library and write a coverage report."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    policy = _load_policy(args.policy_path)
    result = evaluate_sample_library(
        library=load_sample_library(args.sample_library_path),
        policy=policy,
    )
    payload = result.to_mapping()
    payload["sample_library_path"] = args.sample_library_path
    payload["policy_path"] = args.policy_path
    write_json_payload(args.output_path, payload)
    print(
        json.dumps(
            {
                "output_path": args.output_path,
                "passed": result.passed,
                "event_count": result.coverage.event_count,
                "dated_event_count": result.coverage.dated_event_count,
                "positive_event_count": result.coverage.positive_event_count,
                "negative_event_count": result.coverage.negative_event_count,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _load_policy(path: str | None) -> SampleLibraryGatePolicy:
    if not path:
        return SampleLibraryGatePolicy()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return SampleLibraryGatePolicy.from_mapping(payload.get("sample_library_gate_policy", payload))


if __name__ == "__main__":
    raise SystemExit(main())
