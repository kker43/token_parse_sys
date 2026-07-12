# Layered Recall and Signal Threshold Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a research-only strategy version that recalls five structural trend subpools before applying waiting, risk, volume confirmation, ranking, and final signal filters.

**Architecture:** The external `token_fetch` producer publishes turnover-normalized activity and corporate-action context. Stock Lobster consumes those facts through L0/L1 inputs, produces deterministic recall and signal-state decisions, and feeds only signal-eligible recalled candidates into v4 ranking. Existing v1/v2/v3/v3.1 semantics and artifacts remain unchanged.

**Tech Stack:** Python 3.12 dataclasses and `unittest`, MySQL 8 views/tables, TSV/JSON artifacts, existing Stock Lobster research scanners and v3 ranking helpers.

## Global Constraints

- New strategy status remains `research_only`.
- Existing `candidate_v1`, `candidate_v2`, `candidate_v3`, and `candidate_v3_1` behavior is not changed in place.
- Recall runs only after minimum data quality and basic liquidity.
- `volume_ratio_5d_20d` is never a global recall hard gate.
- Missing volume confirmation permits recall but prevents promotion to final signal.
- Stock Lobster consumes published facts and does not query or produce authoritative fact tables outside L0.
- H5 is the primary evaluation horizon; H10 is secondary.
- Sample acceptance target: recall at least 17/23 positives and emit 0/4 hard negatives as final signals.

---

### Task 1: Publish Turnover-Normalized Activity and Corporate-Action Context

**Files:**
- Modify remotely: `/home/ubuntu/token_fetch/cron_script/daily_short_term_anomaly_task.py`
- Modify remotely: `/home/ubuntu/token_fetch/config/indicator_registry.yaml`
- Create remotely: `/home/ubuntu/token_fetch/sql/migrations/004_publish_turnover_and_adj_context.sql`
- Create remotely: `/home/ubuntu/token_fetch/tests/test_short_term_anomaly_activity.py`

**Interfaces:**
- Consumes: `token_daily_details.vol`, `token_daily_basic.turnover_rate`, `stock_adj_factor_daily.adj_factor`.
- Produces: published indicators `turnover_ratio_5d_20d`, `max_volume_ratio_5d_20d`, and `adj_factor_changed_20d` under `legacy_v1/default`.

- [ ] **Step 1: Write failing calculation tests**

```python
def test_activity_ratios_use_same_asof_window():
    frame = build_frame(
        volumes=[100.0] * 15 + [200.0] * 5,
        turnover_rates=[1.0] * 15 + [2.0] * 5,
        adj_factors=[1.0] * 20,
    )
    result = calculate_anomaly_indicators(frame)
    assert result["volume_ratio_5d_20d"] == 1.6
    assert result["turnover_ratio_5d_20d"] == 1.6
    assert result["adj_factor_changed_20d"] is False


def test_adj_factor_change_is_published_without_rewriting_volume():
    frame = build_frame(
        volumes=[100.0] * 15 + [140.0] * 5,
        turnover_rates=[1.0] * 20,
        adj_factors=[1.0] * 15 + [1.4] * 5,
    )
    result = calculate_anomaly_indicators(frame)
    assert result["volume_ratio_5d_20d"] > 1.0
    assert result["turnover_ratio_5d_20d"] == 1.0
    assert result["adj_factor_changed_20d"] is True
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
cd /home/ubuntu/token_fetch
python3 -m unittest tests.test_short_term_anomaly_activity
```

Expected: failures for missing `turnover_ratio_5d_20d` and `adj_factor_changed_20d`.

- [ ] **Step 3: Extend the source query and calculation result**

Load the aligned facts with one query:

```sql
SELECT
  d.ts_code,
  d.trade_date,
  d.close,
  d.vol,
  b.turnover_rate,
  a.adj_factor
FROM token_daily_details d
LEFT JOIN token_daily_basic b
  ON b.ts_code = d.ts_code AND b.trade_date = d.trade_date
LEFT JOIN stock_adj_factor_daily a
  ON a.ts_code = d.ts_code AND a.trade_date = d.trade_date
WHERE d.ts_code IN ({code_list}) {date_filter}
ORDER BY d.ts_code, d.trade_date
```

