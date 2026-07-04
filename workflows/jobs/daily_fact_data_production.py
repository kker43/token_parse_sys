"""Routine job for wrapping an external fact-data producer command."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_foundation.provider_bridge import ExternalFactProductionRunner
from stock_lobster.core.ids import new_run_id
from workflows.jobs.support import utc_now_iso, write_json_payload

DEFAULT_PRODUCER_NAME = "external_producer"
DEFAULT_TIMEOUT_SECONDS = 14_400


@dataclass(frozen=True, slots=True)
class DailyFactProductionSettings:
    """Resolved runtime settings for one fact-production wrapper run."""

    producer_name: str
    producer_root: str
    producer_command: tuple[str, ...]
    timeout_seconds: int
    job_result_path: str | None
    schedule_config_path: str | None


def build_parser() -> argparse.ArgumentParser:
    """Build the routine fact-production wrapper parser."""

    parser = argparse.ArgumentParser(prog="daily_fact_data_production")
    parser.add_argument("--schedule-config-path")
    parser.add_argument("--producer-name")
    parser.add_argument("--producer-root")
    parser.add_argument("--producer-command", nargs="+")
    parser.add_argument("--timeout-seconds", type=int)
    parser.add_argument("--job-result-path")
    return parser


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _read_schedule_config(path: str | Path) -> tuple[dict[str, object], Path]:
    config_path = Path(path).resolve()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("schedule config must contain a JSON object")
    return dict(payload), config_path


def _resolve_path(value: object, base_dir: Path) -> str | None:
    if value is None:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return str(path)


def _resolve_command(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("producer_command in schedule config must be a JSON array")
    return tuple(str(item) for item in value)


def resolve_settings(args: argparse.Namespace) -> DailyFactProductionSettings:
    """Resolve CLI arguments with optional schedule-config defaults."""

    config: dict[str, object] = {}
    config_dir = PROJECT_ROOT
    schedule_config_path: str | None = None
    if args.schedule_config_path:
        config, resolved_config_path = _read_schedule_config(args.schedule_config_path)
        config_dir = resolved_config_path.parent
        schedule_config_path = str(resolved_config_path)

    producer_name = str(args.producer_name or config.get("producer_name") or DEFAULT_PRODUCER_NAME)
    producer_root = args.producer_root or _resolve_path(config.get("producer_root"), config_dir)
    producer_command = tuple(args.producer_command or _resolve_command(config.get("producer_command")))
    timeout_seconds = (
        args.timeout_seconds
        if args.timeout_seconds is not None
        else int(config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
    )
    job_result_path = args.job_result_path or _resolve_path(config.get("job_result_path"), config_dir)

    if producer_root is None:
        raise ValueError("producer_root must be provided by CLI or schedule config")
    if not producer_command:
        raise ValueError("producer_command must be provided by CLI or schedule config")

    return DailyFactProductionSettings(
        producer_name=producer_name,
        producer_root=str(producer_root),
        producer_command=producer_command,
        timeout_seconds=timeout_seconds,
        job_result_path=job_result_path,
        schedule_config_path=schedule_config_path,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the stable fact-production wrapper job."""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    run_id = str(new_run_id(prefix="job"))
    started_at = utc_now_iso()
    settings: DailyFactProductionSettings | None = None

    try:
        settings = resolve_settings(args)
        runner = ExternalFactProductionRunner(
            producer_name=settings.producer_name,
            producer_root=settings.producer_root,
            command=settings.producer_command,
        )
        producer_result = runner.run(timeout_seconds=settings.timeout_seconds)
        result = {
            "job_name": "daily_fact_data_production",
            "run_id": run_id,
            "status": "success" if producer_result.success else "failed",
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "timeout_seconds": settings.timeout_seconds,
            "schedule_config_path": settings.schedule_config_path,
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
        if settings.job_result_path:
            write_json_payload(settings.job_result_path, result)
        _print_json(result)
        return 0 if producer_result.success else 1
    except Exception as exc:  # pragma: no cover - failure branch is integration-oriented
        result = {
            "job_name": "daily_fact_data_production",
            "run_id": run_id,
            "status": "failed",
            "started_at": started_at,
            "finished_at": utc_now_iso(),
            "timeout_seconds": (
                settings.timeout_seconds
                if settings is not None
                else args.timeout_seconds if args.timeout_seconds is not None else DEFAULT_TIMEOUT_SECONDS
            ),
            "schedule_config_path": (
                settings.schedule_config_path
                if settings is not None
                else args.schedule_config_path
            ),
            "error_message": str(exc),
        }
        result_path = settings.job_result_path if settings is not None else args.job_result_path
        if result_path:
            write_json_payload(result_path, result)
        _print_json(result)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
