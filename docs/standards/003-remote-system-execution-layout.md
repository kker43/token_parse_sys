# Standard 003：远程系统执行布局

## 目的

本标准定义大型项目在远程服务器上应如何组织，以及例行作业、外部接口、通用工具、契约和有界上下文代码应放在哪里。

目标远程根目录：

```text
/home/ubuntu/token_parse_sys
```

## 设计规则

项目应该是一个可运行系统，但不是一个扁平代码库。

使用一个根目录，并在其中拆分独立有界上下文：

```text
token_parse_sys/
  shared/
  data_foundation/
  stock_lobster/
  workflows/
  interfaces/
  tools/
  configs/
  ops/
  docs/
```

每个区域只承担一类职责。如果某个文件无法清楚归属于某个区域，在所有权明确前不要放入生产。

## 目标远程目录

```text
/home/ubuntu/token_parse_sys/
  README.md

  shared/
    contracts/
    schemas/
    calendar/
    enums/

  data_foundation/
    provider_bridge/
    sources/
    ingestion/
    normalization/
    indicators/
    quality/
    catalog_export/
    jobs/

  stock_lobster/
    core/
    l0_data_access/
    l1_analysis_snapshot/
    research/
    l2_primitives/
    l3_labels/
    l4_strategy_dsl/
    l5_signal_engine/
    l6_backtest_engine/
    observation/
    app/

  workflows/
    definitions/
    jobs/
    runners/

  interfaces/
    cli/
    api/
    sql/
    reports/

  tools/
    data_asset/
    snapshot/
    research/
    strategy/
    backtest/
    approval/
    observation/

  configs/
    data_sources/
    data_assets/
    primitives/
    labels/
    strategies/
    evaluation_profiles/
    schedules/

  ops/
    crontab/
    systemd/
    env/
    runbooks/
    logs/

  docs/
    decisions/
    standards/
    workflows/
    examples/
```

## 区域职责

### `shared/`（共享契约）

拥有跨上下文语言和契约。

放这里：

- 共享字段名。
- 资产 id 约定。
- 日期语义。
- 质量状态枚举。
- schema 片段。
- 版本和 run id 约定。

不要把可执行生产工作流放在这里。

### `data_foundation/`（数据基础）

拥有事实数据生产和基础指标。

放这里：

- 数据源适配器。
- 采集任务。
- 标准化逻辑。
- 基础统计和基础指标。
- 质量检查。
- `pub_*` 目录导出。
- 围绕现有 `<external_producer_root>` 项目的包装器。

不要放：

- 原语。
- 标签。
- 策略。
- 信号。
- 回测。
- 交易候选。

当前过渡规则：

```text
<external_producer_root> 仍然是运行中的数据生产者。
/home/ubuntu/token_parse_sys/data_foundation/provider_bridge 在需要时包装或镜像外部事实生产者的稳定契约。
```

不要把外部事实生产者的运行态 artifact 复制到新根目录。

### `stock_lobster/`（策略系统）

拥有经验数据、策略语义、信号生成、回测和观察。

放这里：

- L0-L6 层级包。
- 形态研究对象。
- 候选和审批模型。
- 观察和复盘逻辑。
- 供接口和工具使用的应用服务。

不要把源数据采集或上游数据修复逻辑放在这里。

### `workflows/`（工作流）

拥有流程编排。

用于把多个有界上下文组合成一个业务流程的入口。

推荐布局：

```text
workflows/
  definitions/
    daily_fact_data_production.yaml
    daily_snapshot_production.yaml
    daily_label_production.yaml
    daily_signal_generation.yaml
    daily_observation_review.yaml
  jobs/
    daily_fact_data_production.py
    daily_snapshot_production.py
    daily_label_production.py
    daily_signal_generation.py
    daily_observation_review.py
  runners/
    local_runner.py
    cron_runner.py
```

例行调度器应调用 `workflows/jobs/` 下的文件。

工作流作业应编排公开服务。不得把属于 `data_foundation/` 或 `stock_lobster/` 的领域规则藏进作业。

### `interfaces/`（接口）

拥有面向人和外部系统的稳定入口。

放这里：

- 暴露给用户或运维的 CLI 命令。
- 如果之后添加服务，则放 API 适配器。
- 稳定 SQL 或视图消费示例。
- 报告渲染器和导出适配器。

示例：

```text
interfaces/cli/lobster.py
interfaces/api/
interfaces/sql/
interfaces/reports/
```

接口调用应用服务和工作流。接口不拥有业务真相。

### `tools/`（工具）

拥有供 Agent、脚本和运维复用的可调用 helper。

放这里：

- 数据资产检查 helper。
- 快照构建器。
- 形态案例工具。
- 策略组合 helper。
- 回测运行器包装。
- 审批 helper。
- 观察复盘 helper。

工具规则：

