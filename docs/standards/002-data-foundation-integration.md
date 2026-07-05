# Standard 002：数据基础集成

## 目的

本标准记录上游事实数据项目应如何纳入更大的 Stock Lobster 系统。

它基于一次只读检查：

- 远程主机：`ubuntu@111.229.103.59`
- 已配置生产者根目录：`<external_producer_root>`
- 检查日期：2026-07-04

最近一次检查时，被检查的源码 checkout 是干净的。

## 远程部署目标

推荐的未来项目目录：

```text
/home/ubuntu/token_parse_sys
```

这个名称与 `docs/standards/001-system-structure-and-model-guidance.md` 中的大型项目结构一致。

不要覆盖已有远程项目，例如：

- `<external_producer_root>`
- `/home/ubuntu/token_parse`
- `/home/ubuntu/token_parse_recall`
- `/home/ubuntu/token_recall`

项目部署到服务器时，在 `/home/ubuntu` 下创建新目录，然后把本仓库复制或 clone 到那里。在集成计划完成前，不要移动已配置的生产者 checkout。

## 上游当前方向

被检查的外部事实生产者已经符合期望的职责分离：

```text
source/raw -> fact -> statistic/basic_indicator -> publish/pub_*
```

它明确排除：

- primitive（原语）
- signal（信号）
- strategy（策略）
- backtest（回测）
- portfolio（组合）
- 交易候选或买卖决策

这与 Stock Lobster 兼容：

```text
data_foundation
-> shared contracts
-> stock_lobster.l0_data_access
-> stock_lobster.l1_analysis_snapshot
-> stock_lobster.research
-> L2-L6
```

## 推荐放置方式

如果本仓库演进为 `token_parse_sys`，将上游项目放置为：

```text
token_parse_sys/
  data_foundation/
    provider_bridge/
    sources/
    ingestion/
    normalization/
    indicators/
    quality/
    catalog_export/
    jobs/

  shared/
    contracts/
    schemas/

  stock_lobster/
    l0_data_access/
    l1_analysis_snapshot/
    research/
    l2_primitives/
    l3_labels/
    l4_strategy_dsl/
    l5_signal_engine/
    l6_backtest_engine/
```

迁移应循序渐进：

1. 保持 `<external_producer_root>` 独立运行。
2. 从外部事实生产者导出稳定契约。
3. 在 Stock Lobster L0 中消费这些契约。
4. 只有在契约稳定后，才把选定源码移动或镜像到 `data_foundation`。

## 不要迁移运行态 artifact

不要把这些内容从外部事实生产者复制到干净项目中：

- `venv/`
- `logs/`
- `tracker/`
- 本地备份 zip。
- 项目根目录下的运行态 tracker JSON 文件。
- `.git/`
- 机器本地 secret，例如 `config/config.ini`。

这些可以留在运行生产者所在的服务器上。

## 可复用的契约资产

以下上游文件适合作为起点：

```text
config/table_registry.yaml
config/task_registry.yaml
config/data_product_registry.yaml
config/indicator_registry.yaml
docs/DATA_STANDARD.md
docs/DATA_PRODUCTS.md
docs/PROJECT_STRUCTURE.md
product_engine/models.py
product_engine/registry.py
```

SQL 文件应作为草稿对待：

```text
sql/views/pub_stock_kline_views.sql
sql/views/pub_stock_basic_views.sql
sql/migrations/002_create_pub_stock_daily_indicator.sql
```

## 暴露给 Stock Lobster 的数据产品

初始 L0 `DataAsset` 条目应来自 `pub_*` 产品：

| 数据产品 | Stock Lobster 用途 |
| --- | --- |
| `pub_data_quality_status` | 消费任何产品前的就绪门 |
| `pub_stock_daily_kline` | 日线价格/成交量事实 |
| `pub_stock_weekly_kline` | 周线价格/成交量事实 |
| `pub_stock_monthly_kline` | 月线价格/成交量事实 |
| `pub_stock_daily_basic` | 每日估值和基础事实 |
| `pub_stock_asset_basic` | 资产身份和分类 |
| `pub_stock_daily_indicator` | 长表基础指标 |

默认情况下，Stock Lobster 不应消费内部表。只有过渡诊断场景允许直接读取 `token_daily_details` 或 `ma_price_daily_statistic` 等表，并且必须记录为临时用法。

