# Stock Lobster Amount Contract And Recall Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Stock Lobster 显式消费千元成交额契约，并在事实数据修复后重新评估量比和 MA30 分形态召回规则。

**Architecture:** L0 `DataAsset` 保存并校验字段单位，策略金额门槛统一使用千元输入值。现有含当日 `amount_ratio_20d` 保持兼容，同时增加不含当日的研究指标；量比 1.5 和 MA30 90 日承接从通用硬门槛降为分形态标签或评分项。所有新召回逻辑保持 `research_only`。

**Tech Stack:** Python 3.12、dataclasses、unittest、JSON、MySQL 输入导出、Stock Lobster L0-L4/research。

## Global Constraints

- 工作目录固定为 `/Users/kk/git_project/token_parse_sys`。
- 保留当前工作区已有改动，只修改任务列出的文件。
- Stock Lobster 不得按日期修补或改写权威事实数据。
- `amount` 和 `avg_amount_20d` 输入单位固定为 `thousand_cny`。
- 2 亿元流动性门槛表示为 `200_000` 千元。
- 新分子池规则保持 `research_only`，不直接替换生产策略。
- 远端事实修复 SQL 验收通过后，才能执行 Task 4 及以后。

---

### Task 1: L0 字段单位契约

**Files:**
- Modify: `stock_lobster/l0_data_access/contracts.py`
- Modify: `stock_lobster/l0_data_access/config_loader.py`
- Modify: `configs/data_assets/published_products.example.json`
- Modify: `tests/l0_data_access_tests/test_config_loader.py`

**Interfaces:**
- Consumes: 上游 `consumer_contract.field_units`。
- Produces: `DataAsset.field_units` 和 `require_field_unit(field_name, expected_unit)`。

- [ ] **Step 1: 写失败测试**

```python
def test_loads_and_validates_field_units(self) -> None:
    payload = sample_catalog_payload()
    product = payload["products"][0]
    product["consumer_contract"]["field_units"] = {
        "amount": "thousand_cny",
        "vol": "lot",
    }
    asset = DataAssetCatalogLoader().from_mapping(payload).catalog.get(
        "external_provider.pub_stock_daily_kline"
    )
    self.assertEqual("thousand_cny", asset.field_units["amount"])
    asset.require_field_unit("amount", "thousand_cny")
    with self.assertRaisesRegex(ValueError, "amount unit mismatch"):
        asset.require_field_unit("amount", "cny")
```

- [ ] **Step 2: 运行并确认失败**

Run: `/opt/homebrew/bin/python3.12 -m unittest tests.l0_data_access_tests.test_config_loader -v`

Expected: FAIL，`DataAsset` 没有 `field_units`。

- [ ] **Step 3: 实现字段单位契约**

```python
field_units: Mapping[str, str] = field(default_factory=dict)

def require_field_unit(self, field_name: str, expected_unit: str) -> None:
    actual = self.field_units.get(field_name)
    if actual != expected_unit:
        raise ValueError(
            f"{self.asset_id}.{field_name} unit mismatch: expected {expected_unit}, got {actual}"
        )
```

加载器从 `consumer_contract.field_units` 构建映射。日、周、月 K 线资产均声明：

```json
"field_units": {"amount": "thousand_cny", "vol": "lot"}
```

- [ ] **Step 4: 验证**

Run:

```bash
/opt/homebrew/bin/python3.12 -m unittest tests.l0_data_access_tests.test_config_loader tests.l1_analysis_snapshot_tests.test_snapshot_input_builder -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add stock_lobster/l0_data_access/contracts.py stock_lobster/l0_data_access/config_loader.py configs/data_assets/published_products.example.json tests/l0_data_access_tests/test_config_loader.py
git commit -m "feat: validate market data field units"
```

### Task 2: 千元流动性门槛迁移

**Files:**
- Modify: `stock_lobster/l2_primitives/technical.py:122-125`
- Modify: `configs/primitives/primitive_registry.example.json:345-357`
- Modify: `configs/strategies/steady_uptrend_breakout_watch.example.json`
- Modify: `configs/strategies/steady_uptrend_breakout_watch_candidate_v2.example.json`
- Modify: `configs/strategies/steady_uptrend_pre_breakout_watch.example.json`
- Modify: `configs/strategies/steady_uptrend_pre_breakout_watch_candidate_v3.example.json`
- Modify: `configs/strategies/steady_uptrend_pre_breakout_watch_candidate_v3_1.example.json`
- Modify: `tests/workflows_tests/test_daily_strategy_signal_production.py`
- Modify: `tests/research_tests/test_steady_uptrend_breakout_case.py`

**Interfaces:**
- Consumes: `avg_amount_20d`，单位千元。
- Produces: 2 亿元对应配置值 `200_000`。

- [ ] **Step 1: 修改测试期望并确认失败**

```python
self.assertEqual(200_000, policy.min_avg_amount_20d)
```

Run: `/opt/homebrew/bin/python3.12 -m unittest tests.workflows_tests.test_daily_strategy_signal_production -v`

