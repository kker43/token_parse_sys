# Steady Uptrend Email Notification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send one deduplicated HTML email for every newly published `strategy.steady_uptrend_mvp/v1` tracking result without coupling SMTP failures to strategy execution.

**Architecture:** Add a standalone notification job that consumes `latest.json`, `job_result.json`, and the run `result.json`. It renders structured HTML, records a delivery ledger before and after SMTP SSL delivery, and is scheduled after the existing selection cron. SMTP credentials remain in a mode-`0600` remote-only JSON file.

**Tech Stack:** Python 3.12 standard library (`argparse`, `email.message`, `fcntl`, `html`, `json`, `smtplib`, `ssl`), unittest, JSON schedule files, cron.

## Global Constraints

- Do not modify S1-S5 strategy semantics or recompute market facts.
- Do not store or print the SMTP authorization code in Git, logs, reports, exceptions, or tests.
- Only consume authoritative artifacts produced by `daily_steady_uptrend_mvp_tracking.py`.
- Keep `strategy_status=test_tracking`; this notification is not a formal L5 signal.
- A valid zero-candidate run must produce a useful email rather than an empty body.
- Use `strategy_id + strategy_version + trade_date + run_id` as the delivery identity.

---

### Task 1: Report Contract and HTML Rendering

**Files:**
- Create: `workflows/jobs/daily_steady_uptrend_mvp_email.py`
- Create: `tests/workflows_tests/test_daily_steady_uptrend_mvp_email.py`

**Interfaces:**
- Consumes: `latest.json`, `job_result.json`, and `result.json` mappings.
- Produces: `EmailReportBundle`, `load_email_report(schedule)`, and `render_email(bundle) -> RenderedEmail`.

- [ ] **Step 1: Write failing report-contract tests**

Add tests that build temporary success artifacts and assert:

```python
bundle = load_email_report(schedule)
self.assertEqual("20260716", bundle.trade_date)
self.assertEqual("steady-uptrend-mvp-test", bundle.run_id)
```

Also assert rejection of a failed `job_result`, a mismatched strategy ID/version, and a missing `result.json`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
python3 -m unittest tests.workflows_tests.test_daily_steady_uptrend_mvp_email -v
```

Expected: import failure because `daily_steady_uptrend_mvp_email.py` does not exist.

- [ ] **Step 3: Implement the report contract**

Create frozen dataclasses:

```python
@dataclass(frozen=True, slots=True)
class EmailReportBundle:
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
    subject: str
    plain_text: str
    html: str
```

`load_email_report` must resolve paths through the latest and job artifacts, require `status == "success"`, require the approved strategy identity, and require matching `trade_date` and `run_id` in the scan payload.

- [ ] **Step 4: Write failing HTML tests**

Cover one grouped candidate with HTML-sensitive text and a zero-candidate report. Assert escaped output, stage rows, code/name/concepts/deviation, and zero-candidate blocker counts.

- [ ] **Step 5: Implement minimal HTML and plain-text rendering**

Render semantic tables with inline CSS suitable for email clients. Use `html.escape` on every artifact string. Format MA20 deviation as one decimal percent and preserve the diagnostic-only wording.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run the focused unittest command and expect all Task 1 tests to pass.

---

### Task 2: SMTP Delivery, Secret Boundary, and Deduplication

**Files:**
- Modify: `workflows/jobs/daily_steady_uptrend_mvp_email.py`
- Modify: `tests/workflows_tests/test_daily_steady_uptrend_mvp_email.py`

**Interfaces:**
- Consumes: `EmailSchedule`, `SmtpSecret`, and `RenderedEmail` from Task 1.
- Produces: `execute_email_job(schedule, smtp_sender=...) -> tuple[int, dict[str, object]]` and CLI `main()`.

- [ ] **Step 1: Write failing schedule and secret tests**

Test required schedule keys, exact `enabled/status/job` values, non-empty recipients, positive SMTP port and retry count, missing secret fields, mode other than `0600`, and a valid remote-style secret fixture.

- [ ] **Step 2: Verify RED**

Run the focused test module and confirm missing `EmailSchedule`/`SmtpSecret` failures.

- [ ] **Step 3: Implement config models and permission checks**

Add:

```python
@dataclass(frozen=True, slots=True)
class EmailSchedule:
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

