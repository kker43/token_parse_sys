# Stock Lobster 执行计划

本计划把 `requirements.md` 和 `sys_command.md` 转化为实现顺序。它是 Codex 会话的工作地图，应在架构决策形成后持续更新。

## 当前状态

- L0-L6、研究工作流、样本回放、回测、生命周期 gate 和远程研究执行能力均已具备实现与测试。
- 当前唯一例行选股策略为 `strategy.steady_uptrend_mvp/v1`，生命周期为 `test_tracking`，不发布正式 L5 信号。
- 旧 breakout、pre-breakout、v3、v3.1、v4 和五子池策略已退出例行选股，只保留链路、因子、样本回放和研究证据。
- 当前业务策略注册表为 `configs/strategies/strategy_registry.example.json`，任何例行选股入口必须以该注册表为业务真相源。
- 技术体系中的例行任务、执行器、输入契约、回放、因子和审计能力长期保留；策略注册表只管理可替换的业务选股口径。
- 标准系统结构和模型指导记录在 `docs/standards/001-system-structure-and-model-guidance.md`。
- 数据基础集成指导记录在 `docs/standards/002-data-foundation-integration.md`。
- 远程执行布局记录在 `docs/standards/003-remote-system-execution-layout.md`。
- 宏观大类资产投研扩展的 PRD 记录在 `docs/product/001-macro-cross-asset-research-prd.md`，系统 spec 记录在 `docs/standards/010-macro-cross-asset-research-spec.md`，第一批 DataAsset 示例记录在 `configs/data_assets/macro_cross_asset_data_assets.example.json`。
- 远程项目位于 `/home/ubuntu/token_parse_sys`；MVP 先进入例行 `test_tracking`，达到生命周期门槛并经用户批准后再迁移到正式 L3-L5 生产链路。
- 当前下一步是积累例行跟踪天数、未来收益和失败案例，不扩展新的日常选股策略。

## 不可协商边界

- Stock Lobster 不生产权威事实数据。
- Stock Lobster 会生产版本化经验数据，例如形态案例、原语候选、已批准原语契约、标签定义、策略候选、评估证据、审批记录和观察记录。
- 外部数据通过已注册的 `DataAsset` 契约进入系统。
- 外部事实生产者保持外部身份；本项目构建适配器和目录，而不是合并那套代码库。
- `StrategyDSL` 不能直接引用原始价格表或成交量表。
- Agent 不能自行创建事实、已批准原语、已批准标签、已批准策略、正式信号或回测结果。
- 候选策略变为已批准、进入观察池、替换已批准版本或发布正式信号之前，必须经过用户确认。

## 从形态研究到经验生产

除 L0-L6 执行层外，Stock Lobster 还有一条生产级研究工作流。该工作流从真实股票形态样本开始，把研究证据转化为版本化经验 artifact。

参考决策：`docs/decisions/001-pattern-research-to-experience-production.md`。