Add the deterministic calculation:

```python
turnover_5d = stock_df["turnover_rate"].values[-5:]
turnover_20d = stock_df["turnover_rate"].values[-20:]
avg_turnover_5d = np.mean(turnover_5d)
avg_turnover_20d = np.mean(turnover_20d)
turnover_ratio = (
    round(avg_turnover_5d / avg_turnover_20d, 4)
    if avg_turnover_20d != 0
    else None
)
adj_values = stock_df["adj_factor"].values[-20:]
adj_factor_changed = bool(
    len(adj_values) == 20
    and not pd.isna(adj_values).any()
    and len(set(float(value) for value in adj_values)) > 1
)
```

- [ ] **Step 4: Add columns, registry entries, and published view branches**

Migration columns:

```sql
ALTER TABLE short_term_anomaly_daily
  ADD COLUMN turnover_ratio_5d_20d DECIMAL(10,4) NULL,
  ADD COLUMN adj_factor_changed_20d TINYINT(1) NOT NULL DEFAULT 0;
```

Publish both fields through `pub_stock_daily_indicator` with exact indicator name/version/hash keys. Preserve every existing UNION branch.

- [ ] **Step 5: Run tests and validate production data**

```bash
python3 -m unittest tests.test_short_term_anomaly_activity tests.test_market_units
python3 cron_script/daily_short_term_anomaly_task.py --date 2026-07-10 --force
mysql -u root tokens -N -e "
SELECT indicator_name, COUNT(*), SUM(indicator_value IS NOT NULL)
FROM pub_stock_daily_indicator
WHERE trade_date='20260710'
  AND indicator_name IN ('volume_ratio_5d_20d','max_volume_ratio_5d_20d','turnover_ratio_5d_20d','adj_factor_changed_20d')
GROUP BY indicator_name;"
```

Expected: each indicator has at least 5,000 rows; strong-rui sample date reports an adjustment change and turnover ratio near 1.20.

- [ ] **Step 6: Commit and push the producer branch**

```bash
git add cron_script/daily_short_term_anomaly_task.py config/indicator_registry.yaml sql/migrations/004_publish_turnover_and_adj_context.sql tests/test_short_term_anomaly_activity.py
git commit -m "feat: publish turnover normalized activity context"
git push origin dev/basic_fetch_20260704
```

### Task 2: Extend L0/L1 Research Inputs Without Breaking Existing TSVs

**Files:**
- Modify: `stock_lobster/research/trend_breakout_scan.py`
- Modify: `workflows/jobs/daily_strategy_signal_production.py`
- Modify: `workflows/jobs/research_stock_context_batch_export.py`
- Test: `tests/research_tests/test_trend_breakout_scan.py`
- Test: `tests/workflows_tests/test_daily_strategy_signal_production.py`
- Test: `tests/workflows_tests/test_research_stock_context_batch_export.py`

**Interfaces:**
- Produces `KlineBar.volume: float | None`.
- Produces `StockSignalContext.max_volume_ratio_5d_20d`, `turnover_ratio_5d_20d`, and `adj_factor_changed_20d`.
- Existing seven-column K-line TSV and sixteen-column context TSV remain readable.

- [ ] **Step 1: Write compatibility and new-field tests**

```python
def test_kline_reader_accepts_optional_volume_column():
    path.write_text("000001.SZ\t20260710\t10\t11\t9\t10.5\t200000\t3000\n")
    bar = read_kline_tsv(path)[0]
    assert bar.amount == 200000
    assert bar.volume == 3000


def test_old_kline_without_volume_stays_readable():
    path.write_text("000001.SZ\t20260710\t10\t11\t9\t10.5\t200000\n")
    assert read_kline_tsv(path)[0].volume is None


def test_context_reads_activity_confirmation_fields():
    context = read_stock_signal_context_tsv(path)[0]
    assert context.max_volume_ratio_5d_20d == 2.13
    assert context.turnover_ratio_5d_20d == 1.29
    assert context.adj_factor_changed_20d is False
```