@dataclass(frozen=True, slots=True)
class SmtpSecret:
    username: str
    authorization_code: str
```

Require `stat.S_IMODE(path.stat().st_mode) == 0o600` before reading the secret.

- [ ] **Step 4: Write failing SMTP and deduplication tests**

Use an injected sender callable. Assert one call for a new report, no call for an existing successful ledger, pending ledger creation before send, success ledger after send, and a sanitized failed result after exhausted retries.

- [ ] **Step 5: Implement lock, ledger, retries, and SMTP SSL**

Build `EmailMessage` with plain and HTML alternatives. Use `smtplib.SMTP_SSL(host, port, context=ssl.create_default_context())`, `login`, and `send_message`. Never include the authorization code in returned errors. Atomic JSON writes must use a sibling temporary file followed by `Path.replace`.

- [ ] **Step 6: Add and test CLI behavior**

Support:

```text
python3 workflows/jobs/daily_steady_uptrend_mvp_email.py \
  --schedule-config-path configs/schedules/daily_steady_uptrend_mvp_email.json
```

The CLI prints one structured JSON result and exits `0` for sent or already-sent outcomes, `1` for failures.

- [ ] **Step 7: Run focused and full tests**

Run:

```bash
python3 -m unittest tests.workflows_tests.test_daily_steady_uptrend_mvp_email -v
python3 -m unittest discover tests
```

Expected: all tests pass with no credential-shaped fixture values.

---

### Task 3: Versioned Configuration, Operations, Deployment, and Live Email

**Files:**
- Create: `configs/schedules/daily_steady_uptrend_mvp_email.example.json`
- Create: `ops/crontab/daily_steady_uptrend_mvp_email.crontab.example`
- Modify: `ops/runbooks/daily_steady_uptrend_mvp_tracking.md`
- Remote-only create: `/home/ubuntu/token_parse_sys_mvp/configs/schedules/daily_steady_uptrend_mvp_email.json`
- Remote-only create: `/home/ubuntu/token_parse_sys/ops/env/steady_uptrend_email.json`

**Interfaces:**
- Consumes: the CLI from Task 2 and current tracking report paths.
- Produces: one documented and active `00:50` notification cron plus a verified delivery ledger.

- [ ] **Step 1: Add versioned example configuration and cron**

The example config must point to placeholder deployment paths and contain no authorization code. The cron template must run at `50 0 * * 2-6` and append only non-sensitive output to `email_cron.log`.

- [ ] **Step 2: Update the runbook**

Document manual execution, artifact sources, zero-candidate semantics, ledger states, retry behavior, credential rotation, exact file mode, and failure inspection.

- [ ] **Step 3: Validate repository artifacts**

Run:

```bash
git diff --check
python3 -m json.tool configs/schedules/daily_steady_uptrend_mvp_email.example.json
python3 -m unittest discover tests
```

- [ ] **Step 4: Commit and push implementation**

Stage only the intended email job, tests, config, cron, runbook, and plan. Commit with `feat: email steady uptrend tracking results`, then push `codex/layered-recall-signal-optimization`.

- [ ] **Step 5: Deploy exact commit and install private config**

Update `/home/ubuntu/token_parse_sys_mvp` to the pushed commit. Create the actual schedule config and the remote-only SMTP secret file, set `chmod 600`, and verify only key names and mode without printing values.

- [ ] **Step 6: Send one live HTML verification email**

Run the notification job against the latest authoritative report. Confirm exit code `0`, a `sent` result, matching `trade_date/run_id`, and a success ledger with no secret value.

- [ ] **Step 7: Install and verify cron**

Back up the existing crontab, add exactly one active email line at `00:50` Tuesday-Saturday, preserve the existing `00:30` strategy line, and verify no duplicate email cron entries.

- [ ] **Step 8: Final verification**

Confirm deployed Git HEAD, full tests, private file mode, live delivery ledger, active cron count, and unchanged selection artifact checksums for the report used in the email test.

