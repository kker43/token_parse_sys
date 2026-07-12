# Steady Uptrend MVP Routine Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one cron-safe workflow that resolves a ready trade date, exports deterministic inputs, runs the sole enabled steady-uptrend MVP strategy, and atomically publishes its report.

**Architecture:** Add a technical orchestration job that composes the existing read-only K-line/context exporters and MVP scanner without owning strategy thresholds. Read external quality status as a gate, keep full evidence under versioned run directories, and atomically publish a compact human-facing report directory only after success.

**Tech Stack:** Python 3.12, standard library `argparse/json/pathlib/fcntl`, PyMySQL through the existing external adapter, unittest, JSON schedules, cron.

## Global Constraints

- `token_parse_sys` remains a read-only consumer of external factual data.
- The strategy remains `test_tracking`; this task does not publish formal L5 signals.
- Exactly one registry entry may have `routine_selection_enabled=true`.
- S1-S5 policy values and ordering must not change.
- Reports publish under `/home/ubuntu/token_parse_sys/runtime/strategy_tracking/reports/YYYYMMDD/`.
- A failed run must not overwrite the last successful report or `latest.json`.
- Use `/opt/homebrew/bin/python3.12` for local verification.

---

### Task 1: Quality Gate and Trade-Date Resolution

**Files:**
- Create: `workflows/jobs/daily_steady_uptrend_mvp_tracking.py`
- Create: `tests/workflows_tests/test_daily_steady_uptrend_mvp_tracking.py`

**Interfaces:**
- Consumes: rows from external `pub_data_quality_status`.
- Produces: `ResolvedReadiness(trade_date: str, weekly_trade_date: str, statuses: tuple[dict[str, object], ...])` and `resolve_readiness(rows, requested_date=None)`.

- [ ] **Step 1: Write failing tests for exact and automatic date resolution**

Create fixtures for four daily products and one weekly product. Assert automatic resolution ignores a newer incomplete date, explicit resolution rejects missing products, duplicate product keys fail, and the latest weekly source date not after the signal date is selected.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
/opt/homebrew/bin/python3.12 -m unittest tests.workflows_tests.test_daily_steady_uptrend_mvp_tracking
```

Expected: import failure because `daily_steady_uptrend_mvp_tracking.py` does not exist.

- [ ] **Step 3: Implement the quality resolver and read-only query**

Define:

```python
@dataclass(frozen=True, slots=True)
class ResolvedReadiness:
    trade_date: str
    weekly_trade_date: str
    statuses: tuple[dict[str, object], ...]

def resolve_readiness(
    rows: Sequence[Mapping[str, object]],
    requested_date: str | None = None,
) -> ResolvedReadiness:
    """Return the newest complete daily readiness set plus its weekly gate."""