- [ ] **Step 2: Verify RED remotely**

```bash
python3 -m unittest \
  tests.research_tests.test_trend_breakout_scan \
  tests.workflows_tests.test_daily_strategy_signal_production \
  tests.workflows_tests.test_research_stock_context_batch_export
```

- [ ] **Step 3: Add optional dataclass fields and parsers**

```python
@dataclass(frozen=True, slots=True)
class KlineBar:
    asset_id: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    amount: float
    volume: float | None = None


@dataclass(frozen=True, slots=True)
class StockSignalContext:
    # existing fields remain in their current order
    volume_ratio_5d_20d: float | None = None
    max_volume_ratio_5d_20d: float | None = None
    turnover_ratio_5d_20d: float | None = None
    adj_factor_changed_20d: bool = False
```

- [ ] **Step 4: Extend exports through published indicators only**

Add grouped CTE columns for the three new indicator names and append them to TSV headers. Add `d.vol AS volume` as the final K-line export column. Do not query `short_term_anomaly_daily` directly.

- [ ] **Step 5: Run focused tests and commit**

```bash
python3 -m unittest \
  tests.research_tests.test_trend_breakout_scan \
  tests.workflows_tests.test_daily_strategy_signal_production \
  tests.workflows_tests.test_research_stock_context_batch_export
git add stock_lobster/research/trend_breakout_scan.py workflows/jobs tests
git commit -m "feat: consume layered volume confirmation context"
```

### Task 3: Build Five-Subpool Recall Before Strategy Filters

**Files:**
- Modify: `stock_lobster/research/trend_recall_subpools.py`
- Create: `stock_lobster/research/layered_recall_signal.py`
- Modify: `stock_lobster/research/__init__.py`
- Test: `tests/research_tests/test_trend_recall_subpools.py`
- Create: `tests/research_tests/test_layered_recall_signal.py`

**Interfaces:**
- Produces `TrendRecallSubpoolPolicy`.
- Produces `LayeredRecallDecision(metric, matched_subpools, recall_candidate)`.
- `classify_recall_subpools(metric, policy: TrendRecallSubpoolPolicy | None = None)` no longer applies signal-stage shape exclusions.

- [ ] **Step 1: Write tests for stage ordering and sensitivity candidates**

```python
def test_low_volume_pullback_can_enter_recall():
    metric = metric_fixture(
        market_cap_liquidity_pass=True,
        volume_ratio_5d_20d=0.84,
        close_to_high_60d_pct=0.0,
        ma30_hold_ratio_30d=1.0,
        ma30_hold_ratio_60d=0.78,
    )
    decision = build_layered_recall_decision(metric)
    assert decision.recall_candidate is True
    assert "pullback_reacceleration" in decision.matched_subpools


def test_early_reversal_candidate_uses_five_percent_return_floor():
    metric = metric_fixture(
        market_cap_liquidity_pass=True,
        close_new_high_60d_flag=False,
        return_20d=0.06,
        ma20_slope_20d=0.01,
        ma30_hold_ratio_30d=0.60,
    )
    assert classify_recall_subpools(metric)["early_reversal"].matched is True
```

- [ ] **Step 2: Verify RED**

```bash
python3 -m unittest tests.research_tests.test_trend_recall_subpools tests.research_tests.test_layered_recall_signal
```

- [ ] **Step 3: Add explicit policy and decision types**

```python
@dataclass(frozen=True, slots=True)
class TrendRecallSubpoolPolicy:
    pullback_min_ma30_hold_ratio_30d: float = 0.75
    pullback_min_ma30_hold_ratio_60d: float = 0.55
    early_reversal_min_return_20d: float = 0.05
    early_reversal_max_return_20d: float = 0.25
    early_reversal_min_ma30_hold_ratio_30d: float = 0.55


@dataclass(frozen=True, slots=True)
class LayeredRecallDecision:
    metric: TrendBreakoutMetrics
    matched_subpools: tuple[str, ...]
    recall_candidate: bool
```

