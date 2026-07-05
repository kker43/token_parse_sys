# Workflow 001：数据基础 MVP

## 目的

定义把基础事实数据能力接入 `token_parse_sys` 的第一段可执行切片。

本工作流覆盖：

- 外部事实数据契约。
- 基础数据产品接口。
- 例行数据生产入口。
- 例行质量监控。
- Stock Lobster L0 消费边界。

本工作流不覆盖：

- 形态研究。
- 原语。
- 标签。
- 策略 DSL。
- 信号生成。
- 回测执行。
- 观察复盘。

这些属于后续工作流，应在本数据基础切片稳定后再做。

## 模型建议

本工作流被接受前，不要切换到更小模型。

推荐拆分：

| 工作 | 模型 |
| --- | --- |
| 工作流设计、边界决策、schema 决策 | GPT-5.5 |
| 确定性代码实现和测试 | GPT-5.4 |
| registry 扫描、配置草稿生成、重复检查 | GPT-5.4-Mini |
| 极小本地修复 | GPT-5.3-Codex-Spark |

本文档后的第一段代码实现可以使用 GPT-5.4，只要该会话先阅读本工作流、`AGENTS.md` 和标准文档。

## 当前上游假设

上游事实生产者是：

```text
host: ubuntu@111.229.103.59
path: <external_producer_root>
inspection snapshot: external factual producer inspected on 2026-07-04
```

MVP 期间，外部事实生产者仍作为运行中的生产者。本项目暂时不重写或移动它。

`token_parse_sys` 消费它暴露的稳定契约和就绪状态。

## 目标边界

```text
外部事实生产者
  -> 生产事实表和 pub_* 产品
  -> 暴露 registry 文件和质量状态

token_parse_sys/data_foundation
  -> 镜像或读取契约
  -> 校验产品就绪状态
  -> 为 Stock Lobster 导出 DataAsset 配置
  -> 提供例行 bridge 作业

token_parse_sys/stock_lobster/l0_data_access
  -> 消费 DataAsset 配置
  -> 除非明确标记为过渡用途，否则绝不直接读取外部事实生产者内部实现
```

## MVP 组件

### 1. 共享契约

位置：

```text
shared/contracts/
```

初始对象：

```text
DataProductContract
DataProductField
DataQualityStatus
IndicatorContract
PublishedProductRef
```

职责：

- 定义通用词汇。
- 保留产品、字段、版本、日期、质量和来源语义。
- 可被 `data_foundation` 和 `stock_lobster` 导入。

非目标：

- 数据库访问。
- 生产调度。
- 策略语义。

### 2. Provider Bridge（供应方桥接）

位置：

```text
data_foundation/provider_bridge/
```

初始服务：

```text
RegistryReader
PublishedProductCatalog
PublishedQualityReader
```

职责：

- 从 `<external_producer_root>` 读取或镜像选定 registry 文件。
- 暴露标准化契约对象。
- 在元数据中保留来源路径、分支、commit 和 registry 版本。

非目标：

- 直接用于策略。
- 移动外部事实生产者。
- 重写外部事实生产者任务。
- 写入上游表。

### 3. 数据资产导出

位置：

```text
data_foundation/catalog_export/
configs/data_assets/
stock_lobster/l0_data_access/
```

初始输出：

```text
configs/data_assets/published_products.example.json
```

初始产品：

```text
pub_data_quality_status
pub_stock_daily_kline
pub_stock_weekly_kline
pub_stock_monthly_kline
pub_stock_daily_basic
pub_stock_asset_basic
pub_stock_daily_indicator
```

职责：

- 将上游 `pub_*` 契约转成 Stock Lobster L0 `DataAsset` 配置。
- 包含字段 schema、质量门、来源产品、数据版本和日期语义。
- 让配置足够稳定，可供 L1 快照构建器使用。

### 4. 例行作业入口

位置：

```text
workflows/jobs/
```

初始作业：

```text
daily_fact_data_production.py
daily_data_quality_monitor.py
daily_data_asset_export.py
```

职责：

- 作为稳定的调度器入口。
- 保留 `run_id`。
- 调用确定性服务。
- 失败时返回非零。
- 写入结构化作业结果。

过渡行为：

- `daily_fact_data_production.py` 过渡期可以包装现有 `<external_producer_root>` 调度器。
- 它不得内联外部事实生产者逻辑。
- 它必须记录使用了哪个上游 commit 或契约快照。

### 5. 公共接口

位置：

```text
interfaces/cli/
interfaces/sql/
```

初始 CLI 命令：