```

The signature above defines the public contract; implement its body in this step. Daily products are `pub_stock_daily_kline`, `pub_stock_daily_basic`, `pub_stock_daily_indicator`, and `pub_stock_asset_basic`. Group rows by `(data_product, data_date, market, asset_type)`, reject duplicate keys, retain only `CN_A/stock + ready/pass`, and choose the newest date containing all four products with `source_end_date == data_date` and a non-empty `data_version`. Select `pub_stock_weekly_kline` with the latest `source_end_date <= trade_date`. Return only the four selected daily rows and one selected weekly row in deterministic product order. Query rows with parameterized SQL through the existing external MySQL connection factory; do not write to the source database.

- [ ] **Step 4: Run tests and verify GREEN**

Run the Task 1 command and expect all resolver tests to pass.

---

### Task 2: Registry, Export, and Scan Orchestration

**Files:**
- Modify: `workflows/jobs/daily_steady_uptrend_mvp_tracking.py`
- Modify: `tests/workflows_tests/test_daily_steady_uptrend_mvp_tracking.py`
- Modify: `configs/schedules/daily_steady_uptrend_mvp_tracking.example.json`

**Interfaces:**
- Consumes: `ResolvedReadiness`, strategy registry, current strategy config, existing `export_kline_batch`, `export_stock_context_batch`, and MVP scanner.
- Produces: `run_tracking_pipeline(settings, dependencies) -> dict[str, object]` and a complete run directory.

- [ ] **Step 1: Write failing orchestration tests**

Use injected dependencies backed by in-memory fixture functions. Assert:

```text
quality resolution
-> kline export
-> context export
-> scanner
-> publication
```

Assert zero or multiple enabled registry entries fail before export. Assert the enabled entry must be `test_tracking`, its config ID/version/status must match, and its `selection_job` must be `workflows/jobs/steady_uptrend_s1_s5_mvp_scan.py`.

- [ ] **Step 2: Run tests and verify RED**

Expected: failure because schedule loading and `run_tracking_pipeline` are absent.

- [ ] **Step 3: Implement schedule and orchestration**

Add a frozen `TrackingSchedule` with paths for MySQL config, registry, strategy, run root, report root, job-result root, lock, and latest pointer; integer calendar lookbacks; and `qfq_asof` price basis. Use `datetime.strptime` and `timedelta` to compute export windows. Build paths as:

```text
<run_root>/runs/<trade_date>/<strategy_id>/<version>/input
<run_root>/runs/<trade_date>/<strategy_id>/<version>/result.json
<run_root>/runs/<trade_date>/<strategy_id>/<version>/report.md
```

Call the existing export APIs and scanner `main()` directly. Treat nonzero scanner exit as failure. Derive a deterministic run ID from strategy ID/version/date plus the K-line and context manifest hashes.

- [ ] **Step 4: Expand the schedule example**

Use these keys and deployment defaults:

```json
{
  "enabled": true,
  "status": "test_tracking",
  "mysql_config_path": "/home/ubuntu/token_parse_sys/ops/env/external_mysql.json",
  "strategy_registry_path": "/home/ubuntu/token_parse_sys_mvp/configs/strategies/strategy_registry.json",
  "strategy_config_path": "/home/ubuntu/token_parse_sys_mvp/configs/strategies/steady_uptrend_mvp.json",
  "run_root": "/home/ubuntu/token_parse_sys/runtime/strategy_tracking",
  "report_root": "/home/ubuntu/token_parse_sys/runtime/strategy_tracking/reports",
  "job_result_root": "/home/ubuntu/token_parse_sys/runtime/strategy_tracking/job_results",
  "latest_result_path": "/home/ubuntu/token_parse_sys/runtime/strategy_tracking/reports/latest.json",
  "lock_path": "/home/ubuntu/token_parse_sys/runtime/strategy_tracking/daily_tracking.lock",
  "daily_lookback_calendar_days": 440,
  "weekly_lookback_calendar_days": 950,
  "price_basis": "qfq_asof"
}
```

- [ ] **Step 5: Run targeted tests and verify GREEN**

Run the Task 1 test command and expect all orchestration tests to pass.

---

### Task 3: Atomic Report Publication, Locking, and Failure Artifacts

**Files:**
- Modify: `workflows/jobs/daily_steady_uptrend_mvp_tracking.py`
- Modify: `tests/workflows_tests/test_daily_steady_uptrend_mvp_tracking.py`

**Interfaces:**
- Consumes: successful scan result and report files.
- Produces: report directory with `report.md`, `candidates.json`, `job_result.json`; global dated job result; successful `latest.json`.

- [ ] **Step 1: Write failing publication and failure tests**

Assert successful publication writes all three files using temporary sibling files followed by `Path.replace()`. Assert an injected scanner failure writes `<job_result_root>/<date>.json`, returns nonzero from `main`, leaves an existing report and `latest.json` byte-for-byte unchanged, and records `failed_stage`, `error_type`, and `error_message`. Assert a held `fcntl.flock(LOCK_EX | LOCK_NB)` prevents a second run.

- [ ] **Step 2: Run tests and verify RED**

Expected: failure because atomic publication, failure persistence, and locking are absent.

- [ ] **Step 3: Implement publication and failure semantics**

Publish `candidates.json` as the complete deterministic scan payload, not a lossy candidate-only list. Write `job_result.json` with strategy identity, status, trade date, stage counts, candidate count, input/output paths, and dependency versions. Update `latest.json` only after all dated report files exist. Wrap `main()` in the lock and exception boundary; record the current stage before each operation.

- [ ] **Step 4: Run targeted tests and verify GREEN**

Run the Task 1 test command and expect all publication, locking, and error tests to pass.

---

### Task 4: Documentation, Regression, Commit, and Deployment

**Files:**
- Modify: `ops/runbooks/daily_steady_uptrend_mvp_tracking.md`
- Modify: `ops/runbooks/daily_strategy_signal_production.md`
- Modify: `tests/research_tests/test_strategy_registry.py`

**Interfaces:**
- Produces: one documented cron entry, verified deployment, and one active business selection task.

- [ ] **Step 1: Add config and runbook contract tests**

Assert the enabled schedule points at `daily_steady_uptrend_mvp_tracking.py`, declares the stable report root, and the legacy pre-breakout binding remains disabled while its workflow capability remains supported.

- [ ] **Step 2: Run the new test and verify RED**

Run:

```bash
/opt/homebrew/bin/python3.12 -m unittest tests.research_tests.test_strategy_registry
```

Expected: failure until schedule and runbook contracts are aligned.

- [ ] **Step 3: Update runbooks**

Document manual execution, automatic date resolution, output directories, failure inspection, lock handling, deterministic reruns, and the exact cron command from the design spec. Clarify that only the business binding changed; technical workflow and replay capabilities remain supported.

- [ ] **Step 4: Run complete local verification**

Run:

```bash
/opt/homebrew/bin/python3.12 -m unittest discover -s tests -p 'test_*.py'
find configs -type f -name '*.json' -exec jq empty {} +
git diff --check
```

Expected: all tests pass; JSON and whitespace checks are clean.

- [ ] **Step 5: Commit and push**

Commit code, tests, config, and runbooks with:

```bash
git commit -m "feat: automate MVP routine tracking pipeline"
git push origin codex/layered-recall-signal-optimization
```

- [ ] **Step 6: Deploy and verify**

Update `/home/ubuntu/token_parse_sys_mvp` to the exact commit, create actual configs without credentials in Git, run explicit date `20260710`, verify `5521 -> 1482 -> 166 -> 106 -> 90 -> 25`, then run without `--date` and confirm the latest fully ready date. Back up crontab, install exactly one active MVP tracking line, and verify the old pre-breakout line remains commented.