Remove `_severe_shape_reasons()` from subpool matching. The function remains available to the later signal-state task until all callers migrate.

- [ ] **Step 4: Run tests and commit**

```bash
python3 -m unittest tests.research_tests.test_trend_recall_subpools tests.research_tests.test_layered_recall_signal
git add stock_lobster/research tests/research_tests
git commit -m "feat: recall five trend subpools before signal filters"
```

### Task 4: Add Waiting, Hard-Risk, and Price-Volume Confirmation States

**Files:**
- Modify: `stock_lobster/research/layered_recall_signal.py`
- Modify: `stock_lobster/research/trend_breakout_scan.py`
- Test: `tests/research_tests/test_layered_recall_signal.py`
- Test: `tests/research_tests/test_trend_breakout_scan.py`

**Interfaces:**
- Produces `SignalStateAssessment` with `waiting_reasons`, `hard_risk_reasons`, `confirmation_reasons`, and `signal_eligible`.
- Adds metric fields `post_impulse_followthrough_return`, `volume_decay_after_impulse`, `high_volume_bearish_close`, and `price_volume_efficiency_5d`.

- [ ] **Step 1: Write sample-shaped failing tests**

```python
def test_leading_share_is_recalled_but_waits_for_followthrough():
    metric = metric_fixture(
        post_impulse_followthrough_return=-0.0037,
        volume_decay_after_impulse=0.58,
    )
    state = assess_signal_state(recall_fixture(metric))
    assert state.signal_eligible is False
    assert "post_impulse_no_followthrough" in state.waiting_reasons


def test_valid_high_volume_breakout_is_not_rejected():
    metric = metric_fixture(
        volume_ratio_5d_20d=1.51,
        post_impulse_followthrough_return=0.095,
        high_volume_bearish_close=False,
    )
    assert assess_signal_state(recall_fixture(metric)).hard_risk_reasons == ()


def test_missing_volume_confirmation_keeps_recall_but_blocks_signal():
    state = assess_signal_state(recall_fixture(metric_fixture(volume_ratio_5d_20d=None)))
    assert state.recall_candidate is True
    assert state.signal_eligible is False
    assert "insufficient_volume_confirmation" in state.confirmation_reasons
```

- [ ] **Step 2: Verify RED**

```bash
python3 -m unittest tests.research_tests.test_layered_recall_signal tests.research_tests.test_trend_breakout_scan
```

- [ ] **Step 3: Implement deterministic price-volume diagnostics**

For the latest five bars, locate the largest positive close-to-close return. Compute return after that impulse and compare average volume after the impulse with the impulse volume. If daily volume is unavailable, return `None` and block only final confirmation.

```python
@dataclass(frozen=True, slots=True)
class SignalStateAssessment:
    recall_candidate: bool
    waiting_reasons: tuple[str, ...]
    hard_risk_reasons: tuple[str, ...]
    confirmation_reasons: tuple[str, ...]
    signal_eligible: bool
```

State rules:

```python
if metric.return_20d > 0.30 and metric.impulse_consolidation_days < 5:
    waiting.append("acceleration_needs_consolidation")
if metric.return_20d > 0.60 and metric.ma5_10_20_30_convergence_pct > 0.18:
    waiting.append("overextended_wide_ma_needs_rest")
if metric.large_bearish_body_ratio_20d > 0.30:
    confirmation.append("bearish_cluster_score_penalty")
if metric.post_impulse_followthrough_return is not None and metric.post_impulse_followthrough_return <= 0:
    waiting.append("post_impulse_no_followthrough")
```

Keep `noisy_ma30_breakdown_rebound` as hard risk. A high volume ratio alone never enters `hard_risk_reasons`.

- [ ] **Step 4: Run tests and commit**

