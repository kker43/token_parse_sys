# 5/20 日成交量比统一门槛实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将所有活动策略的放量硬门槛统一为上游发布的 `volume_ratio_5d_20d >= 1.2`，并完成远程发布、样本复盘和全市场验证。

**Architecture:** `token_fetch` 只负责把已计算的 `short_term_anomaly_daily.volume_ratio_5d_20d` 暴露到发布视图；Stock Lobster 通过现有股票上下文 TSV 消费该字段。扫描器把该值带入 `TrendBreakoutMetrics`，突破、预突破和 v3/v3.1 只使用新字段做量能硬门槛，成交额量比继续作为诊断与评分。

**Tech Stack:** MySQL 8 view migration、Python 3.12 dataclass/csv、JSON 策略配置、`unittest`、远程 SSH 运行。

## Global Constraints

- 统一门槛为 `min_volume_ratio_5d_20d = 1.2`。
- 缺失 `volume_ratio_5d_20d` 必须拒绝，不得填充为 1。
- `amount_ratio_20d`、`amount_ratio_prev_20d` 只保留为诊断和评分字段。
- Stock Lobster 不得直接查询 `short_term_anomaly_daily`，只能消费发布契约。
- 不调整 MA30、换手率、题材上下文和五类子池结构阈值。

---

### Task 1: 发布上游 5/20 日成交量比

**Files:**
- Create remotely: `/home/ubuntu/token_fetch/sql/migrations/003_publish_registered_daily_indicators.sql`
- Verify: `/home/ubuntu/token_fetch/sql/views/pub_stock_daily_indicator_draft.sql`

**Interfaces:**
- Consumes: `short_term_anomaly_daily.volume_ratio_5d_20d`。
- Produces: `pub_stock_daily_indicator(asset_id, trade_date, indicator_name, indicator_version, params_hash, indicator_value)`。

- [ ] **Step 1: 保留失败证据**

Run:

```sql
SELECT COUNT(*) FROM pub_stock_daily_indicator
WHERE trade_date='20260710' AND indicator_name='volume_ratio_5d_20d';
```

Expected before migration: `0`。

- [ ] **Step 2: 创建版本化视图迁移**

迁移内容以 `pub_stock_daily_indicator_draft` 的列契约和全部 `UNION ALL` 分支为源，将目标视图名改为 `pub_stock_daily_indicator`。不得删除旧的 `ma20`、`amount_ratio_20d` 等发布指标。

- [ ] **Step 3: 应用迁移并验证**

Run:

```bash
mysql -u root tokens < sql/migrations/003_publish_registered_daily_indicators.sql
mysql -u root tokens -N -e "SELECT COUNT(*) FROM pub_stock_daily_indicator WHERE trade_date='20260710' AND indicator_name='volume_ratio_5d_20d' AND indicator_version='legacy_v1' AND params_hash='default'"
```

Expected: count `>= 5000`，且 `(asset_id, trade_date, indicator_name, indicator_version, params_hash)` 无重复。

- [ ] **Step 4: 提交并推送 token_fetch**

```bash
git add sql/migrations/003_publish_registered_daily_indicators.sql
git commit -m "feat: publish registered daily indicators"
git push origin dev/basic_fetch_20260704
```

### Task 2: 将发布指标接入股票上下文

**Files:**
- Modify: `stock_lobster/research/trend_breakout_scan.py`
- Modify: `workflows/jobs/daily_strategy_signal_production.py`
- Modify: `workflows/jobs/research_stock_context_batch_export.py`
- Test: `tests/research_tests/test_trend_breakout_scan.py`
- Test: `tests/workflows_tests/test_daily_strategy_signal_production.py`
- Test: `tests/workflows_tests/test_research_stock_context_batch_export.py`

**Interfaces:**
- Produces: `StockSignalContext.volume_ratio_5d_20d: float | None`。
- SQL joins `pub_stock_daily_indicator` with exact name/version/hash/date predicates.

- [ ] **Step 1: 写失败测试**

覆盖 TSV 解析新字段、SQL 包含精确指标过滤、导出 header 包含 `volume_ratio_5d_20d`。

- [ ] **Step 2: 在远程 Python 3.12 环境确认测试失败**

Run:

```bash
python3 -m unittest tests.research_tests.test_trend_breakout_scan tests.workflows_tests.test_daily_strategy_signal_production tests.workflows_tests.test_research_stock_context_batch_export
```

Expected: 新字段断言失败。

- [ ] **Step 3: 最小实现字段和 SQL 数据流**

`StockSignalContext` 新增可空字段；上下文 SQL 使用：

```sql
LEFT JOIN pub_stock_daily_indicator vr
  ON vr.asset_id = db.ts_code
 AND vr.trade_date = db.trade_date
 AND vr.indicator_name = 'volume_ratio_5d_20d'
 AND vr.indicator_version = 'legacy_v1'
 AND vr.params_hash = 'default'
```

并选择 `vr.indicator_value AS volume_ratio_5d_20d`。

- [ ] **Step 4: 运行测试至通过并提交**

```bash
python3 -m unittest tests.research_tests.test_trend_breakout_scan tests.workflows_tests.test_daily_strategy_signal_production tests.workflows_tests.test_research_stock_context_batch_export
git add stock_lobster/research/trend_breakout_scan.py workflows/jobs/daily_strategy_signal_production.py workflows/jobs/research_stock_context_batch_export.py tests
git commit -m "feat: consume 5d 20d volume ratio"
```