- 工具是薄包装。
- 工具保留版本和 provenance。
- 工具不得静默批准任何内容。
- 工具不得在 Stock Lobster 内部生产权威事实数据。
- 工具不得成为某条业务规则唯一存在的地方。

### `configs/`（配置）

拥有版本化配置和 registry 文件。

放这里：

- 数据源配置模板。
- 数据资产配置。
- 原语 registry 文件。
- 标签 registry 文件。
- 策略配置。
- 评估口径。
- 调度定义。

secret 不放这里。

### `ops/`

拥有部署和运维。

放这里：

- crontab 条目。
- systemd 单元。
- 环境模板。
- 运维手册。
- 日志目录约定。

运行日志可以放在 `ops/logs/` 或服务器特定日志路径，但不应作为源码 artifact 提交。

## 例行组件与被动组件

使用以下拆分：

| 组件 | 例行执行？ | 位置 |
| --- | --- | --- |
| 事实数据生产 | 是 | `workflows/jobs/daily_fact_data_production.py` 包装 `data_foundation` |
| 快照生产 | 是 | `workflows/jobs/daily_snapshot_production.py` |
| 标签生产 | 是 | `workflows/jobs/daily_label_production.py` |
| 已批准策略信号运行 | 是 | `workflows/jobs/daily_signal_generation.py` |
| 观察复盘 | 是 | `workflows/jobs/daily_observation_review.py` |
| 原语函数 | 被动 | `stock_lobster/l2_primitives/` |
| 标签定义 | 被动契约，例行输出 | `stock_lobster/l3_labels/` 和 `configs/labels/` |
| StrategyDSL | 被动契约，例行输入 | `stock_lobster/l4_strategy_dsl/` 和 `configs/strategies/` |
| 回测引擎 | 被动服务，按需或调度 | `stock_lobster/l6_backtest_engine/` |
| CLI | 被动入口 | `interfaces/cli/` |
| API | 被动入口 | `interfaces/api/` |
| 共享 schema | 被动 | `shared/` |
| 通用 helper | 被动 | `tools/` |

## 公共接口规则

公共接口是外部用户或系统唯一受支持的入口。

允许的公共表面：

- `interfaces/cli/`
- `interfaces/api/`
- `interfaces/sql/`
- 调度器使用的 `workflows/jobs/`
- `data_foundation` 中已文档化的 `pub_*` 产品

不要要求外部调用方直接 import 内部层级模块。

## 调度器规则

Cron 或 systemd 只应调用稳定作业入口：

```text
/home/ubuntu/token_parse_sys/workflows/jobs/*.py
```

每个作业应该：

1. 加载调度配置。
2. 检查上游就绪状态。
3. 调用公开应用服务。
4. 写入结构化结果。
5. 失败时返回非零。
6. 保留 `run_id`。
7. 写入审计或状态记录。

过渡期间，外部事实生产者项目下的现有调度器仍然有效；但新的跨系统作业应放在 `token_parse_sys/workflows/jobs/` 下。

## 跨上下文导入规则

允许：

```text
workflows -> data_foundation public services
workflows -> stock_lobster public services
interfaces -> workflows or application services
tools -> public services
stock_lobster L1 -> stock_lobster L0
stock_lobster L2 -> stock_lobster L1
stock_lobster L3 -> stock_lobster L2
stock_lobster L4 -> stock_lobster L3
stock_lobster L5 -> stock_lobster L4
stock_lobster L6 -> stock_lobster L5/L4 through public replay contracts
```

禁止：

```text
stock_lobster -> data_foundation ingestion internals
stock_lobster L0-L6 -> stock_lobster.research
data_foundation -> stock_lobster strategy semantics
shared -> data_foundation or stock_lobster runtime code
tools -> hidden production-only business rules
interfaces -> direct database writes bypassing services
```

## 第一执行计划

按此顺序：

1. 创建 `/home/ubuntu/token_parse_sys` 和顶层目录。
2. 保持 `<external_producer_root>` 作为运行中的数据生产者。
3. 只有需要读取外部事实生产者的稳定契约时，才添加 `data_foundation/provider_bridge/`。
4. 为 `pub_*` 产品添加第一批 `configs/data_assets/` 条目。
5. 实现 Stock Lobster L0 从这些配置加载目录。
6. 实现一个 L1 `AnalysisSnapshot` 构建器。
7. 实现 `research/` 样本到候选对象。
8. 只有被动服务存在后，才添加例行工作流入口。

## 审阅清单

添加文件前回答：

- 这是事实生产、经验生产、工作流编排、外部接口，还是通用工具？
- 它是例行还是被动？
- 哪个目录拥有它？
- 它需要 registry 条目吗？
- 它需要 `run_id`、版本或审批元数据吗？
- 哪个测试证明它没有跨越边界？

如果所有权不清楚，先把它记录为候选设计，再写生产代码。