```bash
python3 -m unittest tests.research_tests.test_layered_recall_signal tests.research_tests.test_trend_breakout_scan
git add stock_lobster/research tests/research_tests
git commit -m "feat: classify waiting and signal confirmation states"
```

### Task 5: Add Research-Only v4 Signal Selection and Stage Counts

**Files:**
- Create: `configs/strategies/steady_uptrend_layered_signal_candidate_v4.example.json`
- Create: `workflows/jobs/layered_recall_signal_research_scan.py`
- Modify: `stock_lobster/research/layered_recall_signal.py`
- Create: `tests/workflows_tests/test_layered_recall_signal_research_scan.py`
- Test: `tests/research_tests/test_layered_recall_signal.py`

**Interfaces:**
- Produces JSON keys `stage_counts`, `recall_candidates`, `waiting_candidates`, `hard_risk_rejected_candidates`, `signal_eligible_candidates`, and `final_signals`.
- Consumes only `LayeredRecallDecision` and `SignalStateAssessment` before ranking.

- [ ] **Step 1: Write workflow contract tests**

```python
def test_scan_outputs_every_stage_count():
    payload = run_scan(fixture_inputs())
    assert payload["stage_counts"] == {
        "minimum_quality_pool": 4,
        "basic_liquidity_pool": 4,
        "recall_union": 3,
        "waiting_pool": 1,
        "hard_risk_rejected": 1,
        "signal_eligible": 1,
        "ranked_topn": 1,
        "final_signal": 1,
    }


def test_topn_post_rank_rejection_does_not_refill():
    payload = run_scan(top5_with_second_candidate_rejected())
    assert len(payload["final_signals"]) == 4
```

- [ ] **Step 2: Verify RED**

```bash
python3 -m unittest tests.workflows_tests.test_layered_recall_signal_research_scan tests.research_tests.test_layered_recall_signal
```

- [ ] **Step 3: Create candidate v4 configuration**

The config must include:

```json
{
  "strategy_id": "strategy.steady_uptrend_layered_signal",
  "version": "candidate_v4",
  "status": "research_only",
  "recall_policy": {
    "early_reversal_min_return_20d": 0.05,
    "pullback_min_ma30_hold_ratio_30d": 0.75,
    "pullback_min_ma30_hold_ratio_60d": 0.55
  },
  "signal_policy": {
    "volume_ratio_is_hard_gate": false,
    "long_base_volume_bonus_threshold": 1.1,
    "weak_market_breadth_ma20_threshold": 0.35,
    "weak_market_top_n": 2,
    "normal_market_top_n": 3
  }
}
```

- [ ] **Step 4: Implement ordered selection**

Rank only `signal_eligible` candidates. Apply TopN, then post-rank no-refill reasons. Reuse v3 score components only as diagnostics; do not make old `breakout_watch/pre_breakout_watch` the candidate source.

- [ ] **Step 5: Run tests and commit**

```bash
python3 -m unittest tests.workflows_tests.test_layered_recall_signal_research_scan tests.research_tests.test_layered_recall_signal
python3 -m json.tool configs/strategies/steady_uptrend_layered_signal_candidate_v4.example.json >/dev/null
git add configs/strategies stock_lobster/research workflows/jobs tests
git commit -m "feat: add layered recall signal candidate v4"
```

### Task 6: Rebuild Sample Evaluation and Threshold Sensitivity

**Files:**
- Modify: `workflows/jobs/sample_strategy_replay.py`
- Create generated: `docs/research_reports/20260712-layered-recall-signal-sample-evaluation.csv`
- Create generated: `docs/research_reports/20260712-layered-recall-signal-sample-evaluation.md`
- Test: `tests/workflows_tests/test_sample_strategy_replay.py`

**Interfaces:**
- Produces target-separated counts for positive, hard negative, low/excluded, and waiting samples at recall, waiting, signal-eligible, and final-signal stages.

- [ ] **Step 1: Write report contract tests**

