# Token Fetch Amount Unit Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将外部事实生产者的 A 股日线成交额统一为 Tushare 原生千元口径，修复历史错误数据，重算衍生表并增加单位漂移阻断。

**Architecture:** `/home/ubuntu/token_fetch` 继续拥有事实数据生产和修复。采集入口通过独立单位函数保留 Tushare 原值，质量任务使用 `amount/(close*vol)` 检测数量级漂移，修复工具先审计和备份再更新事实表；Stock Lobster 不参与事实改写。

**Tech Stack:** Python 3.12、unittest、SQLAlchemy、PyMySQL、MySQL 8、Tushare Pro。

## Global Constraints

- 工作目录固定为 `/home/ubuntu/token_fetch`，当前分支为 `dev/basic_fetch_20260704`。
- 保留当前工作区已有改动，不重置、不覆盖与本计划无关的文件。
- `token_daily_details.amount` 单位为 `thousand_cny`，`vol` 单位为 `lot`。
- 历史修复边界固定为 `trade_date >= 20260427`。
- 任何历史 UPDATE 前必须创建只包含主键和原成交额的备份表。
- 先修新增数据生产逻辑，再修历史数据；修复完成前不得校准策略。

---

### Task 1: Tushare 日线成交额标准化入口

**Files:**
- Create: `data_utils/market_units.py`
- Modify: `cron_script/daily_kline_fetch_task.py:390-404`
- Create: `tests/test_market_units.py`

**Interfaces:**
- Consumes: Tushare `daily.amount`，单位千元。
- Produces: `normalize_tushare_daily_amount(value: object) -> float`。

- [ ] **Step 1: 写失败测试**

```python
import math
import unittest

from data_utils.market_units import normalize_tushare_daily_amount


class MarketUnitsTest(unittest.TestCase):
    def test_preserves_tushare_thousand_cny_amount(self) -> None:
        self.assertEqual(4_780_042.972, normalize_tushare_daily_amount(4_780_042.972))

    def test_rejects_invalid_amount(self) -> None:
        for value in (None, "", math.nan, math.inf, -0.01):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_tushare_daily_amount(value)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `venv/bin/python3 -m unittest tests.test_market_units -v`

Expected: FAIL，提示 `data_utils.market_units` 不存在。

- [ ] **Step 3: 实现最小单位函数并接入采集任务**

```python
from __future__ import annotations

import math


def normalize_tushare_daily_amount(value: object) -> float:
    """Return Tushare daily.amount unchanged in thousand CNY."""
    if value is None or str(value).strip() == "":
        raise ValueError("daily amount is required")
    amount = float(value)
    if not math.isfinite(amount) or amount < 0:
        raise ValueError("daily amount must be finite and non-negative")
    return amount
```

将采集映射改为：

```python
"amount": normalize_tushare_daily_amount(row["amount"]),
```

- [ ] **Step 4: 验证**

Run: `venv/bin/python3 -m unittest tests.test_market_units -v`

Expected: 2 tests PASS。

Run: `venv/bin/python3 -m py_compile data_utils/market_units.py cron_script/daily_kline_fetch_task.py`

Expected: exit 0。

- [ ] **Step 5: 提交**

```bash
git add data_utils/market_units.py cron_script/daily_kline_fetch_task.py tests/test_market_units.py
git commit -m "fix: preserve tushare daily amount unit"
```

### Task 2: 成交额单位质量阻断

**Files:**
- Modify: `data_utils/market_units.py`
- Modify: `cron_script/daily_quality_check_task.py:431-760`
- Modify: `tests/test_market_units.py`

**Interfaces:**
- Consumes: 最近交易日的平均 `amount/(close*vol)` 和有效记录数。
- Produces: `evaluate_daily_amount_unit(avg_ratio, valid_rows)`；质量报告字段 `amount_unit_consistency`。

- [ ] **Step 1: 写失败测试**

```python
from data_utils.market_units import evaluate_daily_amount_unit


def test_accepts_thousand_cny_ratio(self) -> None:
    result = evaluate_daily_amount_unit(0.1012, 5_490)
    self.assertEqual("ok", result["status"])

