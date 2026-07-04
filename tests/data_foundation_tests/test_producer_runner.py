"""Tests for wrapping external fact-production entrypoints."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from data_foundation.provider_bridge import ExternalFactProductionRunner


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


class ExternalFactProductionRunnerTest(unittest.TestCase):
    def test_runs_external_command_and_captures_git_metadata(self) -> None:
        with TemporaryDirectory() as tempdir:
            producer_root = Path(tempdir)
            script_path = producer_root / "producer_task.py"
            script_path.write_text(
                "import sys\n"
                "print('scheduler fixture ran')\n"
                "print('args=' + ' '.join(sys.argv[1:]))\n",
                encoding="utf-8",
            )
            expected_commit = init_git_repo(producer_root)

            runner = ExternalFactProductionRunner(
                producer_name="sample_provider",
                producer_root=producer_root,
                command=(sys.executable, str(script_path), "--date", "20260704"),
            )
            result = runner.run(timeout_seconds=30)

        self.assertTrue(result.success)
        self.assertEqual(0, result.returncode)
        self.assertEqual("sample_provider", result.producer_name)
        self.assertEqual("main", result.producer_branch)
        self.assertEqual(expected_commit, result.producer_commit)
        self.assertEqual("scheduler fixture ran", result.stdout_tail[0])
        self.assertIn("--date", result.command)

    def test_reports_failure_when_external_command_fails(self) -> None:
        with TemporaryDirectory() as tempdir:
            producer_root = Path(tempdir)
            script_path = producer_root / "producer_task.py"
            script_path.write_text(
                "import sys\n"
                "print('failing fixture ran')\n"
                "sys.exit(3)\n",
                encoding="utf-8",
            )
            init_git_repo(producer_root)

            runner = ExternalFactProductionRunner(
                producer_root=producer_root,
                command=(sys.executable, str(script_path)),
            )
            result = runner.run(timeout_seconds=30)

        self.assertFalse(result.success)
        self.assertEqual(3, result.returncode)
        self.assertEqual("producer_returncode:3", result.error_message)