```python
def test_sample_report_separates_recall_and_signal_results():
    row = evaluate_event(sample_event(), layered_result())
    assert row["candidate_v4.recall_candidate"] is True
    assert row["candidate_v4.signal_eligible"] is False
    assert row["candidate_v4.waiting_reasons"] == "post_impulse_no_followthrough"
```

- [ ] **Step 2: Verify RED and implement report fields**

```bash
python3 -m unittest tests.workflows_tests.test_sample_strategy_replay
```

Add sensitivity rows for:

- Early reversal return floor: 0.03, 0.05, 0.08.
- Pullback MA30 30d/60d: 0.75/0.55 and 0.55/0.55.
- Long-base volume score bonus: 1.0, 1.1, 1.2.
- Overextended wait threshold: `(return_20d, convergence)` at `(0.50,0.16)`, `(0.60,0.18)`, `(0.70,0.20)`.

- [ ] **Step 3: Re-export all 24 sample dates and run replay**

Use the remote Python 3.12 environment and fresh published context. Expected acceptance checks:

```text
positive recall >= 17/23
hard negative final signal = 0/4
low/excluded final signal = 0/2
杰华特/冰轮环境/天创时尚 20260707 final signal = false
领先股份 20260707 waiting reason includes post_impulse_no_followthrough
```

- [ ] **Step 4: Commit deterministic reports**

```bash
git add workflows/jobs/sample_strategy_replay.py tests/workflows_tests/test_sample_strategy_replay.py docs/research_reports/20260712-layered-recall-signal-sample-evaluation.*
git commit -m "docs: evaluate layered recall signal thresholds"
```

### Task 7: Full-Market Scan, Historical H5/H10 Validation, and Deployment

**Files:**
- Generate remotely: `runtime/strategy_effect_eval/20260710/layered_candidate_v4.json`
- Create: `docs/research_reports/20260712-layered-recall-signal-full-evaluation.md`

**Interfaces:**
- Compares candidate v4 with five-subpool equal weight, existing v3.1, and current final signals.

- [ ] **Step 1: Run complete tests and schema checks**

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
find configs -name '*.json' -print0 | xargs -0 -n1 python3 -m json.tool >/dev/null
git diff --check
```

- [ ] **Step 2: Run 20260710 full-market v4 scan**

```bash
python3 workflows/jobs/layered_recall_signal_research_scan.py \
  --kline-tsv-path runtime/strategy_signal_production/20260710/input/kline.tsv \
  --weekly-kline-tsv-path runtime/strategy_signal_production/20260710/input/weekly_kline.tsv \
  --stock-context-tsv-path runtime/strategy_signal_production/20260710/input/stock_context.tsv \
  --strategy-config-path configs/strategies/steady_uptrend_layered_signal_candidate_v4.example.json \
  --output-path runtime/strategy_effect_eval/20260710/layered_candidate_v4.json \
  --start-date 20260710
```

- [ ] **Step 3: Rebuild historical context and backtest**

Re-export every signal date with the new published fields. Run event backtests with T+1 open entry for H5 and H10. Report:

- sample size and signal-date count;
- average, median, win rate, worst return, and max drawdown;
- equal-weight recall-pool relative return;
- monthly and `breadth_ma20` stability buckets.

Do not reuse old amount-ratio artifacts as candidate v4 evidence.

- [ ] **Step 4: Write evaluation and keep lifecycle research-only**

The report must state whether sample gates passed and whether H5/H10 improved relative to both benchmarks. Do not promote to `test_tracking` without user approval.

- [ ] **Step 5: Deploy only changed files and verify no residual processes**

```bash
ps -eo pid,cmd | grep -E '(layered_recall_signal|research_stock_context_batch_export)' | grep -v grep
```

Expected: no matching process after jobs finish.

- [ ] **Step 6: Commit and push both repositories**

```bash
git add docs/research_reports/20260712-layered-recall-signal-full-evaluation.md
git commit -m "docs: validate layered recall signal candidate v4"
git push -u origin codex/layered-recall-signal-optimization
```

On the server, commit the exact deployed tracked files on its deployment branch and leave untracked runtime schedule files untouched.
