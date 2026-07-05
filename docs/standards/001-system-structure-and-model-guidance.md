# Standard 001：系统结构和模型指导

## 目的

本标准定义 Stock Lobster 的目标项目结构、工作流边界、工具边界和模型选择规则。

后续 Codex 或 GPT 会话在实现涉及项目结构、工作流、研究生产、策略生产或例行任务的功能前，应先阅读本文档。

## 核心判断

Stock Lobster 应构建为一个大型系统，但内部按独立有界上下文拆分：

```text
data_foundation
-> shared_contracts
-> stock_lobster
-> workflows
-> tools
-> skills
```

系统不应变成一个扁平包，让策略代码直接读取采集器内部实现。更大的项目可以包含数据基础能力，但 Stock Lobster 必须通过契约和已注册资产来消费事实数据。

## 主生产链路

主链路为：

```text
Factual Data
-> DataAsset Contract
-> AnalysisSnapshot
-> Experience Data
-> Strategy Composition
-> Signal Generation
-> Backtest Analysis
-> Observation Tracking
-> Routine Optimization
```

层级映射：

| 链路步骤 | 所有者 |
| --- | --- |
| 事实数据生产 | `data_foundation` |
| 字段 schema 和资产契约 | `shared_contracts` 和 L0 |
| 分析快照 | L1 |
| 样本研究和经验候选 | `stock_lobster.research` |
| 已批准原语 | L2 |
| 已批准标签和标签快照 | L3 |
| 策略组合 | L4 |
| 正式信号 | L5 |
| 正式回测 | L6 |
| 观察和优化 | `observation` 或 `app` 工作流区域 |

## 大型项目目标布局

如果仓库演进为大型项目，使用以下形态：

```text
token_parse_sys/
  shared/
    contracts/
    schemas/
    calendar/

  data_foundation/
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
    fact_data_production/
    snapshot_production/
    pattern_research/
    strategy_construction/
    backtest_evaluation/
    routine_optimization/

  tools/
    data_asset_tools/
    snapshot_tools/
    research_tools/
    strategy_tools/
    backtest_tools/
    approval_tools/
    observation_tools/

  configs/
    data_sources/
    data_assets/
    primitives/
    labels/
    strategies/
    evaluation_profiles/
    schedules/

  docs/
    decisions/
    standards/
    workflows/
    examples/
    data_contracts/
```

当前仓库可以逐步朝该结构演进。除非下一步实现确实需要该边界，否则不要为了匹配目标形态而移动文件。

## 有界上下文规则

### `data_foundation`（数据基础）

拥有事实数据生产。

允许输出：

- 原始和标准化市场数据。
- 复权价格。
- 成交量和成交额事实。
- 移动平均。
- 波动率和 ATR。
- 区间高低点统计。
- 股票、行业、概念和交易日历元数据。
- 数据质量状态。
- 已导出的 `DataAsset` 目录。

不允许输出：

- 策略含义。
- 买入/卖出信号。
- 已批准原语。
- 已批准标签。
- 生产策略决策。

### `shared/contracts`（共享契约）

拥有跨上下文契约。

示例：

- 字段 schema。
- 资产标识符。
- 日期和证券代码约定。
- 质量状态词汇。
- 版本和 run id 约定。

契约必须足够稳定，使 Stock Lobster 能在上游生产代码变化后仍可复现历史分析。

### `stock_lobster`（策略系统）

拥有经验数据、策略语义、信号生成、回测和观察。

Stock Lobster 可以创建：

- `PatternCase`
- `FactorObservation`
- `PrimitiveCandidate`
- 已批准的 `PrimitiveDefinition`
- `LabelCandidate`
- 已批准的 `LabelDefinition`
- `LabelSnapshot`
- `StrategyCandidate`
- 已批准的 `StrategyDSL`
- `StrategySignal`
- `BacktestResult`
- `ApprovalDecision`
- `ObservationRecord`
- `ReviewFinding`

Stock Lobster 不得创建权威事实数据。

### `workflows`（工作流）

拥有可执行流程编排。

工作流调用有界上下文的公开 API。不得把应该放在层级包或 registry 中的业务逻辑藏进工作流。

### `tools`（工具）

拥有可复用调用能力。

工具应是稳定应用服务的薄包装。它们不应成为策略事实来源。

### `skills`（技能）

拥有 Agent playbook。

Skill 描述 Codex/GPT 会话应该如何执行可重复工作流。它们不应包含生产业务逻辑。

## 工作流拆分

使用独立工作流。不要把所有事情压成一个巨大工作流。

### W1 事实数据生产

```text
数据源
-> 采集
-> 标准化
-> 指标生产
-> 质量检查
-> DataAsset 目录导出
```

输出：事实数据表/文件和 `DataAsset` 契约。

### W2 快照生产

```text
DataAsset
-> 查询契约
-> AnalysisSnapshot
-> 快照依赖记录
```

输出：可复现的 L1 快照。

### W3 从形态研究到经验生产