## 作为经验输入的基础指标

以下上游指标可作为事实或基础指标输入：

- `close_new_high_60d_flag`
- `pct_change_20d`
- `amount_ratio_20d`
- `volatility_60d`
- `ma20`
- `close_above_ma20_flag`
- `convergence_5_10_20`
- `convergence_5_10_20_pct`
- `return_ratio_5d_20d`
- `volatility_ratio_5d_20d`
- `volume_ratio_5d_20d`

它们本身不是 Stock Lobster 原语。Stock Lobster 可以用它们构建：

- `AnalysisSnapshot` 字段。
- `FactorObservation`。
- `PrimitiveCandidate`。
- 经样本验证后的已批准 L2 原语。
- 确定性定义后的已批准 L3 标签。

## 生产使用前需要修改的事项

### 1. 先发布质量状态

`pub_data_quality_status` 是预期的就绪门，但实现仍在计划中。下游生产依赖 `pub_*` 之前，应先实现它。

最低要求：

```text
data_product
data_date
market
asset_type
status
quality_level
record_count
expected_min_records
source_tables
source_end_date
published_at
data_version
error_message
```

### 2. 不要硬编码 `quality_status = 'pass'`

当前 SQL 草稿在视图中直接把 `quality_status` 设置为 `pass`。这对下游生产不安全。

推荐做法：

- 写入或计算产品级质量结果。
- 写入 `pub_data_quality_status`。
- 只有质量门就绪后才暴露产品行。
- 只有存在真实行级检查时，才携带行级质量。

### 3. 可复现视图中避免动态 `CURRENT_TIMESTAMP`

草稿视图使用 `CURRENT_TIMESTAMP AS published_at`。这会让每次查询结果都变化，削弱可复现性。

推荐做法：

- 物化发布输出，并使用稳定的 `published_at`。
- 或连接稳定的发布批次/状态表。

### 4. 对齐 registry 和 SQL 字段

`pub_stock_daily_indicator` 文档提到可选的 `indicator_score` 和 `indicator_rank`，但草稿 DDL 未包含它们。

二选一：

- 添加可空的 `indicator_score` 和 `indicator_rank`。
- 或在支持前把它们从契约中移除。

### 5. 解决 `pub_stock_daily_basic` 来源不一致

`data_product_registry.yaml` 同时列出 `token_daily_basic` 和 `token_valuation_daily` 作为来源表，但草稿 SQL 当前只从 `token_daily_basic` 选择。

二选一：

- join 估值来源。
- 或更新 registry，使其匹配实际 v1 产品。

### 6. 复查 `stock_recall_daily`

`stock_recall_daily` 被分类为事实/事件。名称和语义可能看起来像策略召回。

只有当它被定义为中性事件事实时，例如“满足客观价格/成交量事件条件”，才应留在 `data_foundation`。如果它表示“某个策略的候选股票”，就应把该语义移入 Stock Lobster research 或 L4。

### 7. 扩展指标元数据

`indicator_registry.yaml` 最终应包含足够的可复现元数据：

- 公式描述。
- 参数 schema。
- 输入窗口。
- `source_start_date` 规则。
- `code_version`。
- 空值和异常值处理。

### 8. 将 `product_engine` 视为草稿框架

`product_engine.registry` 可以较快复用。`product_engine.publisher` 仍返回 `publisher_not_implemented`，因此尚未达到生产可用状态。

## 集成顺序

推荐下一步：

1. 稳定并版本化外部事实生产者契约。
2. 实现 `pub_data_quality_status`。
3. 修复上面的 SQL 草稿问题。
4. 将 `data_product_registry.yaml` 导出为第一份共享契约。
5. 为每个 `pub_*` 产品创建匹配的 Stock Lobster L0 `DataAsset` 配置。
6. 基于 `pub_stock_daily_kline`、`pub_stock_daily_basic`、`pub_stock_asset_basic` 和 `pub_stock_daily_indicator` 构建一个 L1 `AnalysisSnapshot`。
7. 用一个真实形态家族验证研究工作流。

## 当前推荐边界

保持这条规则：

```text
data_foundation 回答：有哪些事实数据和基础指标可用？
stock_lobster 回答：这些数据支持什么形态、原语、标签、策略和证据？
```

两部分可以存在于同一个大型项目中，但它们应通过包、registry、工作流和审批边界保持分离。
