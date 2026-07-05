"""CLI job for auditing factor reuse before adding new research factors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_lobster.research.factor_reuse import (
    FactorRequirement,
    audit_factor_reuse,
    load_indicator_catalog,
)
from workflows.jobs.support import write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build parser for factor reuse audit."""

    parser = argparse.ArgumentParser(prog="factor_reuse_audit")
    parser.add_argument("--requirements-path", required=True)
    parser.add_argument(
        "--indicator-registry-path",
        default="configs/technical_indicators/basic_technical_indicators.example.json",
    )
    parser.add_argument("--output-path", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run factor reuse audit."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    requirements = _load_requirements(args.requirements_path)
    indicators = load_indicator_catalog(args.indicator_registry_path)
    decisions = audit_factor_reuse(requirements, indicators)
    payload = {
        "schema_version": 1,
        "job_name": "factor_reuse_audit",
        "requirements_path": args.requirements_path,
        "indicator_registry_path": args.indicator_registry_path,
        "decisions": [decision.to_mapping() for decision in decisions],
    }
    write_json_payload(args.output_path, payload)
    print(json.dumps({"output_path": args.output_path, "decision_count": len(decisions)}, indent=2))
    return 0


def _load_requirements(path: str | Path) -> tuple[FactorRequirement, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload.get("requirements", payload if isinstance(payload, list) else ())
    if not isinstance(rows, list):
        raise ValueError("requirements payload must be a list or contain requirements list")
    requirements: list[FactorRequirement] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("each factor requirement must be a JSON object")
        requirements.append(
            FactorRequirement(
                name=str(row["name"]),
                meaning=str(row.get("meaning", "")),
                timeframe=str(row["timeframe"]) if row.get("timeframe") is not None else None,
                window=int(row["window"]) if row.get("window") is not None else None,
                reuse_family=str(row["reuse_family"]) if row.get("reuse_family") is not None else None,
            )
        )
    return tuple(requirements)


if __name__ == "__main__":
    raise SystemExit(main())