```text
PatternCase
-> FactorObservation
-> PrimitiveCandidate
-> LabelCandidate
-> StrategyCandidate
-> EvaluationProfile
-> BacktestEvidence
-> ApprovalDecision
-> RegisteredArtifact or ScheduledProduction
```

输出：已批准或已归档的经验 artifact。

### W4 策略构建

```text
已批准标签字段
-> CandidatePoolPolicy
-> StagePipeline
-> StrategyCandidate
-> StrategyDSL
-> ApprovalDecision
```

输出：版本化 L4 策略定义。

### W5 回测评估

```text
StrategyDSL
-> EvaluationProfile
-> 历史信号重放
-> BacktestResult
-> FailureCase
-> ReviewFinding
```

输出：正式 L6 证据。

### W6 例行优化

```text
定时标签生产
-> 已批准策略运行
-> 信号生成
-> 观察更新
-> 周期复盘
-> 优化候选
```

输出：观察记录和新的候选版本。

## Skill 策略

不要为整个系统构建一个巨大 skill。

使用一个轻量路由 skill 加上聚焦的工作流 skill：

```text
stock-lobster-router
stock-lobster-data-foundation
stock-lobster-pattern-research
stock-lobster-strategy-construction
stock-lobster-backtest-review
stock-lobster-routine-optimization
stock-lobster-architecture-review
```

路由 skill 只负责判断适用哪个工作流 skill。

每个工作流 skill 应说明：

- 何时使用。
- 需要先读哪些文件和文档。
- 允许的文件范围。
- 必需工具或 CLI 命令。
- 必需 artifact。
- 审批门。
- 验证命令。
- 会话收尾格式。

## 工具策略

将工具构建为小型可复用能力，不要做成隐藏策略引擎。

推荐工具组：

```text
DataAssetTool
SnapshotBuilderTool
PatternCaseTool
FactorObservationTool
PrimitiveCandidateTool
LabelCandidateTool
StrategyComposerTool
BacktestRunnerTool
FailureAnalyzerTool
ApprovalTool
ScheduleTool
ObservationReviewTool
```

工具规则：

- 工具通过公开应用服务读写。
- 工具保留版本、来源和 run id。
- 工具不得静默批准候选项。
- 工具不得在 Stock Lobster 内部创建事实数据。
- 工具必须让输入和输出 artifact 可检查。

## 模型选择标准

编码可以切换模型。根据风险、模糊度和范围选择模型。

| 模型 | 适合 | 避免用于 |
| --- | --- | --- |
| GPT-5.5 | 架构、边界、schema 设计、困难的多层代码、DSL、回测逻辑、最终审阅 | 琐碎扫描 |
| GPT-5.4 | 常规实现、测试、CLI、配置读取器、稳定层级工作 | 重大且模糊的架构决策 |
| GPT-5.4-Mini | 仓库扫描、表/目录发现、摘要、小型配置编辑、重复测试 | 最终策略语义或复杂重构 |
| GPT-5.3-Codex-Spark | 快速问题、极小本地编辑、单个窄问题的快速迭代 | 持久架构、大型变更、生产语义 |

默认规则：

```text
用 GPT-5.5 做设计。
用 GPT-5.4 实现稳定模块。
用 GPT-5.4-Mini 扫描和起草。
只在快速小循环中使用 Codex-Spark。
用 GPT-5.5 审阅重要变更。
```

## 模型交接规则

切换模型时，包含交接说明：

```text
Goal:
Allowed files:
Must read:
Layer boundary:
Artifacts to produce:
Validation:
Open questions:
```

实现会话始终包含：

- 目标工作流。
- 层级或有界上下文。
- 精确允许目录。
- 要运行的测试。
- 审批门。

## 实现顺序

推荐顺序：

1. 保留当前规划基线和导入边界测试。
2. 只在需要时添加 `shared/contracts` 或等价契约模型。
3. 从现有事实表构建第一版 L0 `DataAsset` 目录。
4. 构建第一版 L1 `AnalysisSnapshot`。
5. 添加 `research/` 工作流对象，用于形态样本分析。
6. 用一个形态家族起草原语和标签候选。
7. 批准一个很小的原语和一个很小的标签。
8. 构建一个候选 `StrategyDSL`。
9. 运行一次正式回测。
10. 在第一个策略闭环可复现后，再添加观察和例行优化。

## 后续模型不得做的事

- 不要把事实生产逻辑移入 L2-L6。
- 不要让策略 DSL 直接读取原始价格。
- 不要让 `data_foundation` 输出买入/卖出语义。
- 不要自动批准候选项。
- 不要把生产逻辑埋在 skill 中。
- 不要把核心业务规则只放在工具包装器里。
- 在出现一个端到端形态案例前，不要添加宽泛抽象。

## 新代码的最低完成标准

任何新的面向生产代码都必须回答：

- 它由哪个有界上下文拥有？
- 哪个工作流使用它？
- 它属于哪个层或 registry？
- 它生产或消费哪个 artifact 版本？
- 哪些测试证明它没有违反导入边界？
- 投入生产前需要哪种用户审批？

如果无法回答这些问题，应先把工作保留为研究证据或候选 artifact，而不是注册为生产行为。