def test_rejects_ten_thousand_fold_drift(self) -> None:
    result = evaluate_daily_amount_unit(998.4, 5_490)
    self.assertEqual("critical", result["status"])
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `venv/bin/python3 -m unittest tests.test_market_units -v`

Expected: FAIL，提示函数未定义。

- [ ] **Step 3: 实现纯函数和 SQL 检查**

```python
def evaluate_daily_amount_unit(avg_ratio: float | None, valid_rows: int) -> dict[str, object]:
    valid = avg_ratio is not None and valid_rows >= 4_000 and 0.03 <= avg_ratio <= 0.30
    return {
        "status": "ok" if valid else "critical",
        "has_violations": not valid,
        "avg_amount_to_notional_ratio": avg_ratio,
        "valid_rows": valid_rows,
        "expected_range": [0.03, 0.30],
    }
```

数据库检查使用：

```sql
SELECT COUNT(*) valid_rows,
       AVG(amount / NULLIF(close * vol, 0)) avg_ratio
FROM token_daily_details
WHERE trade_date = :trade_date AND amount > 0 AND close > 0 AND vol > 0
```

状态为 `critical` 时加入 `critical_issues`，使质量任务退出码为 1。

- [ ] **Step 4: 验证**

Run: `venv/bin/python3 -m unittest tests.test_market_units -v`

Expected: 4 tests PASS。

Run: `venv/bin/python3 -m py_compile cron_script/daily_quality_check_task.py`

Expected: exit 0。

- [ ] **Step 5: 提交**

```bash
git add data_utils/market_units.py cron_script/daily_quality_check_task.py tests/test_market_units.py
git commit -m "feat: block daily amount unit drift"
```

### Task 3: 生产者字段契约

**Files:**
- Modify: `config/table_registry.yaml:89-103`
- Modify: `config/data_product_registry.yaml:100-130`
- Modify: `docs/DATA_PRODUCTS.md:65-85`

**Interfaces:**
- Consumes: Task 1 确立的字段口径。
- Produces: `field_units.amount=thousand_cny`、`field_units.vol=lot`。

- [ ] **Step 1: 在表注册表增加单位**

```yaml
    field_units:
      amount: thousand_cny
      vol: lot
```

- [ ] **Step 2: 在日线产品消费契约增加相同单位**

```yaml
      field_units:
        amount: thousand_cny
        vol: lot
```

- [ ] **Step 3: 更新文档字段表**

```markdown
| `vol` | 成交量，单位：手（lot） |
| `amount` | 成交额，单位：千元人民币（thousand_cny），保留 Tushare daily 原始口径 |
```

- [ ] **Step 4: 验证**

Run: `venv/bin/python3 cron_script/workflow_guard.py validate`

Expected: exit 0。

Run: `git diff --check -- config/table_registry.yaml config/data_product_registry.yaml docs/DATA_PRODUCTS.md`

Expected: no output。

- [ ] **Step 5: 提交**

```bash
git add config/table_registry.yaml config/data_product_registry.yaml docs/DATA_PRODUCTS.md
git commit -m "docs: declare daily amount field unit"
```

### Task 4: 可恢复的历史修复工具

**Files:**
- Create: `cron_script/repair_daily_amount_unit.py`
- Create: `tests/test_repair_daily_amount_unit.py`

**Interfaces:**
- Consumes: `--start-date 20260427`、可选 `--apply`。
- Produces: `token_daily_details_amount_backup_20260711`、审计 JSON、退出码 0/1。

- [ ] **Step 1: 写失败测试**

```python
import unittest

from cron_script.repair_daily_amount_unit import RepairSettings, build_repair_sql


class RepairDailyAmountUnitTest(unittest.TestCase):
    def test_update_is_bounded_and_idempotent(self) -> None:
        sql = build_repair_sql(RepairSettings(start_date="20260427"))
        self.assertIn("trade_date >= :start_date", sql)
        self.assertIn("amount = amount / 10000", sql)
        self.assertIn("amount / NULLIF(close * vol, 0) > 3", sql)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `venv/bin/python3 -m unittest tests.test_repair_daily_amount_unit -v`

Expected: FAIL，修复模块不存在。

- [ ] **Step 3: 实现 dry-run、备份和事务更新**

更新语句固定为：

```sql
UPDATE token_daily_details
SET amount = amount / 10000
WHERE trade_date >= :start_date
  AND amount > 0 AND close > 0 AND vol > 0
  AND amount / NULLIF(close * vol, 0) > 3
