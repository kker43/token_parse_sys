"""Execution wrappers for the upstream token_fetch routine producer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tail_lines(text: str | None, limit: int = 40) -> tuple[str, ...]:
    if not text:
        return ()
    lines = [line for line in text.splitlines() if line.strip()]
    return tuple(lines[-limit:])


@dataclass(frozen=True, slots=True)
class TokenFetchSourceMetadata:
    """Resolved provenance for one upstream token_fetch checkout."""

    upstream_root: str
    upstream_branch: str
    upstream_commit: str


@dataclass(frozen=True, slots=True)
class TokenFetchRoutineRunResult:
    """Structured result for one wrapped token_fetch routine run."""

    success: bool
    command: tuple[str, ...]
    returncode: int | None
    started_at: str
    finished_at: str
    upstream_root: str
    upstream_branch: str
    upstream_commit: str
    stdout_tail: tuple[str, ...]
    stderr_tail: tuple[str, ...]
    error_message: str | None = None


class TokenFetchRoutineRunner:
    """Wrap stable token_fetch scheduler entrypoints without inlining producer logic."""

    def __init__(self, upstream_root: str | Path = "/home/ubuntu/token_fetch", python_executable: str | None = None):
        self.upstream_root = Path(upstream_root)
        self.python_executable = python_executable

    def collect_source_metadata(self) -> TokenFetchSourceMetadata:
        """Collect git provenance for the current upstream checkout."""

        return TokenFetchSourceMetadata(
            upstream_root=str(self.upstream_root),
            upstream_branch=self._git_output(("branch", "--show-current")),
            upstream_commit=self._git_output(("rev-parse", "HEAD")),
        )

    def resolve_python_executable(self) -> str:
        """Resolve the python executable for the upstream producer."""

        if self.python_executable is not None:
            return self.python_executable

        candidate = self.upstream_root / "venv" / "bin" / "python3"
        if candidate.exists():
            return str(candidate)
        return sys.executable

    def build_daily_master_command(self, now: bool = True) -> tuple[str, ...]:
        """Build the stable upstream daily master scheduler command."""

        script_path = self.upstream_root / "cron_script" / "daily_master_scheduler.py"
        command = [self.resolve_python_executable(), str(script_path)]
        if now:
            command.append("--now")
        return tuple(command)

    def run_daily_master_scheduler(
        self,
        now: bool = True,
        timeout_seconds: int = 14_400,
    ) -> TokenFetchRoutineRunResult:
        """Execute token_fetch daily master scheduler and capture structured evidence."""

        metadata = self.collect_source_metadata()
        command = self.build_daily_master_command(now=now)
        started_at = _utc_now_iso()

        try:
            completed = subprocess.run(
                command,
                cwd=self.upstream_root,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            finished_at = _utc_now_iso()
            return TokenFetchRoutineRunResult(
                success=completed.returncode == 0,
                command=command,
                returncode=completed.returncode,
                started_at=started_at,
                finished_at=finished_at,
                upstream_root=metadata.upstream_root,
                upstream_branch=metadata.upstream_branch,
                upstream_commit=metadata.upstream_commit,
                stdout_tail=_tail_lines(completed.stdout),
                stderr_tail=_tail_lines(completed.stderr),
                error_message=None if completed.returncode == 0 else f"upstream_returncode:{completed.returncode}",
            )
        except subprocess.TimeoutExpired as exc:
            finished_at = _utc_now_iso()
            return TokenFetchRoutineRunResult(
                success=False,
                command=command,
                returncode=None,
                started_at=started_at,
                finished_at=finished_at,
                upstream_root=metadata.upstream_root,
                upstream_branch=metadata.upstream_branch,
                upstream_commit=metadata.upstream_commit,
                stdout_tail=_tail_lines(exc.stdout),
                stderr_tail=_tail_lines(exc.stderr),
                error_message=f"timeout_after_seconds:{timeout_seconds}",
            )
        except Exception as exc:
            finished_at = _utc_now_iso()
            return TokenFetchRoutineRunResult(
                success=False,
                command=command,
                returncode=None,
                started_at=started_at,
                finished_at=finished_at,
                upstream_root=metadata.upstream_root,
                upstream_branch=metadata.upstream_branch,
                upstream_commit=metadata.upstream_commit,
                stdout_tail=(),
                stderr_tail=(),
                error_message=str(exc),
            )

    def _git_output(self, args: tuple[str, ...]) -> str:
        try:
            completed = subprocess.run(
                ("git", "-C", str(self.upstream_root), *args),
                capture_output=True,
                text=True,
                check=True,
            )
        except Exception:
            return "unknown"

        output = completed.stdout.strip()
        return output or "unknown"
