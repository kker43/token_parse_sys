# Steady Uptrend S1-S5 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a deterministic, replayable S1-S5 steady-uptrend MVP scanner with per-stage blockers and industry-grouped entry output.

**Architecture:** Add a focused research evaluator that consumes existing daily bars, weekly bars, and stock context without changing legacy strategy semantics. Expose the evaluator through a research-only workflow job and versioned candidate config; emit JSON as the source of truth plus a deterministic Markdown view.

**Tech Stack:** Python 3.12, standard-library dataclasses/JSON/argparse/unittest, existing `stock_lobster.research.trend_breakout_scan` data readers.

## Global Constraints

- Keep technical architecture L0-L6 unchanged; S1-S5 are business stages implemented through the research/strategy path.
- Stock Lobster consumes external facts and must not collect, repair, or author authoritative market data.
- Signal-date windows exclude the signal day unless the rule explicitly says current state.
- Daily prices and moving averages use one reproducible adjusted-price basis.
- Do not modify legacy candidate v2/v3/v3_1/v4 behavior.
- No cooldown, no no-refill, no TopN, and no MA20-deviation hard filter.

---

### Task 1: Policy, Metrics, and S1-S4 Evaluation

**Files:**
- Create: `stock_lobster/research/steady_uptrend_s1_s5_mvp.py`
- Create: `tests/research_tests/test_steady_uptrend_s1_s5_mvp.py`
- Modify: `stock_lobster/research/__init__.py`

**Interfaces:**
- Consumes: `KlineBar`, `StockSignalContext`, and weekly `KlineBar` sequences from `trend_breakout_scan.py`.
- Produces: `SteadyUptrendMvpPolicy`, `StageDecision`, `SteadyUptrendMvpCandidate`, and `evaluate_steady_uptrend_mvp(...)`.

- [x] **Step 1: Write failing S1 and S2 tests**

Add fixtures with at least 120 daily bars and 64 weekly bars. The daily minimum is required because every day in the latest 60-day MA60 hold window must have its own MA60 value. Assert S1 accepts exactly `total_mv >= 1_000_000` and `avg_amount_20d >= 200_000`, and S2 enforces the daily/weekly mature-trend conjunction including a 50% MA60 hold ratio.

- [x] **Step 2: Run the focused test and verify RED**

Run: `/opt/homebrew/bin/python3.12 -m unittest tests.research_tests.test_steady_uptrend_s1_s5_mvp -v`

Expected: import failure for `stock_lobster.research.steady_uptrend_s1_s5_mvp`.

- [x] **Step 3: Implement the policy and S1/S2 decisions**

Create frozen dataclasses for thresholds and stage output. Compute moving averages from bars as-of `signal_date`; return stable blocker keys such as `market_cap_below_minimum`, `avg_amount_20d_below_minimum`, `daily_mature_trend_failed`, and `weekly_mature_trend_failed`.

- [x] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2 and require all S1/S2 tests to pass.

- [x] **Step 5: Write failing S3 tests**

Cover S3-A at exactly -10% from the 60-day high, S3-B healthy pullback/recovery and effective MA60 breakdown, and S3-C steady alignment plus the `previous_5d <= -5% AND recent_5d >= 20%` wide-swing rejection.

- [x] **Step 6: Implement S3 branch metrics and OR recall**

Return every matched branch in deterministic order `("s3_a_high_position", "s3_b_pullback_recovery", "s3_c_steady_ma")`; block only when none match.

- [x] **Step 7: Write failing S4 tests**

Cover the three-way noisy-shadow composite, `red_k_ratio_60d < 0.45`, and at least three extreme bearish days in the previous ten complete trading days. Include boundary tests for 60%, 56%, 5 transitions, 45%, and 7%.

- [x] **Step 8: Implement S4 metrics and hard blockers**

Use the exact upper-shadow and total-shadow formulas from the approved spec, count MA alignment state changes, treat `close == open` as red K, and retain all matched S4 blocker keys.

- [x] **Step 9: Run research tests and commit**

Run: `/opt/homebrew/bin/python3.12 -m unittest tests.research_tests.test_steady_uptrend_s1_s5_mvp tests.research_tests.test_layered_recall_signal -v`

Commit only Task 1 files with message `feat: add steady uptrend S1-S4 evaluator`.

### Task 2: S5 Context, Deviation, and Deterministic Grouping

**Files:**
- Modify: `stock_lobster/research/steady_uptrend_s1_s5_mvp.py`
- Modify: `tests/research_tests/test_steady_uptrend_s1_s5_mvp.py`

**Interfaces:**
- Consumes: Task 1 `SteadyUptrendMvpCandidate` and `StockSignalContext`.
- Produces: `build_steady_uptrend_mvp_report(...)`, `ma20_deviation_level(...)`, and JSON-friendly grouped output.

