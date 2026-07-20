"""Tests for the steady-uptrend MVP email notification job."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from workflows.jobs.daily_steady_uptrend_mvp_email import (
    EmailSchedule,
    SmtpSecret,
    execute_email_job,
    load_email_report,
    main,
    render_email,
)


class DailySteadyUptrendMvpEmailReportTest(unittest.TestCase):
    def test_loads_matching_success_artifacts(self) -> None:
        with TemporaryDirectory() as directory:
            schedule = _write_artifacts(Path(directory))

            bundle = load_email_report(schedule)

        self.assertEqual("20260716", bundle.trade_date)
        self.assertEqual("steady-uptrend-mvp-test", bundle.run_id)
        self.assertEqual(1, bundle.candidate_count)
        self.assertEqual("海思科", bundle.candidates[0]["name"])

    def test_rejects_failed_selection_job(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            schedule = _write_artifacts(root)
            job_path = root / "reports/20260716/job_result.json"
            job = json.loads(job_path.read_text(encoding="utf-8"))
            job["status"] = "failed"
            job_path.write_text(json.dumps(job), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "selection job is not successful"):
                load_email_report(schedule)

    def test_rejects_strategy_identity_mismatch(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            schedule = _write_artifacts(root)
            result_path = root / "runs/20260716/result.json"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["strategy_id"] = "strategy.unapproved"
            result_path.write_text(json.dumps(result), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "strategy identity mismatch"):
                load_email_report(schedule)

    def test_renders_grouped_candidate_and_escapes_artifact_text(self) -> None:
        with TemporaryDirectory() as directory:
            schedule = _write_artifacts(Path(directory), candidate_name="海思科<script>")
            rendered = render_email(load_email_report(schedule))

        self.assertIn("2026-07-16", rendered.subject)
        self.assertIn("海思科&lt;script&gt;", rendered.html)
        self.assertNotIn("海思科<script>", rendered.html)
        self.assertIn("002653.SZ", rendered.html)
        self.assertIn("创新药", rendered.html)
        self.assertIn("20.9%", rendered.html)
        self.assertIn("S5 介入筛选", rendered.html)
        self.assertIn("MA20 偏离度仅作诊断和排序", rendered.html)

    def test_zero_candidate_email_contains_stage_and_blocker_summary(self) -> None:
        with TemporaryDirectory() as directory:
            schedule = _write_artifacts(Path(directory), candidate_count=0)
            rendered = render_email(load_email_report(schedule))

        self.assertIn("无最终入选", rendered.html)
        self.assertIn("S3 形态召回", rendered.html)
        self.assertIn("S4 稳健性精筛", rendered.html)
        self.assertIn("收盘价未站上 MA5", rendered.html)
        self.assertIn("5", rendered.html)
        self.assertNotIn("market_cap_below_minimum", rendered.html)
        self.assertIn("无最终入选", rendered.plain_text)


class DailySteadyUptrendMvpEmailDeliveryTest(unittest.TestCase):
    def test_schedule_loads_valid_config(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "schedule.json"
            config_path.write_text(
                json.dumps(_schedule_payload(root)),
                encoding="utf-8",
            )

            schedule = EmailSchedule.load(config_path)

        self.assertEqual("smtp.163.com", schedule.smtp_host)
        self.assertEqual(465, schedule.smtp_port)
        self.assertEqual(("recipient@example.com",), schedule.recipients)

    def test_schedule_rejects_wrong_job_binding(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            payload = _schedule_payload(root)
            payload["job"] = "wrong.py"
            config_path = root / "schedule.json"
            config_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "job path is invalid"):
                EmailSchedule.load(config_path)

    def test_secret_requires_mode_0600(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "smtp.json"
            path.write_text(
                json.dumps(
                    {
                        "username": "sender@example.com",
                        "authorization_code": "fixture-authorization-value",
                    }
                ),
                encoding="utf-8",
            )
            path.chmod(0o644)

            with self.assertRaisesRegex(ValueError, "permissions must be 0600"):
                SmtpSecret.load(path)

            path.chmod(0o600)
            secret = SmtpSecret.load(path)

        self.assertEqual("sender@example.com", secret.username)

    def test_new_report_writes_sending_ledger_before_delivery(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            schedule = _write_artifacts(root)
            _write_secret(schedule.smtp_secret_path)
            observed: list[str] = []

            def sender(active_schedule, secret, rendered) -> None:
                ledger = json.loads(
                    (schedule.delivery_root / "20260716.json").read_text(encoding="utf-8")
                )
                observed.append(ledger["status"])
                self.assertEqual("sender@example.com", secret.username)
                self.assertIn("2026-07-16", rendered.subject)

            exit_code, result = execute_email_job(schedule, smtp_sender=sender)

            ledger = json.loads(
                (schedule.delivery_root / "20260716.json").read_text(encoding="utf-8")
            )

        self.assertEqual(0, exit_code)
        self.assertEqual(["sending"], observed)
        self.assertEqual("sent", result["status"])
        self.assertEqual("sent", ledger["status"])
        self.assertNotIn("authorization_code", json.dumps(ledger))

    def test_success_ledger_prevents_duplicate_delivery(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            schedule = _write_artifacts(root)
            _write_secret(schedule.smtp_secret_path)
            schedule.delivery_root.mkdir(parents=True)
            (schedule.delivery_root / "20260716.json").write_text(
                json.dumps(
                    {
                        "status": "sent",
                        "strategy_id": "strategy.steady_uptrend_mvp",
                        "strategy_version": "v1",
                        "trade_date": "20260716",
                        "run_id": "steady-uptrend-mvp-test",
                    }
                ),
                encoding="utf-8",
            )
            sender = mock.Mock()

            exit_code, result = execute_email_job(schedule, smtp_sender=sender)

        self.assertEqual(0, exit_code)
        self.assertEqual("already_sent", result["status"])
        sender.assert_not_called()

    def test_delivery_failure_is_retried_and_secret_is_redacted(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            schedule = _write_artifacts(root)
            _write_secret(schedule.smtp_secret_path)
            secret_value = "fixture-authorization-value"
            sender = mock.Mock(side_effect=RuntimeError(f"transport failed {secret_value}"))

            exit_code, result = execute_email_job(schedule, smtp_sender=sender)

            ledger_text = (schedule.delivery_root / "20260716.json").read_text(
                encoding="utf-8"
            )

        self.assertEqual(1, exit_code)
        self.assertEqual("failed", result["status"])
        self.assertEqual("smtp_delivery", result["failed_stage"])
        self.assertEqual(3, sender.call_count)
        self.assertNotIn(secret_value, json.dumps(result))
        self.assertNotIn(secret_value, ledger_text)

    def test_main_prints_structured_failure_for_bad_schedule(self) -> None:
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "schedule.json"
            config_path.write_text("{}", encoding="utf-8")

            with mock.patch("builtins.print") as printer:
                exit_code = main(["--schedule-config-path", str(config_path)])

        self.assertEqual(1, exit_code)
        payload = json.loads(printer.call_args.args[0])
        self.assertEqual("failed", payload["status"])
        self.assertEqual("initialize", payload["failed_stage"])


def _write_artifacts(
    root: Path,
    *,
    candidate_count: int = 1,
    candidate_name: str = "海思科",
) -> EmailSchedule:
    report_dir = root / "reports/20260716"
    run_dir = root / "runs/20260716"
    report_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    latest_path = root / "reports/latest.json"
    job_path = report_dir / "job_result.json"
    result_path = run_dir / "result.json"
    latest_path.write_text(
        json.dumps(
            {
                "trade_date": "20260716",
                "strategy_id": "strategy.steady_uptrend_mvp",
                "strategy_version": "v1",
                "report_dir": str(report_dir),
                "job_result_path": str(job_path),
            }
        ),
        encoding="utf-8",
    )
    stage_counts = {
        "s1_quality_filter": {"input": 5524, "passed": 1409, "rejected": 4115},
        "s2_mature_trend_filter": {"input": 1409, "passed": 44, "rejected": 1365},
        "s3_structure_recall": {"input": 44, "passed": 34, "rejected": 10},
        "s4_stability_refinement": {"input": 34, "passed": 29, "rejected": 5},
        "s5_entry_selection": {
            "input": 29 if candidate_count else 6,
            "passed": candidate_count,
            "rejected": 28 if candidate_count else 6,
        },
    }
    job_path.write_text(
        json.dumps(
            {
                "status": "success",
                "trade_date": "20260716",
                "strategy_id": "strategy.steady_uptrend_mvp",
                "strategy_version": "v1",
                "strategy_status": "test_tracking",
                "run_id": "steady-uptrend-mvp-test",
                "candidate_count": candidate_count,
                "stage_counts": stage_counts,
                "data_dependency_versions": {"daily_kline": "v1:test"},
                "run_dir": str(run_dir),
                "report_dir": str(report_dir),
            }
        ),
        encoding="utf-8",
    )
    candidate = {
        "asset_id": "002653.SZ",
        "name": candidate_name,
        "industry": "化学制药",
        "ma20_deviation_pct": 0.209146,
        "ma20_deviation_level": "20",
        "strong_concept_names": ["创新药"],
    }
    candidates = [candidate] if candidate_count else []
    groups = (
        [{"industry": "化学制药", "candidate_count": 1, "stocks": candidates}]
        if candidates
        else []
    )
    result_path.write_text(
        json.dumps(
            {
                "strategy_id": "strategy.steady_uptrend_mvp",
                "version": "v1",
                "status": "test_tracking",
                "signal_date": "20260716",
                "run_id": "steady-uptrend-mvp-test",
                "stage_counts": stage_counts,
                "data_dependency_versions": {"daily_kline": "v1:test"},
                "candidates": candidates,
                "industry_groups": groups,
                "blocker_counts": {
                    "close_not_above_ma5": 5,
                    "context_strength_unavailable": 4,
                    "market_cap_below_minimum": 3812,
                },
            }
        ),
        encoding="utf-8",
    )
    return EmailSchedule(
        latest_result_path=latest_path,
        delivery_root=root / "delivery",
        job_result_root=root / "email_job_results",
        lock_path=root / "email.lock",
        smtp_secret_path=root / "smtp.json",
        smtp_host="smtp.163.com",
        smtp_port=465,
        sender="sender@example.com",
        recipients=("recipient@example.com",),
        max_attempts=3,
    )


def _schedule_payload(root: Path) -> dict[str, object]:
    return {
        "enabled": True,
        "status": "test_tracking",
        "job": "workflows/jobs/daily_steady_uptrend_mvp_email.py",
        "latest_result_path": str(root / "reports/latest.json"),
        "delivery_root": str(root / "delivery"),
        "job_result_root": str(root / "email_job_results"),
        "lock_path": str(root / "email.lock"),
        "smtp_secret_path": str(root / "smtp.json"),
        "smtp_host": "smtp.163.com",
        "smtp_port": 465,
        "sender": "sender@example.com",
        "recipients": ["recipient@example.com"],
        "max_attempts": 3,
    }


def _write_secret(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "username": "sender@example.com",
                "authorization_code": "fixture-authorization-value",
            }
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)


if __name__ == "__main__":
    unittest.main()
