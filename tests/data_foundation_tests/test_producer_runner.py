"""Tests for wrapping upstream token_fetch production entrypoints."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from data_foundation.token_fetch_bridge import TokenFetchRoutineRunner


def init_git_repo(root: Path) -> str:
    subprocess.run(("git", "init", "-b", "main"), cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(("git", "add", "."), cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(
        ("git", "commit", "-m", "init upstream fixture"),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    completed = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


class TokenFetchRoutineRunnerTest(unittest.TestCase):
    def test_runs_daily_master_scheduler_and_captures_git_metadata(self) -> None:
        with TemporaryDirectory() as tempdir:
            upstream_root = Path(tempdir)
            (upstream_root / "cron_script").mkdir()
            script_path = upstream_root / "cron_script" / "daily_master_scheduler.py"
            script_path.write_text(
                "import sys\n"
                "print('scheduler fixture ran')\n"
                "print('args=' + ' '.join(sys.argv[1:]))\n",
                encoding="utf-8",
            )
            expected_commit = init_git_repo(upstream_root)

            runner = TokenFetchRoutineRunner(
                upstream_root=upstream_root,
                python_executable=sys.executable,
            )
            result = runner.run_daily_master_scheduler(now=True, timeout_seconds=30)

        self.assertTrue(result.success)
        self.assertEqual(0, result.returncode)
        self.assertEqual("main", result.upstream_branch)
        self.assertEqual(expected_commit, result.upstream_commit)
        self.assertEqual("scheduler fixture ran", result.stdout_tail[0])
        self.assertIn("--now", result.command)

    def test_reports_failure_when_upstream_scheduler_fails(self) -> None:
        with TemporaryDirectory() as tempdir:
            upstream_root = Path(tempdir)
            (upstream_root / "cron_script").mkdir()
            script_path = upstream_root / "cron_script" / "daily_master_scheduler.py"
            script_path.write_text(
                "import sys\n"
                "print('failing fixture ran')\n"
                "sys.exit(3)\n",
                encoding="utf-8",
            )
            init_git_repo(upstream_root)

            runner = TokenFetchRoutineRunner(
                upstream_root=upstream_root,
                python_executable=sys.executable,
            )
            result = runner.run_daily_master_scheduler(now=False, timeout_seconds=30)

        self.assertFalse(result.success)
        self.assertEqual(3, result.returncode)
        self.assertEqual("upstream_returncode:3", result.error_message)
        self.assertNotIn("--now", result.command)
