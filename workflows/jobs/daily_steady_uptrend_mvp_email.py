"""Email notification for published steady-uptrend MVP tracking results."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from email.message import EmailMessage
import fcntl
from html import escape
import json
import os
from pathlib import Path
import smtplib
import ssl
import stat
import sys
from typing import Callable, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workflows.jobs.support import utc_now_iso


APPROVED_STRATEGY_ID = "strategy.steady_uptrend_mvp"
APPROVED_STRATEGY_VERSION = "v1"
APPROVED_STRATEGY_STATUS = "test_tracking"

STAGE_LABELS = {
    "s1_quality_filter": "S1 质量过滤",
    "s2_mature_trend_filter": "S2 成熟趋势过滤",
    "s3_structure_recall": "S3 形态召回",
    "s4_stability_refinement": "S4 稳健性精筛",
    "s5_entry_selection": "S5 介入筛选",
}

BLOCKER_LABELS = {
    "close_not_above_ma5": "收盘价未站上 MA5",
    "close_too_far_below_prior_high_20d": "距离前20日高点低于 -5%",
    "context_strength_unavailable": "未命中强势行业或概念",
    "noisy_shadow_ma_flip_composite": "影线与均线切换组合不稳健",
    "frequent_extreme_bearish_days_10d": "近10日大阴柱过多",
    "low_red_k_ratio_60d": "近60日阳线比例不足",
}

S5_BLOCKER_KEYS = (
    "context_strength_unavailable",
    "close_not_above_ma5",
    "close_too_far_below_prior_high_20d",
)


@dataclass(frozen=True, slots=True)
class EmailSchedule:
    """Paths and SMTP metadata for one email notification run."""

    latest_result_path: Path
    delivery_root: Path
    job_result_root: Path
    lock_path: Path
    smtp_secret_path: Path
    smtp_host: str
    smtp_port: int
    sender: str
    recipients: tuple[str, ...]
    max_attempts: int

    @classmethod
    def load(cls, path: str | Path) -> "EmailSchedule":
        payload = _read_json_object(path)
        if payload.get("enabled") is not True:
            raise ValueError("email schedule must be enabled")
        if payload.get("status") != APPROVED_STRATEGY_STATUS:
            raise ValueError("email schedule status must be test_tracking")
        if payload.get("job") != "workflows/jobs/daily_steady_uptrend_mvp_email.py":
            raise ValueError("email schedule job path is invalid")
        recipients = payload.get("recipients")
        if (
            not isinstance(recipients, list)
            or not recipients
            or not all(isinstance(value, str) and value.strip() for value in recipients)
        ):
            raise ValueError("recipients must be a non-empty string array")
        return cls(
            latest_result_path=Path(_required_string(payload, "latest_result_path")),
            delivery_root=Path(_required_string(payload, "delivery_root")),
            job_result_root=Path(_required_string(payload, "job_result_root")),
            lock_path=Path(_required_string(payload, "lock_path")),
            smtp_secret_path=Path(_required_string(payload, "smtp_secret_path")),
            smtp_host=_required_string(payload, "smtp_host"),
            smtp_port=_positive_int(payload, "smtp_port"),
            sender=_required_string(payload, "sender"),
            recipients=tuple(str(value).strip() for value in recipients),
            max_attempts=_positive_int(payload, "max_attempts"),
        )


@dataclass(frozen=True, slots=True)
class SmtpSecret:
    """Remote-only SMTP credential loaded after strict mode validation."""

    username: str
    authorization_code: str

    @classmethod
    def load(cls, path: str | Path) -> "SmtpSecret":
        secret_path = Path(path)
        mode = stat.S_IMODE(secret_path.stat().st_mode)
        if mode != 0o600:
            raise ValueError("SMTP secret permissions must be 0600")
        payload = _read_json_object(secret_path)
        return cls(
            username=_required_string(payload, "username"),
            authorization_code=_required_string(payload, "authorization_code"),
        )


@dataclass(frozen=True, slots=True)
class EmailReportBundle:
    """Validated selection artifacts needed to render one notification."""

    trade_date: str
    strategy_id: str
    strategy_version: str
    strategy_status: str
    run_id: str
    candidate_count: int
    stage_counts: Mapping[str, object]
    data_dependency_versions: Mapping[str, object]
    candidates: tuple[Mapping[str, object], ...]
    industry_groups: tuple[Mapping[str, object], ...]
    blocker_counts: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    """Multipart email content before SMTP transport."""

    subject: str
    plain_text: str
    html: str


SmtpSender = Callable[[EmailSchedule, SmtpSecret, RenderedEmail], None]


def load_email_report(schedule: EmailSchedule) -> EmailReportBundle:
    """Load and validate the latest authoritative tracking artifacts."""

    latest = _read_json_object(schedule.latest_result_path)
    trade_date = _required_string(latest, "trade_date")
    job_path = Path(_required_string(latest, "job_result_path"))
    job = _read_json_object(job_path)
    if job.get("status") != "success":
        raise ValueError("selection job is not successful")

    run_dir = Path(_required_string(job, "run_dir"))
    result = _read_json_object(run_dir / "result.json")
    identity = (
        str(job.get("strategy_id") or ""),
        str(job.get("strategy_version") or ""),
        str(result.get("strategy_id") or ""),
        str(result.get("version") or ""),
    )
    expected = (
        APPROVED_STRATEGY_ID,
        APPROVED_STRATEGY_VERSION,
        APPROVED_STRATEGY_ID,
        APPROVED_STRATEGY_VERSION,
    )
    if identity != expected:
        raise ValueError("strategy identity mismatch")
    if latest.get("strategy_id") != APPROVED_STRATEGY_ID:
        raise ValueError("strategy identity mismatch")
    if latest.get("strategy_version") != APPROVED_STRATEGY_VERSION:
        raise ValueError("strategy identity mismatch")
    if job.get("strategy_status") != APPROVED_STRATEGY_STATUS:
        raise ValueError("strategy status mismatch")
    if result.get("status") != APPROVED_STRATEGY_STATUS:
        raise ValueError("strategy status mismatch")
    if job.get("trade_date") != trade_date or result.get("signal_date") != trade_date:
        raise ValueError("trade date mismatch")
    run_id = _required_string(job, "run_id")
    if result.get("run_id") != run_id:
        raise ValueError("run id mismatch")

    candidates = _mapping_tuple(result.get("candidates"), "candidates")
    industry_groups = _mapping_tuple(
        result.get("industry_groups"),
        "industry_groups",
    )
    candidate_count = int(job.get("candidate_count", -1))
    if candidate_count != len(candidates):
        raise ValueError("candidate count mismatch")

    return EmailReportBundle(
        trade_date=trade_date,
        strategy_id=APPROVED_STRATEGY_ID,
        strategy_version=APPROVED_STRATEGY_VERSION,
        strategy_status=APPROVED_STRATEGY_STATUS,
        run_id=run_id,
        candidate_count=candidate_count,
        stage_counts=_mapping(result.get("stage_counts"), "stage_counts"),
        data_dependency_versions=_mapping(
            result.get("data_dependency_versions"),
            "data_dependency_versions",
        ),
        candidates=candidates,
        industry_groups=industry_groups,
        blocker_counts=_mapping(result.get("blocker_counts"), "blocker_counts"),
    )


def render_email(bundle: EmailReportBundle) -> RenderedEmail:
    """Render HTML and plain-text alternatives from validated artifacts."""

    display_date = (
        f"{bundle.trade_date[:4]}-{bundle.trade_date[4:6]}-{bundle.trade_date[6:8]}"
    )
    subject = f"【Stock Lobster】{display_date} 稳步上行选股 {bundle.candidate_count}只"
    stage_rows = "".join(_render_stage_row(stage, bundle.stage_counts) for stage in STAGE_LABELS)
    candidate_html = _render_candidate_groups(bundle)
    dependency_text = "；".join(
        f"{key}={value}"
        for key, value in sorted(bundle.data_dependency_versions.items())
    )
    html = f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;background:#f5f6f8;color:#1f2937;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif;">
  <div style="max-width:760px;margin:0 auto;padding:24px 14px;">
    <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
      <div style="padding:20px 24px;background:#111827;color:#ffffff;">
        <div style="font-size:13px;color:#cbd5e1;">strategy.steady_uptrend_mvp / v1 / test_tracking</div>
        <h1 style="font-size:22px;line-height:1.35;margin:6px 0 0;letter-spacing:0;">{escape(display_date)} 选股结果</h1>
      </div>
      <div style="padding:20px 24px;">
        <p style="margin:0 0 16px;font-size:16px;"><strong>最终入选：{bundle.candidate_count}只</strong></p>
        <table role="presentation" style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:22px;">
          <thead><tr><th style="text-align:left;padding:8px;border-bottom:2px solid #d1d5db;">层级</th><th style="text-align:right;padding:8px;border-bottom:2px solid #d1d5db;">输入</th><th style="text-align:right;padding:8px;border-bottom:2px solid #d1d5db;">通过</th><th style="text-align:right;padding:8px;border-bottom:2px solid #d1d5db;">淘汰</th></tr></thead>
          <tbody>{stage_rows}</tbody>
        </table>
        {candidate_html}
        <p style="font-size:12px;color:#6b7280;margin:20px 0 0;">MA20 偏离度仅作诊断和排序，不单独过滤。</p>
      </div>
      <div style="padding:14px 24px;background:#f9fafb;border-top:1px solid #e5e7eb;font-size:11px;color:#6b7280;word-break:break-all;">
        run_id: {escape(bundle.run_id)}<br>数据版本：{escape(dependency_text)}
      </div>
    </div>
  </div>
</body>
</html>"""
    plain = _render_plain_text(bundle, display_date)
    return RenderedEmail(subject=subject, plain_text=plain, html=html)