核心流程：

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
-> ObservationRecord
-> ReviewFinding
-> NewCandidateVersion
```

职责：

- 研究编排负责样本案例、因子观察、候选语义、审批证据和复盘发现。
- L2 负责已批准原语定义和纯原语执行。
- L3 负责已批准标签定义和可重复的标签快照生产。
- L4 负责已批准策略 DSL 版本和候选策略 schema。
- L5 负责正式信号生产。
- L6 负责正式回测结果。

规则：

- 研究 artifact 是经验数据，不是权威事实数据。
- 候选原语、标签和策略在批准并注册前，不是生产 artifact。
- 只有已批准的层级 artifact 才允许进入定时生产。
- 每个已批准 artifact 都必须保留指向样本证据、上游 `DataAsset` 依赖、版本和 `run_id` 的链接。
- 研究编排可以协调 L0-L6，但 L0-L6 不得依赖研究编排。

## 宏观大类资产投研扩展

宏观大类资产模块用于回答黄金、石油、大宗商品、Crypto、股市、美债、中国国债等资产的趋势、异动和下钻分析问题。

该模块仍遵守现有边界：

- 外部数据源只通过 L0 `DataAsset` 契约进入系统。
- L1 生成 `MacroAnalysisSnapshot`、`AssetStateSnapshot` 和 `CrossAssetSnapshot`。
- L2/L3 生成确定性趋势、异动、跨资产一致性和反证标签。
- 研究结论必须带证据、反证、置信度分解和审阅状态。
- 宏观标签若要影响 A 股策略，只能作为已批准 L3 标签或 approved metadata 被 L4 引用。

后续实现顺序：

1. 用 `configs/data_assets/macro_cross_asset_data_assets.example.json` 扩展第一批宏观 DataAsset。
2. 为宏观快照补 L1 schema 和合成测试。
3. 实现趋势、异动、跨资产一致性和反证原语。
4. 生成宏观标签 registry 和每日简报工作流草稿。
5. 在用户审批后，再设计宏观标签到 A 股策略上下文的连接。

## 目标目录布局

第一版代码脚手架：

```text
stock_lobster/
  __init__.py
  core/
    __init__.py
    ids.py
    versioning.py
    audit.py
    errors.py
  l0_data_access/
    __init__.py
    contracts.py
    catalog.py
    repositories.py
    adapters/
      __init__.py
      external_mysql.py
  l1_analysis_snapshot/
    __init__.py
    schema.py
    builder.py
    repository.py
  l2_primitives/
    __init__.py
    registry.py
    functions.py
  l3_labels/
    __init__.py
    registry.py
    snapshot.py
    generator.py
  l4_strategy_dsl/
    __init__.py
    schema.py
    candidate_pool.py
    stage_pipeline.py
    validator.py
  l5_signal_engine/
    __init__.py
    engine.py
    ranking.py
    explanation.py
  l6_backtest_engine/
    __init__.py
    profiles.py
    engine.py
    metrics.py
    result.py
  research/
    __init__.py
    pattern_case.py
    factor_observation.py
    candidates.py
    approval.py
  app/
    __init__.py
    cli.py
configs/
  data_assets/
  labels/
  strategies/
docs/
  decisions/
  standards/
  examples/
tests/
  test_import_boundaries.py
  l0_data_access/
  l1_analysis_snapshot/
  l2_primitives/
  l3_labels/
  l4_strategy_dsl/
  l5_signal_engine/
  l6_backtest_engine/