- [x] **Step 1: Write failing S5 boundary tests**

Assert context passes for industry OR concept hit, fails when both are false, and maps exact deviations 20%, 30%, 40%, and 50% to the higher level without filtering.

- [x] **Step 2: Verify RED, implement S5, and verify GREEN**

Run the focused research test before and after implementation. S5 blocker key is `context_strength_unavailable`; a missing/zero MA20 is reported as data unavailability and cannot become final.

- [x] **Step 3: Write failing ordering and rendering tests**

Assert industry groups sort by strong-industry candidate count descending, then total count descending, then name; stocks sort by industry hit, deviation ascending, then asset ID. Concepts appear after deviation and never form separate groups.

- [x] **Step 4: Implement JSON and Markdown report builders**

Return `stage_counts`, `blocker_counts`, `candidates`, `industry_groups`, and `markdown`. Keep each stock in exactly one canonical industry group.

- [x] **Step 5: Run focused tests and commit**

Run: `/opt/homebrew/bin/python3.12 -m unittest tests.research_tests.test_steady_uptrend_s1_s5_mvp -v`

Commit Task 2 files with message `feat: add S5 entry grouping and alerts`.

### Task 3: Research CLI and Candidate Configuration

**Files:**
- Create: `workflows/jobs/steady_uptrend_s1_s5_mvp_scan.py`
- Create: `tests/workflows_tests/test_steady_uptrend_s1_s5_mvp_scan.py`
- Create: `configs/strategies/steady_uptrend_s1_s5_mvp_candidate_v1.example.json`

**Interfaces:**
- Consumes: existing TSV readers and Task 2 `build_steady_uptrend_mvp_report(...)`.
- Produces: CLI `main(argv) -> int`, JSON artifact at `--output-path`, and Markdown artifact at `--markdown-output-path` when supplied.

- [x] **Step 1: Write failing CLI contract tests**

Assert the parser requires daily bars, weekly bars, stock context, config, output, and signal date. Assert a small fixture run writes deterministic stage counts and Markdown.

- [x] **Step 2: Run workflow test and verify RED**

Run: `/opt/homebrew/bin/python3.12 -m unittest tests.workflows_tests.test_steady_uptrend_s1_s5_mvp_scan -v`

Expected: import failure for the new job.

- [x] **Step 3: Implement CLI and versioned config**

Read only supplied artifacts, parse approved policy keys, evaluate one signal date, and write with `workflows.jobs.support.write_json_payload`. The config includes `strategy_id="steady_uptrend_s1_s5_mvp_candidate_v1"`, `status="research_only"`, and every approved threshold. Promotion to `test_tracking` requires a separate StrategyDSL/L5/L6 implementation and lifecycle approval.

- [x] **Step 4: Run workflow and legacy regression tests**

Run: `/opt/homebrew/bin/python3.12 -m unittest tests.workflows_tests.test_steady_uptrend_s1_s5_mvp_scan tests.workflows_tests.test_layered_recall_signal_research_scan -v`

- [x] **Step 5: Commit**

Commit Task 3 files with message `feat: add steady uptrend S1-S5 research scan`.

### Task 4: Sample Replay, Full Verification, and Usage Documentation

**Files:**
- Create: `docs/research/steady_uptrend_s1_s5_mvp.md`
- Modify only if tests expose a defect: files created in Tasks 1-3.

**Interfaces:**
- Consumes: versioned config and CLI from Task 3.
- Produces: reproducible usage instructions and verification evidence for the agreed positive/negative samples when source fixtures are available.

- [x] **Step 1: Add exact run instructions and output contract**

Document business-stage to technical-layer mapping, required TSV columns, signal-date semantics, CLI command, blocker keys, and final industry-group format in Chinese.

- [x] **Step 2: Run focused sample replay**

Use available repository or externally supplied read-only facts to evaluate 铜冠铜箔 `20260609`, 强瑞技术 `20260608`, and the recorded 宏和科技 dates. Record observed stage/blocker results in a temporary artifact, not as authoritative facts in source code.

- [x] **Step 3: Run complete verification**

Run:

```bash
/opt/homebrew/bin/python3.12 -m unittest \
  tests.research_tests.test_steady_uptrend_s1_s5_mvp \
  tests.workflows_tests.test_steady_uptrend_s1_s5_mvp_scan \
  tests.research_tests.test_layered_recall_signal \
  tests.workflows_tests.test_layered_recall_signal_research_scan -v
git diff --check
```

Expected: all tests pass and `git diff --check` has no output.

- [x] **Step 4: Run boundary and config validation**

Run the repository's import-boundary and config/schema validation commands discovered from `sys_command.md`; report any suite that cannot run and why.

- [x] **Step 5: Commit final documentation/fixes**

Commit with message `docs: document steady uptrend S1-S5 MVP`.
