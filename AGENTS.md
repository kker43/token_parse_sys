# Stock Lobster Agent 指南

本文件定义 Codex 会话在本仓库中的工作方式。除非用户明确覆盖，否则它对所有项目工作均有约束力。

## 优先阅读

修改前先阅读：

1. `requirements.md`
2. `sys_command.md`
3. `PLANS.md`
4. `docs/standards/001-system-structure-and-model-guidance.md`
5. `docs/standards/002-data-foundation-integration.md`
6. `docs/standards/003-remote-system-execution-layout.md`
7. 代码存在后，再阅读最近的相关源码和测试

如果指令冲突，按以下优先级处理：

1. 用户的最新请求
2. `sys_command.md`
3. `requirements.md`
4. `PLANS.md`
5. `docs/standards/001-system-structure-and-model-guidance.md`
6. `docs/standards/002-data-foundation-integration.md`
7. `docs/standards/003-remote-system-execution-layout.md`
8. 本文件

## 项目使命

Stock Lobster 是面向 A 股的策略研究、分析编排、信号生成、回测和观察系统。

它不生产权威市场事实数据。`<external_producer_root>` 等外部系统负责生产事实数据并暴露数据契约。Stock Lobster 消费这些契约，构建可复现的分析快照，派生确定性标签，运行白盒策略 DSL，生成信号，执行回测，并跟踪未来表现。

## 硬性架构规则

系统必须严格分层：

```text
L0 Data Access Contract Layer
L1 Analysis Snapshot Layer
L2 Primitive Function Layer
L3 Label Snapshot Layer
L4 Strategy DSL Layer
L5 Signal Engine Layer
L6 Backtest Engine Layer
```

规则：

- 下层不得依赖上层。
- 上层只能消费下层产物。
- 不允许跨层绕行。
- Stock Lobster 不得采集、清洗、修复、改写或成为权威事实数据来源。
- L0 是唯一与外部数据契约交互的层。
- L1 基于 L0 输出构建版本化 `AnalysisSnapshot` 对象。
- L2 原语只能是作用于 `AnalysisSnapshot` 的纯函数。
- L3 标签是从已注册原语派生的确定性快照。
- L4 `StrategyDSL` 只能引用已批准的 `LabelSnapshot` 字段和已批准的元数据字段。
- L5 是唯一生成 `StrategySignal` 的层。
- L6 是唯一生成 `BacktestResult` 的层。
- Agent 可以提出候选项、编排工具、解释结果和起草计划，但不能生产事实数据，也不能绕过 DSL 或回测引擎。

## 外部数据边界

初期数据访问可以适配远程 `<external_producer_root>` 项目，但不要把该仓库整体合并进来。

不要导入或复制：

- 虚拟环境
- 日志
- 运行态 tracker 文件
- 历史报告
- `old_version`
- 临时文件

优先使用适配器、目录、注册表和可复现查询契约。

做数据基础工作时，还要阅读 `docs/workflows/001-data-foundation-mvp.md`。

## 建议初始代码布局

除非后续架构决策改变，否则使用此布局：

```text
stock_lobster/
  core/
  l0_data_access/
  l1_analysis_snapshot/
  l2_primitives/
  l3_labels/
  l4_strategy_dsl/
  l5_signal_engine/
  l6_backtest_engine/
  research/
  app/
configs/
  data_assets/
  labels/
  strategies/
docs/
  decisions/
  standards/
  examples/
tests/
  l0_data_access/
  l1_analysis_snapshot/
  l2_primitives/
  l3_labels/
  l4_strategy_dsl/
  l5_signal_engine/
  l6_backtest_engine/
```

各层包可以从 `stock_lobster.core` 和更低编号层导入。L0-L6 不得导入 `stock_lobster.research` 或 `stock_lobster.app`。一旦开始实现，测试应强制检查这一点。

## 多会话工作规则

按所有权边界拆分会话，不要按模糊功能名拆分。

推荐会话：

- S0 架构控制：文档、计划、未决决策、边界。
- S1 数据契约侦察：外部表和字段发现；除非写目录草稿，否则只读。
- S2 工程脚手架：包结构、测试设置、依赖检查。
- S3 数据基础和 L0/L1：共享契约、`data_foundation` 桥接、L0 数据资产和分析快照。
- S4R 形态研究：样本案例、因子观察、候选项和经验数据审批证据。
- S4 L2/L3：原语、标签、注册表。
- S5 L4：策略 DSL、候选池策略、阶段流水线、校验器。
- S6 L5：信号执行、解释、排序。
- S7 L6：回测口径、指标、结果持久化。
- S8 观察/app：审批流、观察池、CLI/报告。
- S9 审阅：架构、依赖、测试和回归审阅。

不要让两个会话同时修改同一批文件。

## 模型使用指导

- GPT-5.5 用于架构、模糊的多步工作、DSL 设计、信号引擎、回测和最终审阅。
- GPT-5.4 用于稳定实现、测试、CLI 和常规编码。
- GPT-5.4-Mini 用于扫描、目录探索、摘要和小型辅助任务。
- GPT-5.3-Codex-Spark 只用于近乎即时的小迭代或快速本地问题。

较大的交接应遵循 `docs/standards/001-system-structure-and-model-guidance.md`。

## 实现标准

- 将改动限制在当前层或当前会话范围内。
- 相比隐式字典，优先使用显式 schema 和 registry。
- 相比 Agent 生成状态，优先使用确定性、可复现函数。
- 每个会影响策略行为的持久 artifact 都需要版本，适用时还需要 `run_id`。
- 候选策略语义应与已批准的生产策略语义分开存储。
- 保留策略晋升、进入观察池、替换已批准版本时的人类审批边界。
- 在出现具体层级用例前，不要添加大型抽象。

## 验证期望

代码存在后，每个实现会话都应运行最小相关检查，并报告已运行和未运行的内容。

预期检查类别：

- 格式化
- lint
- 变更层的单元测试
- 导入边界测试
- schema 校验测试
- 快照、标签、信号和回测的可复现性测试

如果还没有测试框架，工程脚手架会话应在业务逻辑扩展前先创建测试框架。

## 会话收尾格式

每个实现会话都应以下列格式结束：

```text
Changed:
- ...

Validated:
- ...

Layer boundary check:
- ...

Open questions:
- ...
```

收尾应简短，并基于证据。
