# Workflow 002: 个股研究策略沉淀 Skill

## 1. 目标

本文档定义“个股研究策略沉淀 skill”的第一版工程口径。

这个 skill 用于把一个给定股票、给定日期、给定研究观察，沉淀成可复用的 L2 原语、L3 标签和 L4 策略候选。它不是自由发挥的策略生成器，而是一个确定性编排 workflow。

核心输入：

```text
个股代码
研究日期
L1 AnalysisSnapshot
研究假设
候选 L2 原语
候选 L3 标签
可选 L6 回测结果
```

核心输出：

```text
PatternCase
FactorObservation
PrimitiveAssessment 或 PrimitiveBuildRequirement
LabelAssessment 或 LabelBuildRequirement
StrategyDSL
BacktestGateDecision
NextActions
```

## 2. 层级边界

### 2.1 Agent 的职责

Agent 只做编排和解释：

- 根据图形、日期、上下文提出研究假设。
- 选择需要检查的 L2 原语和 L3 标签。
- 调用确定性工具拉取 L1 快照、计算 L2、组合 L3、生成 L4。
- 汇总缺口和下一步动作。

Agent 不直接批准：

- 正式 L2 原语。
- 正式 L3 标签。
- 正式生产策略。
- 测试跟踪策略。

### 2.2 确定性工具的职责

确定性工具负责可复现结果：

- 判断某个 L2 primitive 是否已存在。
- 对已存在 L2 primitive 计算输出。
- 判断某个 L3 label 是否已存在。
- 识别缺失的 L2/L3 数据建设任务。
- 基于已存在或候选 L3 输出 L4 `StrategyDSL`。
- 基于 L6 `BacktestResult` 判断是否达到测试跟踪标准。

## 3. 本次已实现的代码入口

代码入口：

```text
stock_lobster.research.IndividualStockStrategyResearchWorkflow
```

配置样例：

```text
configs/research_workflows/single_stock_strategy_research.example.json
```

这个 workflow 接收：

- `PrimitiveRegistry`：已有 L2 原语注册表。
- `LabelRegistry`：已有 L3 标签注册表。
- `IndividualStockStrategyResearchRequest`：单个研究案例的输入。

然后输出：

- `pattern_case`：本次个股研究案例。
- `factor_observations`：从 L1 特征得到的观察。
- `primitive_assessments`：已经存在并可计算的 L2 结果。
- `label_assessments`：已经存在并可组合的 L3 结果。
- `experience_build_plan`：需要新建的 L2/L3 以及阈值校准问题。
- `strategy`：L4 策略 DSL 草案或测试跟踪策略。
- `backtest_decision`：是否满足回测准入。
- `next_actions`：后续建设动作。

## 4. L2/L3 建设判断

### 4.1 L2 已存在

当 `primitive_id` 已存在于 `PrimitiveRegistry`：

```text
workflow 会直接调用 L2 纯函数。
输出 PrimitiveAssessment。
```

这表示当前个股样本可以复用已有经验原语。

### 4.2 L2 不存在

当 `primitive_id` 不存在：

```text
workflow 不会临时硬编码判断。
workflow 输出 PrimitiveBuildRequirement。
```

`PrimitiveBuildRequirement` 会说明：

- 需要的新 primitive id。
- 所属 L2 分类。
- 提议计算逻辑。
- 需要哪些 L1 features。
- 当前缺哪些 L1 features。
- 哪些阈值需要样本校准。

### 4.3 L3 已存在

当 `label_id` 已存在，且依赖的 L2 primitive 都已经算出：

```text
workflow 输出 LabelAssessment。
该 label 可以进入 L4 策略草案。
```

### 4.4 L3 不存在

当 `label_id` 不存在：

```text
workflow 输出 LabelBuildRequirement。
```

如果其依赖 L2 已经齐全，说明 L3 只是缺注册和审批；如果依赖 L2 也缺，说明要先建设 L2。

## 5. L4 策略沉淀规则

workflow 总会生成一个 L4 `StrategyDSL`，但状态不同：

```text
存在 L2/L3 缺口 -> draft
没有 L2/L3 缺口，但没有合格回测 -> draft
没有 L2/L3 缺口，且回测合格 -> test_tracking
```

第一版 L4 策略包含两个阶段：

```text
recall_by_l3_labels
rank_by_research_confidence
```

后续可以继续扩展为：

- 召回阶段。
- 质量过滤阶段。
- 风险过滤阶段。
- 评分排序阶段。
- 组合约束阶段。

## 6. 回测准入标准

默认回测准入标准在 `BacktestAcceptancePolicy` 中定义：

```text
min_sample_size = 30
min_win_rate = 0.55
return_metric_name = annual_return
min_return_metric = 0.0
drawdown_metric_name = max_drawdown
max_abs_drawdown = 0.25
```

中文解释：

- 样本数不能太少。
- 胜率要超过最低线。
- 收益指标不能为负。
- 最大回撤绝对值不能超过阈值。

这些阈值不是最终投资标准，只是第一版测试跟踪准入门槛。后续可以按策略类型、持有周期、市场状态分层配置。

## 7. 后续开发顺序

建议下一步按这个顺序继续：

1. 接入从 MySQL published views 构建真实 `AnalysisSnapshot` 的工具入口。
2. 增加 L2 primitive registry 的 JSON 加载器。
3. 增加 L3 label registry 的 JSON 加载器。
4. 增加样本组回测任务，把多个 PatternCase 扩展为候选策略样本池。
5. 增加 observation 记录，用于跟踪 test_tracking 策略的真实召回效果。
