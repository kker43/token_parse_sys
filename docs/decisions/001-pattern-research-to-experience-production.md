# ADR 001：从形态研究到经验数据生产

## 状态

已接受草稿。

## 背景

上游系统只应提供事实数据，例如市场价格、成交量、派生事实指标、交易日历、股票元数据、行业元数据和数据质量状态。

在早期阶段，系统中可能几乎没有研究派生或经验派生数据。因此 Stock Lobster 需要一条生产级研究工作流：从真实股票形态样本开始，关联可观察因子，提炼原语定义，构建标签，评估策略组合，然后把可重复生产调度起来，或把计算契约注册到正确层级。

这不会改变硬性边界：Stock Lobster 不得生产权威事实数据。

## 决策

Stock Lobster 拥有经验数据生产。

经验数据指从事实数据派生出的版本化研究和策略 artifact，而不是事实数据本身。示例包括：

- 形态案例和形态群组。
- 与形态样本绑定的因子观察。
- 原语候选。
- 已批准原语定义。
- 标签候选。
- 已批准标签定义和标签快照。
- 策略候选。
- 评估口径。
- 回测证据。
- 生产审批记录。
- 观察和复盘记录。

主工作流为：

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

## 层级放置

经验 artifact 必须按职责放置：

| Artifact | 层级或区域 | 规则 |
| --- | --- | --- |
| `PatternCase` | 研究编排 | 样本证据，不是事实来源 |
| `FactorObservation` | 研究编排 | 引用 L1 字段和来源 DataAsset |
| `PrimitiveCandidate` | 研究编排 | 提议的 L2 契约，不是可执行生产逻辑 |
| 已批准 `PrimitiveDefinition` | L2 | 只能是作用于 `AnalysisSnapshot` 的纯函数 |
| `LabelCandidate` | 研究编排 | 提议的 L3 契约 |
| 已批准 `LabelDefinition` | L3 | 从 L2 原语输出派生的确定性标签 |
| `LabelSnapshot` | L3 | 可重复的语义生产输出 |
| `StrategyCandidate` | L4 | 候选 DSL，不是已批准生产策略 |
| 已批准 `StrategyDSL` | L4 | 白盒版本化策略定义 |
| `StrategySignal` | L5 | 正式信号输出 |
| `BacktestResult` | L6 | 正式评估输出 |
| `ObservationRecord` | 观察工作流 | 未来跟踪证据 |

研究编排可以协调下层，但 L0-L6 不得依赖研究编排模块。

## 生产模式

每个研究派生 artifact 必须选择三种结果之一：

1. 仅作为研究证据归档。
2. 将计算契约注册到正确层级。
3. 为已批准的层级 artifact 调度可重复生产。

示例：

- 解释某只股票为什么有趣的样本笔记保留为 `PatternCase`。
- 可复用纯计算成为 L2 `PrimitiveDefinition`。
- 确定性语义字段成为 L3 `LabelDefinition`，并调度 `LabelSnapshot` 生产。
- 白盒选股配方成为 L4 `StrategyDSL`。
- 已验证候选策略可以批准用于 L5 信号生成和 L6 回测。

## 审批边界

系统可以自动起草：

- 形态案例。
- 因子观察。
- 原语候选。
- 标签候选。
- 策略候选。
- 评估建议。
- 回测证据。
- 复盘发现。

系统不得静默批准：

- 正式原语。
- 正式标签。
- 生产策略版本。
- 进入观察池。
- 正式信号发布。
- 替换已批准策略版本。

审批必须记录审批人、审批时间、证据集，以及被批准的精确版本。

## 与上游数据生产对齐

上游事实数据项目通过契约与 Stock Lobster 对齐，而不是通过共享策略代码对齐。

必需链接：

- `DataAsset` id 和版本。
- 字段 schema 和字段语义。
- 数据质量状态。
- `AnalysisSnapshot` 版本。
- 原语版本。
- 标签版本。
- 策略版本。
- 评估口径版本。
- run id。

这让已批准策略可以同时解释：

- 它使用了哪些上游事实数据。
- 哪些 Stock Lobster 经验 artifact 把这些事实转化为策略语义。

## 影响

收益：

- 真实样本驱动原语和标签，而不是抽象猜测。
- 经验生产保持可复现和可审计。
- 上游数据生产保持干净且事实化。
- 策略语义可以通过显式版本演进。
- 调度标签或策略生产时，可以追溯到研究案例。

代价：

- 需要更多 registry 和审批对象。
- 早期研究流程比直接硬编码策略更慢。
- 样本质量很重要，弱样本必须保留为研究证据，而不是批准为层级契约。

## 第一实现含义

添加大量原语前，先实现一个小型研究工作流模型：

```text
PatternCase
FactorObservation
PrimitiveCandidate
LabelCandidate
StrategyCandidate
ApprovalDecision
```

然后使用一个真实形态家族作为第一个端到端测试案例。第一个形态家族应足够小，便于人工检查，同时足够丰富，可以覆盖 L1-L6。