Expected: FAIL，当前配置仍为 `2_000_000_000`。

- [ ] **Step 2: 修改原语和所有策略配置**

```python
def avg_amount_20d_ge_2e(snapshot: AnalysisSnapshot) -> bool:
    return get_indicator_value(snapshot, "avg_amount_20d") >= 200_000
```

```json
"min_avg_amount_20d": 200000,
"min_avg_amount_20d_note": "输入单位为千元人民币；200,000 千元对应 2 亿元。"
```

primitive registry 参数改为：

```json
"min_avg_amount_20d_thousand_cny": 200000,
"amount_unit": "thousand_cny"
```

- [ ] **Step 3: 扫描旧口径**

Run: `rg -n "2000000000|实际成交额\(元\) \* 10|actual yuan times 10" configs stock_lobster tests docs`

Expected: 不再命中有效策略、原语和研究地图中的旧口径。

- [ ] **Step 4: 验证**

Run:

```bash
/opt/homebrew/bin/python3.12 -m unittest tests.workflows_tests.test_daily_strategy_signal_production tests.research_tests.test_steady_uptrend_breakout_case tests.research_tests.test_trend_breakout_scan -v
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add stock_lobster/l2_primitives/technical.py configs/primitives configs/strategies tests/workflows_tests/test_daily_strategy_signal_production.py tests/research_tests/test_steady_uptrend_breakout_case.py
git commit -m "fix: migrate liquidity threshold to thousand cny"
```

### Task 3: 前 20 日成交额研究指标

**Files:**
- Modify: `stock_lobster/research/trend_breakout_scan.py`
- Modify: `tests/research_tests/test_trend_breakout_scan.py`
- Modify: `configs/technical_indicators/basic_technical_indicators.example.json`

**Interfaces:**
- Consumes: 按资产和交易日排序的成交额序列。
- Produces: `TrendBreakoutMetrics.amount_ratio_prev_20d`；保留现有 `amount_ratio_20d`。

- [ ] **Step 1: 写失败测试**

```python
def test_amount_ratio_prev_20d_excludes_signal_day(self) -> None:
    bars = _daily_breakout_bars("000099.SZ")
    previous_average = sum(bar.amount for bar in bars[-21:-1]) / 20
    latest = scan_trend_breakouts(bars)[-1]
    self.assertAlmostEqual(
        bars[-1].amount / previous_average,
        latest.amount_ratio_prev_20d,
        places=6,
    )
```

- [ ] **Step 2: 运行并确认失败**

Run: `/opt/homebrew/bin/python3.12 -m unittest tests.research_tests.test_trend_breakout_scan.TrendBreakoutScanTest.test_amount_ratio_prev_20d_excludes_signal_day -v`

Expected: FAIL，指标字段未定义。

- [ ] **Step 3: 实现不含当日的滚动指标**

```python
previous_amount_average_20d = sum(amounts[index - 20:index]) / 20
amount_ratio_prev_20d = bar.amount / previous_amount_average_20d
```

仅在 `index >= 20` 且分母大于 0 时生成。现有含当日指标公式不变。

- [ ] **Step 4: 验证**

Run: `/opt/homebrew/bin/python3.12 -m unittest tests.research_tests.test_trend_breakout_scan -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add stock_lobster/research/trend_breakout_scan.py tests/research_tests/test_trend_breakout_scan.py configs/technical_indicators/basic_technical_indicators.example.json
git commit -m "feat: add previous 20 day amount ratio"
```

### Task 4: 修复后输入刷新和现有策略基线

**Files:**
- Create: `docs/research_reports/20260711-amount-repaired-strategy-baseline.md`
- Create: `docs/research_reports/20260711-amount-repaired-sample-blockers.csv`
- Runtime: `/home/ubuntu/token_parse_sys/runtime/strategy_signal_production/`

**Interfaces:**
- Consumes: SQL 验收通过的远端事实和成交额统计。
- Produces: 正负、等待、低价值样本逐层阻断基线。

- [ ] **Step 1: 重新导出全部样本事件输入**

Run:

```bash
/opt/homebrew/bin/python3.12 workflows/jobs/research_kline_batch_export.py --help
/opt/homebrew/bin/python3.12 workflows/jobs/research_stock_context_batch_export.py --help
```

Expected: 两个入口退出码 0；实际导出固定使用 `qfq_asof` 和千元成交额。

- [ ] **Step 2: 不改阈值运行现有五个策略**

运行 `breakout_v1`、`breakout_v2_weak_shape`、`pre_breakout_v1`、`pre_breakout_v3`、`pre_breakout_v3_1`，记录每层数量和每个样本首个阻断条件。

- [ ] **Step 3: 核对修复口径**

报告必须包含：

```text
avg_amount_20d threshold = 200000 thousand_cny
amount ratio window = inclusive current 20d
amount unit discontinuity count = 0
```

并单列 2026-04-27 后 20 个交易日的修复前后量比变化。