def execute_email_job(
    schedule: EmailSchedule,
    *,
    smtp_sender: SmtpSender | None = None,
) -> tuple[int, dict[str, object]]:
    """Send one new report under a lock and persist a deduplication ledger."""

    schedule.lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = schedule.lock_path.open("a+", encoding="utf-8")
    bundle: EmailReportBundle | None = None
    try:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            result = _failure_result("acquire_lock", exc, None)
            return 1, result

        try:
            bundle = load_email_report(schedule)
            ledger_path = schedule.delivery_root / f"{bundle.trade_date}.json"
            identity = _delivery_identity(bundle)
            existing = _read_optional_json_object(ledger_path)
            if existing is not None and _ledger_matches(existing, identity):
                if existing.get("status") == "sent":
                    result = {
                        **identity,
                        "schema_version": 1,
                        "job_name": "daily_steady_uptrend_mvp_email",
                        "status": "already_sent",
                        "finished_at": utc_now_iso(),
                    }
                    _write_job_result(schedule, bundle.trade_date, result)
                    return 0, result
                if existing.get("status") == "sending":
                    raise RuntimeError("delivery state is uncertain")

            secret = SmtpSecret.load(schedule.smtp_secret_path)
            if secret.username != schedule.sender:
                raise ValueError("SMTP username must match sender")
            rendered = render_email(bundle)
            sending = {
                **identity,
                "schema_version": 1,
                "job_name": "daily_steady_uptrend_mvp_email",
                "status": "sending",
                "started_at": utc_now_iso(),
                "recipient_count": len(schedule.recipients),
            }
            _atomic_write_json(ledger_path, sending)

            active_sender = smtp_sender or _send_smtp_ssl
            last_error: Exception | None = None
            for _ in range(schedule.max_attempts):
                try:
                    active_sender(schedule, secret, rendered)
                    last_error = None
                    break
                except Exception as exc:  # SMTP libraries raise several error families.
                    last_error = exc
            if last_error is not None:
                failed = _failure_result(
                    "smtp_delivery",
                    last_error,
                    bundle.trade_date,
                    identity=identity,
                )
                _atomic_write_json(ledger_path, failed)
                _write_job_result(schedule, bundle.trade_date, failed)
                return 1, failed

            sent = {
                **identity,
                "schema_version": 1,
                "job_name": "daily_steady_uptrend_mvp_email",
                "status": "sent",
                "finished_at": utc_now_iso(),
                "recipient_count": len(schedule.recipients),
                "subject": rendered.subject,
            }
            _atomic_write_json(ledger_path, sent)
            _write_job_result(schedule, bundle.trade_date, sent)
            return 0, sent
        except Exception as exc:
            trade_date = bundle.trade_date if bundle is not None else None
            identity = _delivery_identity(bundle) if bundle is not None else None
            result = _failure_result(
                "prepare_delivery",
                exc,
                trade_date,
                identity=identity,
            )
            if trade_date is not None:
                _write_job_result(schedule, trade_date, result)
            return 1, result
    finally:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        finally:
            lock_handle.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="daily_steady_uptrend_mvp_email")
    parser.add_argument("--schedule-config-path", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        schedule = EmailSchedule.load(args.schedule_config_path)
        exit_code, result = execute_email_job(schedule)
    except Exception as exc:
        exit_code = 1
        result = _failure_result("initialize", exc, None)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return exit_code


def _send_smtp_ssl(
    schedule: EmailSchedule,
    secret: SmtpSecret,
    rendered: RenderedEmail,
) -> None:
    message = EmailMessage()
    message["Subject"] = rendered.subject
    message["From"] = schedule.sender
    message["To"] = ", ".join(schedule.recipients)
    message.set_content(rendered.plain_text)
    message.add_alternative(rendered.html, subtype="html")
    with smtplib.SMTP_SSL(
        schedule.smtp_host,
        schedule.smtp_port,
        context=ssl.create_default_context(),
        timeout=30,
    ) as client:
        client.login(secret.username, secret.authorization_code)
        client.send_message(message)


def _render_stage_row(stage: str, stage_counts: Mapping[str, object]) -> str:
    counts = _mapping(stage_counts.get(stage), stage)
    values = (counts.get("input", 0), counts.get("passed", 0), counts.get("rejected", 0))
    cells = "".join(
        f'<td style="text-align:right;padding:8px;border-bottom:1px solid #e5e7eb;">{int(value)}</td>'
        for value in values
    )
    return (
        '<tr><td style="padding:8px;border-bottom:1px solid #e5e7eb;">'
        f"{escape(STAGE_LABELS[stage])}</td>{cells}</tr>"
    )


def _render_candidate_groups(bundle: EmailReportBundle) -> str:
    if bundle.candidate_count == 0:
        blockers = "".join(
            "<li style=\"margin:5px 0;\">"
            f"{escape(BLOCKER_LABELS.get(str(key), str(key)))}：{int(value)}只"
            "</li>"
            for key, value in _s5_blocker_items(bundle.blocker_counts)
        )
        return (
            '<div style="padding:16px;background:#f9fafb;border-left:4px solid #6b7280;">'
            '<strong>无最终入选</strong>'
            '<p style="font-size:13px;margin:8px 0;">S3 形态召回与 S4 稳健性精筛后，候选在 S5 介入筛选被阻断。</p>'
            f'<ul style="font-size:13px;margin:8px 0 0;padding-left:20px;">{blockers}</ul>'
            "</div>"
        )

    sections: list[str] = []
    for raw_group in bundle.industry_groups:
        industry = escape(str(raw_group.get("industry") or "未分类"))
        stocks = _mapping_tuple(raw_group.get("stocks"), "industry stocks")
        rows = "".join(_render_candidate_row(stock) for stock in stocks)
        sections.append(
            f'<h2 style="font-size:17px;margin:22px 0 8px;letter-spacing:0;">{industry}</h2>'
            '<table role="presentation" style="width:100%;border-collapse:collapse;font-size:13px;">'
            '<thead><tr><th style="text-align:left;padding:8px;border-bottom:2px solid #d1d5db;">股票</th><th style="text-align:left;padding:8px;border-bottom:2px solid #d1d5db;">概念</th><th style="text-align:right;padding:8px;border-bottom:2px solid #d1d5db;">MA20偏离</th></tr></thead>'
            f"<tbody>{rows}</tbody></table>"
        )
    return "".join(sections)


def _render_candidate_row(stock: Mapping[str, object]) -> str:
    code = escape(str(stock.get("asset_id") or ""))
    name = escape(str(stock.get("name") or ""))
    concepts = stock.get("strong_concept_names")
    concept_text = "、".join(str(value) for value in concepts) if isinstance(concepts, list) else ""
    deviation = float(stock.get("ma20_deviation_pct") or 0.0) * 100
    level = escape(str(stock.get("ma20_deviation_level") or "正常"))
    return (
        "<tr>"
        f'<td style="padding:9px 8px;border-bottom:1px solid #e5e7eb;"><strong>{name}</strong><br><span style="color:#6b7280;">{code}</span></td>'
        f'<td style="padding:9px 8px;border-bottom:1px solid #e5e7eb;">{escape(concept_text) or "-"}</td>'
        f'<td style="text-align:right;padding:9px 8px;border-bottom:1px solid #e5e7eb;">{deviation:.1f}%<br><span style="color:#6b7280;">{level}级</span></td>'
        "</tr>"
    )


def _render_plain_text(bundle: EmailReportBundle, display_date: str) -> str:
    lines = [
        f"{display_date} 稳步上行选股",
        f"最终入选：{bundle.candidate_count}只",
        "",
    ]
    for stage, label in STAGE_LABELS.items():
        counts = _mapping(bundle.stage_counts.get(stage), stage)
        lines.append(
            f"{label}：{counts.get('input', 0)} -> {counts.get('passed', 0)}"
        )
    if bundle.candidate_count == 0:
        lines.extend(("", "无最终入选", "S5主要阻断："))
        for key, value in _s5_blocker_items(bundle.blocker_counts):
            lines.append(f"- {BLOCKER_LABELS.get(str(key), str(key))}：{int(value)}只")
    else:
        for group in bundle.industry_groups:
            lines.extend(("", f"{group.get('industry') or '未分类'}："))
            for stock in _mapping_tuple(group.get("stocks"), "industry stocks"):
                deviation = float(stock.get("ma20_deviation_pct") or 0.0) * 100
                concepts = stock.get("strong_concept_names")
                concept_text = "、".join(str(value) for value in concepts) if isinstance(concepts, list) else ""
                lines.append(
                    f"- {stock.get('name')} {stock.get('asset_id')}，MA20偏离{deviation:.1f}%"
                    + (f"，概念：{concept_text}" if concept_text else "")
                )
    lines.extend(("", "MA20 偏离度仅作诊断和排序，不单独过滤。", f"run_id: {bundle.run_id}"))
    return "\n".join(lines)


def _delivery_identity(bundle: EmailReportBundle) -> dict[str, object]:
    return {
        "strategy_id": bundle.strategy_id,
        "strategy_version": bundle.strategy_version,
        "trade_date": bundle.trade_date,
        "run_id": bundle.run_id,
    }


def _s5_blocker_items(
    blocker_counts: Mapping[str, object],
) -> tuple[tuple[str, int], ...]:
    values = (
        (key, int(blocker_counts.get(key, 0)))
        for key in S5_BLOCKER_KEYS
    )
    return tuple(
        sorted(
            ((key, count) for key, count in values if count > 0),
            key=lambda item: (-item[1], item[0]),
        )
    )


def _ledger_matches(
    payload: Mapping[str, object],
    identity: Mapping[str, object],
) -> bool:
    return all(payload.get(key) == value for key, value in identity.items())


def _write_job_result(
    schedule: EmailSchedule,
    trade_date: str,
    payload: Mapping[str, object],
) -> None:
    _atomic_write_json(schedule.job_result_root / f"{trade_date}.json", payload)


def _failure_result(
    stage: str,
    cause: Exception,
    trade_date: str | None,
    *,
    identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "schema_version": 1,
        "job_name": "daily_steady_uptrend_mvp_email",
        "status": "failed",
        "finished_at": utc_now_iso(),
        "trade_date": trade_date,
        "failed_stage": stage,
        "error_type": type(cause).__name__,
        "error_message": "email notification failed",
    }
    if identity is not None:
        result.update(identity)
    return result


def _atomic_write_json(path: str | Path, payload: Mapping[str, object]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(output)


def _read_optional_json_object(path: str | Path) -> dict[str, object] | None:
    input_path = Path(path)
    if not input_path.exists():
        return None
    return _read_json_object(input_path)


def _mapping_tuple(value: object, label: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise ValueError(f"{label} must be an array of objects")
    return tuple(dict(item) for item in value)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return dict(value)


def _read_json_object(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return dict(payload)


def _required_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _positive_int(payload: Mapping[str, object], key: str) -> int:
    value = int(payload.get(key, 0))
    if value <= 0:
        raise ValueError(f"{key} must be positive")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
