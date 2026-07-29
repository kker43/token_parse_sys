"""Execution wrappers for an external fact-data producer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import subprocess
import time


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tail_lines(text: str | bytes | None, limit: int = 40) -> tuple[str, ...]:
    if not text:
        return ()
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    return tuple(lines[-limit:])


def _linux_descendant_pids(root_pid: int) -> tuple[int, ...]:
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return ()

    children_by_parent: dict[int, list[int]] = {}
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text(encoding="utf-8")
            fields = stat[stat.rfind(")") + 2 :].split()
            parent_pid = int(fields[1])
        except (FileNotFoundError, IndexError, PermissionError, ValueError):
            continue
        children_by_parent.setdefault(parent_pid, []).append(int(entry.name))

    descendants: list[int] = []
    pending = list(children_by_parent.get(root_pid, ()))
    while pending:
        pid = pending.pop()
        descendants.append(pid)
        pending.extend(children_by_parent.get(pid, ()))
    return tuple(descendants)


def _pid_exists(pid: int) -> bool:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        if stat[stat.rfind(")") + 2 :].split()[0] == "Z":
            return False
    except FileNotFoundError:
        return False
    except (IndexError, PermissionError):
        pass

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_process_tree(
    process: subprocess.Popen[str],
    grace_seconds: float = 2.0,
) -> None:
    """Terminate one producer process and descendants, including nested groups."""

    descendant_pids = _linux_descendant_pids(process.pid)
    if descendant_pids:
        target_pids = (*descendant_pids, process.pid)
        for pid in target_pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            process.poll()
            if not any(_pid_exists(pid) for pid in target_pids):
                return
            try:
                process.wait(timeout=0.05)
            except subprocess.TimeoutExpired:
                pass

        for pid in target_pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()
        return

    process_group_id = process.pid
    try:
        os.killpg(process_group_id, signal.SIGTERM)
        process.wait(timeout=grace_seconds)
    except ProcessLookupError:
        process.wait()
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        os.killpg(process_group_id, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


@dataclass(frozen=True, slots=True)
class ExternalFactSourceMetadata:
    """Resolved provenance for one external factual-producer checkout."""

    producer_name: str
    producer_root: str
    producer_branch: str
    producer_commit: str


@dataclass(frozen=True, slots=True)
class ExternalFactProductionRunResult:
    """Structured result for one wrapped external-producer routine run."""

    success: bool
    command: tuple[str, ...]
    returncode: int | None
    started_at: str
    finished_at: str
    producer_name: str
    producer_root: str
    producer_branch: str
    producer_commit: str
    stdout_tail: tuple[str, ...]
    stderr_tail: tuple[str, ...]
    error_message: str | None = None


class ExternalFactProductionRunner:
    """Wrap an external factual-producer command without inlining producer logic."""

    def __init__(
        self,
        producer_name: str = "external_producer",
        producer_root: str | Path = ".",
        command: tuple[str, ...] | None = None,
    ):
        self.producer_name = producer_name
        self.producer_root = Path(producer_root)
        self.command = tuple(command or ())

    def collect_source_metadata(self) -> ExternalFactSourceMetadata:
        """Collect git provenance for the configured producer checkout."""

        return ExternalFactSourceMetadata(
            producer_name=self.producer_name,
            producer_root=str(self.producer_root),
            producer_branch=self._git_output(("branch", "--show-current")),
            producer_commit=self._git_output(("rev-parse", "HEAD")),
        )

    def resolve_command(self, command: tuple[str, ...] | None = None) -> tuple[str, ...]:
        """Resolve the command that should be executed."""

        resolved = tuple(command or self.command)
        if not resolved:
            raise ValueError("producer command must not be empty")
        return resolved

    def run(
        self,
        command: tuple[str, ...] | None = None,
        timeout_seconds: int = 14_400,
    ) -> ExternalFactProductionRunResult:
        """Execute one external factual-producer command and capture structured evidence."""

        metadata = self.collect_source_metadata()
        resolved_command = self.resolve_command(command)
        started_at = _utc_now_iso()

        try:
            process = subprocess.Popen(
                resolved_command,
                cwd=self.producer_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                _terminate_process_tree(process)
                stdout, stderr = process.communicate()
                finished_at = _utc_now_iso()
                return ExternalFactProductionRunResult(
                    success=False,
                    command=resolved_command,
                    returncode=None,
                    started_at=started_at,
                    finished_at=finished_at,
                    producer_name=metadata.producer_name,
                    producer_root=metadata.producer_root,
                    producer_branch=metadata.producer_branch,
                    producer_commit=metadata.producer_commit,
                    stdout_tail=_tail_lines(stdout),
                    stderr_tail=_tail_lines(stderr),
                    error_message=f"timeout_after_seconds:{timeout_seconds}",
                )

            finished_at = _utc_now_iso()
            return ExternalFactProductionRunResult(
                success=process.returncode == 0,
                command=resolved_command,
                returncode=process.returncode,
                started_at=started_at,
                finished_at=finished_at,
                producer_name=metadata.producer_name,
                producer_root=metadata.producer_root,
                producer_branch=metadata.producer_branch,
                producer_commit=metadata.producer_commit,
                stdout_tail=_tail_lines(stdout),
                stderr_tail=_tail_lines(stderr),
                error_message=None if process.returncode == 0 else f"producer_returncode:{process.returncode}",
            )
        except Exception as exc:
            finished_at = _utc_now_iso()
            return ExternalFactProductionRunResult(
                success=False,
                command=resolved_command if "resolved_command" in locals() else (),
                returncode=None,
                started_at=started_at,
                finished_at=finished_at,
                producer_name=metadata.producer_name,
                producer_root=metadata.producer_root,
                producer_branch=metadata.producer_branch,
                producer_commit=metadata.producer_commit,
                stdout_tail=(),
                stderr_tail=(),
                error_message=str(exc),
            )

    def _git_output(self, args: tuple[str, ...]) -> str:
        try:
            completed = subprocess.run(
                ("git", "-C", str(self.producer_root), *args),
                capture_output=True,
                text=True,
                check=True,
            )
        except Exception:
            return "unknown"

        output = completed.stdout.strip()
        return output or "unknown"