- [ ] **Step 4: 校验并提交基线**

Run: `git diff --check -- docs/research_reports/20260711-amount-repaired-strategy-baseline.md docs/research_reports/20260711-amount-repaired-sample-blockers.csv`

Expected: no output。

```bash
git add docs/research_reports/20260711-amount-repaired-strategy-baseline.md docs/research_reports/20260711-amount-repaired-sample-blockers.csv
git commit -m "docs: record repaired amount strategy baseline"
```

### Task 5: 分形态量比和 MA30 召回候选

**Files:**
- Create: `stock_lobster/research/trend_recall_subpools.py`
- Create: `tests/research_tests/test_trend_recall_subpools.py`
- Create: `configs/strategies/trend_recall_subpools_candidate_v1.example.json`
- Create: `workflows/jobs/trend_recall_subpools_research_scan.py`

**Interfaces:**
- Consumes: `TrendBreakoutMetrics`、最低数据质量和基础流动性结果。
- Produces: `RecallSubpoolMatch(subpool_id, matched, score_adjustment, reasons)`。

- [ ] **Step 1: 写失败测试**

```python
def test_reacceleration_uses_recent_ma30_support_without_volume_hard_gate(self) -> None:
    metric = metric_fixture(
        ma30_hold_ratio_30d=0.96,
        ma30_hold_ratio_60d=0.60,
        ma30_hold_ratio_90d=0.54,
        amount_ratio_prev_20d=1.05,
    )
    result = classify_recall_subpools(metric)
    self.assertTrue(result["pullback_reacceleration"].matched)
    self.assertNotIn("amount_ratio_below_1_5", result["pullback_reacceleration"].reasons)
```

- [ ] **Step 2: 运行并确认失败**

Run: `/opt/homebrew/bin/python3.12 -m unittest tests.research_tests.test_trend_recall_subpools -v`

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现五个 research-only 子池**

```json
{
  "lifecycle_status": "research_only",
  "subpools": {
    "long_base_breakout": {"amount_ratio_mode": "score"},
    "pullback_reacceleration": {"min_ma30_hold_30d": 0.75, "min_ma30_hold_60d": 0.55},
    "ma10_ma20_walkup": {"amount_ratio_mode": "score"},
    "trend_following": {"ma30_hold_90d_mode": "quality_score"},
    "early_reversal": {"require_ma30_hold_90d": false}
  }
}
```

五个子池都在最低数据质量和基础流动性之后执行。`amount_ratio_prev_20d >= 1.5` 只产生强放量加分。

- [ ] **Step 4: 验证**

Run:

```bash
/opt/homebrew/bin/python3.12 -m unittest tests.research_tests.test_trend_recall_subpools -v
/opt/homebrew/bin/python3.12 workflows/jobs/trend_recall_subpools_research_scan.py --help
```

Expected: PASS；CLI 退出码 0。

- [ ] **Step 5: 提交**

```bash
git add stock_lobster/research/trend_recall_subpools.py tests/research_tests/test_trend_recall_subpools.py configs/strategies/trend_recall_subpools_candidate_v1.example.json workflows/jobs/trend_recall_subpools_research_scan.py
git commit -m "feat: add research trend recall subpools"
```

### Task 6: 正负样本与历史事件验收

**Files:**
- Create: `docs/research_reports/20260711-trend-recall-subpools-evaluation.md`
- Create: `docs/research_reports/20260711-trend-recall-subpools-events.csv`

**Interfaces:**
- Consumes: Task 4 基线和 Task 5 分子池候选。
- Produces: 召回变化、误召回变化和逐条件证据。

- [ ] **Step 1: 运行样本日期精确回放**

每个事件记录：

```text
data_quality_pass,basic_liquidity_pass,matched_subpools,volume_confirmation,
ma30_support_branch,negative_shape_reasons,final_recall
```

- [ ] **Step 2: 运行全交易日历史回测**

比较组固定为生产 `pre_breakout_v1`、修复后同口径基线、`trend_recall_subpools_candidate_v1`；输出 H5/H10/H20 收益、胜率、最大回撤和候选数量。

- [ ] **Step 3: 写报告**

必须列出每个新增正样本的子池来源、每个负/等待/低价值样本的误召回变化、量比 1.0/1.1/1.2/1.5 分档、MA30 30/60/90 日分布和未解决负向形态。

- [ ] **Step 4: 验证生命周期和格式**

Run: `rg -n '"lifecycle_status": "research_only"' configs/strategies/trend_recall_subpools_candidate_v1.example.json`

Expected: 命中 `research_only`。

Run: `git diff --check -- docs/research_reports/20260711-trend-recall-subpools-evaluation.md docs/research_reports/20260711-trend-recall-subpools-events.csv`

Expected: no output。

- [ ] **Step 5: 提交**

```bash
git add docs/research_reports/20260711-trend-recall-subpools-evaluation.md docs/research_reports/20260711-trend-recall-subpools-events.csv
git commit -m "docs: evaluate trend recall subpools"
```
