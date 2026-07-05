"""Job for reviewing whether research artifacts can enter production."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_foundation.quality import (
    load_promotion_evidence,
    load_promotion_policy,
    review_promotion,
)
from workflows.jobs.support import write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build parser for production-promotion reviews."""

    parser = argparse.ArgumentParser(prog="production_promotion_review")
    parser.add_argument("--policy-path", required=True)
    parser.add_argument("--evidence-path", required=True)
    parser.add_argument("--output-path", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one deterministic production-promotion review."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    policy = load_promotion_policy(args.policy_path)
    evidence = load_promotion_evidence(args.evidence_path)
    result = review_promotion(evidence=evidence, policy=policy)
    payload = {
        "schema_version": 1,
        "job_name": "production_promotion_review",
        "policy_id": policy.policy_id,
        "evidence_path": args.evidence_path,
        "review": result.to_mapping(),
    }
    write_json_payload(args.output_path, payload)
    print(json.dumps(payload["review"], indent=2, ensure_ascii=False))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