### Task 3: 替换基础扫描器量能硬门槛

**Files:**
- Modify: `stock_lobster/research/trend_breakout_scan.py`
- Modify: `workflows/jobs/sample_strategy_replay.py`
- Modify: `workflows/jobs/steady_uptrend_breakout_research_scan.py`
- Test: `tests/research_tests/test_trend_breakout_scan.py`
- Test: `tests/workflows_tests/test_sample_strategy_replay.py`

**Interfaces:**
- Produces: `TrendBreakoutMetrics.volume_ratio_5d_20d: float | None`。
- Produces: `TrendBreakoutScanPolicy.min_volume_ratio_5d_20d: float = 1.2`。

- [ ] **Step 1: 写门槛边界失败测试**

分别构造 `None`、`1.19`、`1.20`，断言缺失和 `1.19` 不触发，`1.20` 触发；阻断原因分别为 `volume_ratio_5d_20d_missing` 和 `volume_ratio_5d_20d_below_1.2`。

- [ ] **Step 2: 运行测试确认 RED**

```bash
python3 -m unittest tests.research_tests.test_trend_breakout_scan tests.workflows_tests.test_sample_strategy_replay
```

- [ ] **Step 3: 实现基础门槛替换**

`breakout_watch` 和 `pre_breakout_watch` 均使用：

```python
volume_ratio_pass = (
    metric_value is not None
    and metric_value >= policy.min_volume_ratio_5d_20d
)
```

删除策略硬过滤对 `min_amount_ratio_20d`、`min_pre_breakout_amount_ratio_20d` 的引用；报告同时输出三种量比。

- [ ] **Step 4: 测试通过并提交**

```bash
python3 -m unittest tests.research_tests.test_trend_breakout_scan tests.workflows_tests.test_sample_strategy_replay
git commit -am "feat: gate breakouts on 5d 20d volume ratio"
```

### Task 4: 替换 v3/v3.1 与活动配置

**Files:**
- Modify: `stock_lobster/research/steady_uptrend_v3.py`
- Modify: `configs/strategies/steady_uptrend_breakout_watch.example.json`
- Modify: `configs/strategies/steady_uptrend_breakout_watch_candidate_v2.example.json`
- Modify: `configs/strategies/steady_uptrend_pre_breakout_watch.example.json`
- Modify: `configs/strategies/steady_uptrend_pre_breakout_watch_candidate_v3.example.json`
- Modify: `configs/strategies/steady_uptrend_pre_breakout_watch_candidate_v3_1.example.json`
- Test: `tests/research_tests/test_steady_uptrend_v3_selection.py`
- Test: `tests/workflows_tests/test_steady_uptrend_v3_research_scan.py`

**Interfaces:**
- `SteadyUptrendV3Policy.min_volume_ratio_5d_20d: float | None`。
- v3 rejection reason: `volume_ratio_5d_20d_below_v3_threshold`。

- [ ] **Step 1: 写 v3 失败测试并确认 RED**

测试 `1.19` 被拒绝、`1.20` 通过、缺失被拒绝；配置序列化只出现新字段。

- [ ] **Step 2: 实现 v3 字段和配置迁移**

所有活动配置写入：

```json
"min_volume_ratio_5d_20d": 1.2
```

删除承担硬门槛的旧 `min_amount_ratio_20d` 和 `min_pre_breakout_amount_ratio_20d`。

- [ ] **Step 3: 运行测试和配置扫描**

```bash
python3 -m unittest tests.research_tests.test_steady_uptrend_v3_selection tests.workflows_tests.test_steady_uptrend_v3_research_scan
python3 -m json.tool configs/strategies/steady_uptrend_pre_breakout_watch.example.json >/dev/null
rg 'min_(pre_breakout_)?amount_ratio_20d' configs/strategies
```

Expected: tests pass；活动配置扫描无匹配。

- [ ] **Step 4: 提交**

```bash
git add stock_lobster/research/steady_uptrend_v3.py configs/strategies tests
git commit -m "feat: unify strategy volume ratio threshold"
```

### Task 5: 部署、重导和效果验证

**Files:**
- Update generated: `docs/research_reports/20260711-amount-repaired-strategy-baseline.csv`
- Update generated: `docs/research_reports/20260711-amount-repaired-strategy-baseline.md`

**Interfaces:**
- Consumes repaired QFQ kline and newly exported stock context.
- Produces sample recall report and 2026-07-10 full-market artifacts.

- [ ] **Step 1: 本地/远程完整验证**

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
find configs -name '*.json' -print0 | xargs -0 -n1 python3 -m json.tool >/dev/null
git diff --check
```

- [ ] **Step 2: 备份并部署远程策略文件**

只覆盖本次变更文件；保留服务器实际调度 JSON 和其它未提交改动。

- [ ] **Step 3: 重导 2026-07-10 正式上下文和全部样本日期上下文**

确认 TSV header 含 `volume_ratio_5d_20d`，且 `20260710` 非空覆盖不少于 5000 只。

- [ ] **Step 4: 重跑正式策略、样本复盘和 v3/v3.1 扫描**

输出新旧候选差异、23个正样本召回、4个硬负误召回、每层数量和量比阻断分布。

- [ ] **Step 5: 提交报告、推送分支并检查后台进程**

```bash
git add docs/research_reports
git commit -m "docs: refresh volume gate strategy evaluation"
git push origin codex/amount-unit-repair
```

远程不得遗留策略、导出或质量检查后台进程。