```

初始脚手架只应包含最小模型、校验器和测试。在第一个 DataAsset 目录明确前，避免构建完整数据库 schema。

## 层级所有权

### L0 数据访问契约层（Data Access Contract Layer）

目的：

- 描述外部表、文件、API、schema、质量状态和更新频率。
- 为下游层提供安全查询契约。

初始交付物：

- `ExternalDataContract`
- `DataAsset`
- `DataAssetCatalog`
- 外部事实生产者 MySQL 适配器草稿。
- 日线、周线、月线、MA、波动率、成交额和股票基础表的目录示例。

验收：

- L0 绝不导入 L1-L6。
- 每个外部字段都有来源、类型、日期语义和质量状态。
- 不修改事实数据。

### L1 分析快照层（Analysis Snapshot Layer）

目的：

- 从 L0 契约构建可复现的分析快照。
- 记录来源依赖和查询参数。

初始交付物：

- `AnalysisSnapshot`
- `AnalysisSnapshotDependency`
- 快照构建器接口。
- 用于测试的内存 repository。

验收：

- L1 只通过公开契约对象导入 L0。
- 每个快照都有 `analysis_version`、`run_id`、`stock_code` 和 `snapshot_date`。
- 快照输出可以追溯到 DataAsset 依赖。

### L2 原语函数层（Primitive Function Layer）

目的：

- 定义作用于 `AnalysisSnapshot` 的纯函数。

初始交付物：

- `PrimitiveDefinition`
- 原语 registry。
- 第一批候选原语示例，例如基于合成测试快照的均线收敛和放量。

验收：

- 不访问外部数据。
- 没有有状态行为。
- 原语输出为 boolean 或数值 score。

### L3 标签快照层（Label Snapshot Layer）

目的：

- 从已注册原语构建确定性的版本化标签。

初始交付物：

- `LabelDefinition`
- `LabelSnapshot`
- 标签 registry。
- 标签生成器。

验收：

- 标签依赖 L2 原语结果，而不是原始数据。
- 标签快照包含 `label_version` 和 `run_id`。
- 相同输入快照能复现相同标签生成结果。

### L4 策略 DSL 层（Strategy DSL Layer）

目的：

- 定义人类可读的白盒策略规则。

初始交付物：

- `StrategyDSL` schema。
- `CandidatePoolPolicy`。
- `StagePipeline`。
- 召回、过滤、排除、评分、排序和周期结构。
- 拒绝原始数据引用的 DSL 校验器。

验收：

- DSL 只引用已批准标签字段。
- 候选池策略版本化，并可在回测中复现。
- 策略候选与已批准策略保持分离。

### L5 信号引擎层（Signal Engine Layer）

目的：

- 在标签快照上执行已批准或候选 DSL，产出排序后的信号结果。

初始交付物：

- `StrategySignal`
- 信号引擎。
- 排序引擎。
- 解释构建器。

验收：

- 正式信号只能在这里生成。
- 每条结果解释候选池进入原因、触发标签、过滤、风险提示、排名分数和排名。
- 候选策略可以运行试验信号，但不会因此变成已批准策略。

### L6 回测引擎层（Backtest Engine Layer）

目的：

- 在历史日期上复现策略运行，并生成回测结果。

初始交付物：

- `EvaluationProfile`
- 事件收益回测。
- 固定周期回测。
- 排名分桶分析。
- `BacktestResult`。

验收：

- 正式回测结果只能在这里生成。
- 候选池生成必须复现，不能近似。
- 结果包含基准、周期、样本数、收益、回撤、胜率和失败案例。

## 里程碑计划

### M0 项目控制基线

状态：草稿完成

交付物：

- `AGENTS.md`
- `PLANS.md`
- 初始目录和层级所有权计划。
- 未决决策清单。

完成标准：

- 后续会话有清楚的所有权边界。
- 第一版代码脚手架没有歧义。

### M1 工程脚手架

交付物：

- Python 包布局。
- 测试运行器。
- 导入边界测试。
- 最小核心版本和审计类型。
- 示例配置目录。

完成标准：

- 测试可以在本地运行。
- 依赖规则能阻止向上层导入。

### M2 数据资产目录

交付物：

- 共享数据产品和质量契约。
- `data_foundation/provider_bridge` 骨架。
- 确定性产品就绪检查器。
- `data_foundation/catalog_export` 导出器。
- L0 契约模型。
- 第一版外部事实生产者目录草稿。
- 表和字段元数据。
- 质量/更新元数据占位。

完成标准：

- Workflow 001 第一段代码通过测试。
- 至少一个真实外部表表示为 `DataAsset`。
- 没有业务层直接读取外部数据。

### M3 分析快照 MVP

交付物：

- L1 快照 schema。
- 依赖追踪。
- 从 L0 行构建快照的构建器。
- 合成测试。

完成标准：

- 可以为一个股票/日期从已编目的数据构建快照。
- 快照 provenance 被记录。

### M4 Primitive 和 Label MVP

交付物：

- `PatternCase`、`FactorObservation`、`PrimitiveCandidate` 和 `LabelCandidate` 的研究工作流对象。
- 原语 registry。
- 标签 registry。
- 第一版确定性标签快照生成器。

完成标准：

- 一个真实或合成形态案例可以产出候选原语和候选标签定义，并且不会自动变成已批准。
- 标签可以从相同分析快照和版本复现。

### M5 策略 DSL MVP

交付物：

- 策略 DSL schema。
- 候选池策略。
- 阶段流水线。
- DSL 校验器。
- 示例候选策略。

完成标准：

- 策略可以表达质量、趋势、精筛、介入和排序阶段。
- 校验器会拒绝原始数据引用。

### M6 Signal 和 Backtest MVP

交付物：

- 信号引擎。
- 解释输出。
- 事件收益和固定周期回测。
- 回测报告结构。

完成标准：

- 候选策略可以生成试验信号和回测报告。
- 已批准策略流程仍然受用户确认门控。

### M7 观察和复盘闭环

交付物：

- 审批状态流。
- 观察池记录。
- 未来跟踪结果。
- 周期复盘报告草稿。

完成标准：

- 已批准策略信号可以被跟踪，同时不修改历史策略定义。

## 推荐会话计划

按不重叠的文件所有权运行会话。

| 会话 | 模型 | 文件范围 | 任务 |
| --- | --- | --- | --- |
| S0 | GPT-5.5 | `AGENTS.md`, `PLANS.md`, `docs/decisions/` | 架构控制 |
| S1 | GPT-5.4-Mini | 只读或 `configs/data_assets/` | 发现外部数据契约 |
| S2 | GPT-5.5 | 包脚手架、测试 | 创建工程基础 |
| S3 | GPT-5.5 | `l0_data_access/`, `l1_analysis_snapshot/` | 数据契约和快照 |
| S4R | GPT-5.5 | `research/`, research docs | 形态研究和经验候选 |
| S4 | GPT-5.4 | `l2_primitives/`, `l3_labels/` | 原语和标签 |
| S5 | GPT-5.5 | `l4_strategy_dsl/` | DSL、候选池、流水线 |
| S6 | GPT-5.5 | `l5_signal_engine/` | 信号执行和解释 |
| S7 | GPT-5.5 | `l6_backtest_engine/` | 回测 |
| S8 | GPT-5.4 | `app/`, observation docs | 审批和观察工作流 |
| S9 | GPT-5.5 | 只审阅或窄范围修复 | 边界和质量审阅 |

## Prompt 模板

架构会话：

```text
你是 Stock Lobster 的 S0 架构控制会话。
阅读 requirements.md、sys_command.md、AGENTS.md 和 PLANS.md。
除非被要求，否则不要实现业务代码。
澄清架构决策，更新文档，并保持严格层级边界。
```

层级实现会话：

```text
你只负责 <LAYER>。
先阅读 requirements.md、sys_command.md、AGENTS.md 和 PLANS.md。
只修改 <ALLOWED PATHS> 中的文件。
不要绕过下层契约。
添加聚焦测试。
最后报告变更文件、验证、层级边界检查和未决问题。
```

审阅会话：

```text
审阅当前 Stock Lobster 工作区。
优先关注层级违规、策略/数据边界违规、缺失测试和可复现性缺口。
先用文件和行号报告发现的问题。
除非明确要求，否则不要重构。
```

## 未决决策

M1/M2 之前或期间需要确定：

- 在这个目录初始化项目 Git 仓库，还是把这些文档迁入已有仓库？
- 使用带 `pyproject.toml` 的 Python 打包，还是使用其他运行时？
- 第一版 MVP 的 registry 和 snapshot 数据存在本地文件、MySQL、SQLite，还是混合方案？
- `StrategyDSL` 表示为 YAML、JSON、数据库记录、Python 对象，还是组合形式？
- 第一个用于驱动候选策略生成的股票形态是什么？
- 第一版默认基准用哪个：沪深 300、中证 500、中证 1000、全 A 等权，还是按策略类型选择？
- 第一版用户审批使用 CLI、数据库状态、Markdown 审阅文件，还是 Web？
- 观察更新初期手动运行，还是按日调度？

## 立即下一步

推荐下一步：

1. 决定是否在这里初始化 Git。
2. 创建 M1 Python 脚手架。
3. 在添加业务逻辑前先加入导入边界测试。
4. 使用只读 S1 会话检查外部事实生产者契约，并起草第一批 `configs/data_assets/` 条目。
