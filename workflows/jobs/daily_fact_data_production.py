"""Routine job for wrapping an external fact-data producer command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_foundation.provider_bridge import ExternalFactProductionRunner
from stock_lobster.core.ids import new_run_id
from workflows.jobs.support import utc_now_iso, write_json_payload


def build_parser() -> argparse.ArgumentParser:
    """Build the routine fact-production wrapper parser."""

    parser = argparse.ArgumentParser(prog="daily_fact_data_production")
    parser.add_argument("--producer-name", default="external_producer")
    parser.add_argument("--producer-root", required=True)
    parser.add_argument("--producer-command", nargs="+", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=14_400)
    parser.add_argument("--job-result-path")
    return parser


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the stable fact-production wrapper job."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    run_id = str(new_run_id(prefix="job"))
    started_at = utc_now_iso()

    try:
        runner = ExternalFactProductionRunner(
            producer_name=args.producer_name,
            producer_root=args.producer_root,
            command=tuple(args.producer_command),
        )
        producer_result = runner.run(timeout_seconds=args.timeout_seconds)
        result = {
            "job_name": "daily_fact_data_production",
            "run_id": run_id,
            "status": "success" if producer_result.success else "failed",
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "timeout_seconds": args.timeout_seconds,
            "producer": {
                "name": producer_result.producer_name,
                "root": producer_result.producer_root,
                "branch": producer_result.producer_branch,
                "commit": producer_result.producer_commit,
                "command": list(producer_result.command),
                "returncode": producer_result.returncode,
                "started_at": producer_result.started_at,
                "finished_at": producer_result.finished_at,
                "stdout_tail": list(producer_result.stdout_tail),
                "stderr_tail": list(producer_result.stderr_tail),
                "error_message": producer_result.error_message,
            },
        }
        if args.job_result_path:
            write_json_payload(args.job_result_path, result)
        _print_json(result)
        return 0 if producer_result.success else 1
    except Exception as exc:  # pragma: no cover - failure branch is integration-oriented
        result = {
            "job_name": "daily_fact_data_production",
            "run_id": run_id,
            "status": "failed",
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "timeout_seconds": args.timeout_seconds,
            "error_message": str(exc),
        }
        if args.job_result_path:
            write_json_payload(args.job_result_path, result)
        _print_json(result)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
