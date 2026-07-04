"""Tests for the fact-production wrapper workflow job."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from workflows.jobs.daily_fact_data_production import main


def init_git_repo(root: Path) -> None:
    subprocess.run(("git", "init", "-b", "main"), cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(("git", "add", "."), cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(
        ("git", "commit", "-m", "init upstream fixture"),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


class DailyFactDataProductionJobTest(unittest.TestCase):
    def test_job_wraps_upstream_master_scheduler(self) -> None:
        with TemporaryDirectory() as tempdir:
            upstream_root = Path(tempdir)
            (upstream_root / "cron_script").mkdir()
            (upstream_root / "cron_script" / "daily_master_scheduler.py").write_text(
                "print('master scheduler success')\n",
                encoding="utf-8",
            )
            init_git_repo(upstream_root)
            job_result_path = upstream_root / "job_result.json"

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--upstream-root",
                        str(upstream_root),
                        "--upstream-python",
                        sys.executable,
                        "--job-result-path",
                        str(job_result_path),
                    ]
                )

            payload = json.loads(job_result_path.read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        self.assertEqual("success", payload["status"])
        self.assertEqual("main", payload["upstream"]["branch"])
        self.assertIn("--now", payload["upstream"]["command"])

    def test_job_returns_non_zero_when_upstream_fails(self) -> None:
        with TemporaryDirectory() as tempdir:
            upstream_root = Path(tempdir)
            (upstream_root / "cron_script").mkdir()
            (upstream_root / "cron_script" / "daily_master_scheduler.py").write_text(
                "import sys\nsys.exit(5)\n",
                encoding="utf-8",
            )
            init_git_repo(upstream_root)
            job_result_path = upstream_root / "job_result.json"

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--upstream-root",
                        str(upstream_root),
                        "--upstream-python",
                        sys.executable,
                        "--run-mode",
                        "schedule",
                        "--job-result-path",
                        str(job_result_path),
                    ]
                )

            payload = json.loads(job_result_path.read_text(encoding="utf-8"))

        self.assertEqual(1, exit_code)
        self.assertEqual("failed", payload["status"])
        self.assertEqual(5, payload["upstream"]["returncode"])
        self.assertNotIn("--now", payload["upstream"]["command"])

    def test_job_script_runs_as_direct_file_entrypoint(self) -> None:
        with TemporaryDirectory() as tempdir:
            upstream_root = Path(tempdir)
            (upstream_root / "cron_script").mkdir()
            (upstream_root / "cron_script" / "daily_master_scheduler.py").write_text(
                "print('direct script entrypoint ok')\n",
                encoding="utf-8",
            )
            init_git_repo(upstream_root)
            job_result_path = upstream_root / "job_result.json"
            repo_root = Path(__file__).resolve().parents[2]
            script_path = repo_root / "workflows" / "jobs" / "daily_fact_data_production.py"

            completed = subprocess.run(
                (
                    sys.executable,
                    str(script_path),
                    "--upstream-root",
                    str(upstream_root),
                    "--upstream-python",
                    sys.executable,
                    "--job-result-path",
                    str(job_result_path),
                ),
                cwd=repo_root,
                check=False,
                capture_output=True,
                text=True,
            )
            payload = json.loads(job_result_path.read_text(encoding="utf-8"))

        self.assertEqual(0, completed.returncode, msg=completed.stderr)
        self.assertEqual("success", payload["status"])