```text
data-foundation list-products
data-foundation check-readiness --date YYYYMMDD
data-foundation export-data-assets
```

初始 SQL 示例：

```text
interfaces/sql/check_pub_data_quality_status.sql
interfaces/sql/select_pub_stock_daily_indicator.sql
```

职责：

- 提供面向运维的稳定入口。
- 避免要求用户或作业 import 内部模块。

### 6. 质量监控

位置：

```text
data_foundation/quality/
workflows/jobs/daily_data_quality_monitor.py
```

初始检查：

- 产品就绪记录存在。
- 状态为 `ready`。
- 质量级别为 `pass` 或 `warning`。
- 记录数达到最低预期。
- 主日期字段匹配请求日期。
- 根据契约，核心字段非空。
- 产品数据版本匹配 registry。

质量结果：

```text
DataProductReadinessResult
```

质量监控器应报告就绪状态。它不应修改策略或经验 artifact。

## 例行与被动拆分

| 区域 | 例行？ | 第一位置 |
| --- | --- | --- |
| 契约 dataclass | 否 | `shared/contracts/` |
| registry 读取器 | 否 | `data_foundation/provider_bridge/` |
| 就绪检查器 | 否 | `data_foundation/quality/` |
| 数据资产导出器 | 按需或调度 | `data_foundation/catalog_export/` |
| 事实生产包装器 | 是 | `workflows/jobs/daily_fact_data_production.py` |
| 质量监控作业 | 是 | `workflows/jobs/daily_data_quality_monitor.py` |
| 运维 CLI | 被动 | `interfaces/cli/` |
| SQL 示例 | 被动 | `interfaces/sql/` |
| Stock Lobster L0 目录 | 被动 | `stock_lobster/l0_data_access/` |

## 第一段代码切片

第一轮编码会话实现：

```text
shared/contracts/
  __init__.py
  data_product.py
  quality.py

data_foundation/
  __init__.py
  provider_bridge/
    __init__.py
    registry_reader.py
  quality/
    __init__.py
    readiness.py
  catalog_export/
    __init__.py
    data_asset_exporter.py

configs/data_assets/
  published_products.example.json

tests/
  test_import_boundaries.py
  data_foundation/
    test_data_product_contract.py
    test_readiness.py
```

除非明确添加 YAML 解析依赖，否则第一版纳入版本管理的示例配置使用 JSON。上游可以继续保持 YAML。

## 第二段代码切片

第一段通过测试后：

```text
workflows/jobs/
  daily_data_asset_export.py
  daily_data_quality_monitor.py

interfaces/cli/
  data_foundation.py

interfaces/sql/
  check_pub_data_quality_status.sql
  select_pub_stock_daily_indicator.sql
```

这些应调用第一段切片提供的服务。

## 验收标准

MVP 完成标准：

- `DataProductContract` 可以表示所有第一阶段 `pub_*` 产品。
- L0 `DataAsset` 配置可以从这些契约导出。
- 就绪检查器可以对某个产品/日期做确定性的通过或阻断判断。
- 用于质量监控和数据资产导出的例行作业入口存在。
- 没有 Stock Lobster 策略层读取外部事实生产者内部实现。
- 导入边界测试阻止下层导入编排代码。
- 所有测试在本地通过。

## 未决决策

- 生产配置先用 JSON，还是项目添加 PyYAML？
- bridge 在服务器上直接读取 `<external_producer_root>/config/*.yaml`，还是先把这些 registry 导出到本项目？
- `daily_fact_data_production.py` 第一阶段调用现有外部事实生产者调度器，还是只监控其输出？
- 结构化作业结果应持久化到哪里：文件、MySQL、SQLite，还是后续应用表？

## 交接给 GPT-5.4 实现的 Prompt

```text
你正在实现 Workflow 001：数据基础 MVP。
阅读 AGENTS.md、PLANS.md、docs/standards/001-system-structure-and-model-guidance.md、
docs/standards/002-data-foundation-integration.md、
docs/standards/003-remote-system-execution-layout.md 和
docs/workflows/001-data-foundation-mvp.md。

只实现第一段代码切片：
- shared/contracts 数据产品和质量模型
- data_foundation provider_bridge registry reader 骨架
- data_foundation quality readiness checker
- data_foundation catalog_export data asset exporter
- 示例 JSON data asset 配置
- 聚焦测试

不要修改外部事实生产者。
不要实现策略、原语、标签、信号、回测或观察。
被动服务通过测试前，不要添加例行作业。
运行 unittest，并报告层级边界状态。
```