```

`--apply` 前创建：

```sql
CREATE TABLE token_daily_details_amount_backup_20260711 AS
SELECT ts_code, trade_date, amount
FROM token_daily_details
WHERE trade_date >= '20260427'
  AND amount > 0 AND close > 0 AND vol > 0
  AND amount / NULLIF(close * vol, 0) > 3
```

备份表已存在时拒绝执行。dry-run 只输出受影响行数、日期范围和修复后预估比例。

- [ ] **Step 4: 测试并 dry-run**

Run: `venv/bin/python3 -m unittest tests.test_repair_daily_amount_unit -v`

Expected: PASS。

Run: `venv/bin/python3 cron_script/repair_daily_amount_unit.py --start-date 20260427`

Expected: `mode=dry_run`，受影响行数大于 0。

- [ ] **Step 5: 提交**

```bash
git add cron_script/repair_daily_amount_unit.py tests/test_repair_daily_amount_unit.py
git commit -m "feat: add audited daily amount repair"
```

### Task 5: 执行修复、重算与 SQL 验收

**Files:**
- Runtime database mutation only.
- Create runtime audit: `reports/amount_unit_repair_20260711.json`

**Interfaces:**
- Consumes: Task 4 修复工具和现有统计任务。
- Produces: 单位一致的源表、衍生表和 SQL 验收证据。

- [ ] **Step 1: 执行最终 dry-run**

Run: `venv/bin/python3 cron_script/repair_daily_amount_unit.py --start-date 20260427`

Expected: 修复后预估平均比例位于 `[0.03,0.30]`。

- [ ] **Step 2: 执行事务修复**

Run: `venv/bin/python3 cron_script/repair_daily_amount_unit.py --start-date 20260427 --apply`

Expected: 创建备份表，审计状态为 `success`。

- [ ] **Step 3: 重算日成交额统计**

对以下查询返回的每个交易日执行 `daily_amount_statistics_task.py --date YYYY-MM-DD --force`：

```sql
SELECT DISTINCT trade_date
FROM token_daily_details
WHERE trade_date >= '20260427'
ORDER BY trade_date;
```

Expected: 每日任务均返回 `success: True`。

- [ ] **Step 4: 验证并重算周/月成交额产品**

先用 `amount/(close*vol)` 验证 `token_weekly_details` 始终为独立 Tushare 千元口径，不对正确周线事实做缩放。对以下查询返回的每个周线日期执行 `weekly_amount_statistics_task.py --date YYYY-MM-DD --force`：

```sql
SELECT DISTINCT trade_date
FROM token_weekly_details
WHERE trade_date >= '20260427'
ORDER BY trade_date;
```

对以下查询返回的每个月末日期执行 `monthly_kline_fetch_task.py --date YYYY-MM-DD --force`：

```sql
SELECT MAX(trade_date) period_end_date
FROM token_daily_details
WHERE trade_date >= '20260401'
GROUP BY LEFT(trade_date, 6)
ORDER BY period_end_date;
```

Expected: 每个指定日期任务退出码为 0；周线千元事实不被重复缩放，月线覆盖 2026-04 起全部月份。

- [ ] **Step 5: SQL 验收**

```sql
SELECT trade_date, COUNT(*) rows_count,
       AVG(amount / NULLIF(close * vol, 0)) avg_ratio
FROM token_daily_details
WHERE trade_date IN ('20260424','20260427','20260428')
GROUP BY trade_date;

SELECT COUNT(*) mismatch_rows
FROM amount_daily_statistic s
JOIN token_daily_details d USING (ts_code, trade_date)
WHERE s.trade_date >= '20260427'
  AND ABS(s.amount - d.amount) > 0.01;
```

Expected: 三日 `avg_ratio` 均在 `[0.03,0.30]`；`mismatch_rows=0`。

- [ ] **Step 6: 运行生产质量检查**

Run: `venv/bin/python3 cron_script/daily_quality_check_task.py`

Expected: `amount_unit_consistency.status=ok`，退出码 0。
