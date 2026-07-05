# Standard 008: Workflow Construction Standard 横向业务流程施工规范

## 1. 目的

本文档定义业务 workflow 如何把 L0-L6 串成可执行链路，同时保持层级解耦。

它回答：

```text
workflow 能做什么？
workflow 不能做什么？
不同业务链路如何复用同一套层级能力？
```

## 2. workflow 的定位

workflow 是编排层，不是事实层、标签层、策略层或回测层。

workflow 可以：

- 选择候选池来源。
- 调用各层公开服务。
- 串联 artifact。
- 记录 `run_id` 和执行证据。
- 输出缺口、候选项、报告和下一步动作。
- 为人工审批准备材料。

workflow 不可以：

- 绕过 L0 直接读取未注册事实表。
- 在 workflow 内临时计算生产 primitive 或 label。
- 在 workflow 内定义正式 `StrategyDSL` 语义后跳过 L4 校验。
- 直接生成正式 `StrategySignal` 后绕过 L5。
- 改变 L6 回测假设来适配结果。
- 自动替代用户审批，把候选策略推进观察池。

## 3. 标准 workflow 模板

新增 workflow 文档必须包含：

```text
Workflow name:
Business goal:
Owner session:
Layer path:
Inputs:
Outputs:
Allowed states:
Entry gate:
Exit gate:
Config surface:
Run artifact:
Validation:
Human approval points:
Forbidden shortcuts:
Open decisions:
```

## 4. 标准链路

Stock Lobster 的核心业务链路应优先复用同一条骨架：

```text
CandidatePoolPolicy
-> AnalysisSnapshot
-> StagePipeline
-> StrategyDSL
-> Signal Engine
-> Backtest Engine
-> Observation Tracking
```

不同业务场景只能在下列位置分歧：

- 候选池来源。
- 阶段名称。
- 阈值配置。
- 排序目标。
- 回测 profile。
- 观察频率。
- 报告视图。

不应为全市场筛选和异动观察池各建一套独立执行引擎。

## 5. workflow 类型

### 5.1 数据契约接入 workflow

目标：

```text
外部事实数据契约 -> DataAsset -> L0 -> L1 AnalysisSnapshot
```

边界：

- 可以检查外部契约和质量状态。
- 可以导出 `DataAsset` 配置。
- 不能把 Stock Lobster 变成权威事实生产者。

典型文档：

```text
docs/workflows/001-data-foundation-mvp.md
```

### 5.2 研究沉淀 workflow

目标：

```text
样本案例 -> 经验观察 -> L2/L3 建设需求 -> 候选 StrategyDSL
```

边界：

- 可以产出 `PrimitiveBuildRequirement` 和 `LabelBuildRequirement`。
- 可以生成候选策略草案。
- 不能直接批准正式 primitive、label 或策略。

典型文档：

```text
docs/workflows/002-single-stock-strategy-research-skill.md
```

### 5.3 全市场筛选 workflow

目标：

```text
全 A 候选池 -> StagePipeline -> 策略信号 -> 回测/观察
```

必须使用：

- `CandidatePoolPolicy` 记录全市场候选来源。
- L1/L3 已准出的分析和标签。
- L4 已校验的 `StrategyDSL`。
- L5 生成可解释信号。
- L6 生成可复现回测。

待建设文档：

```text
docs/workflows/003-full-market-screening.md
```

### 5.4 异动观察池 workflow

目标：

```text
异动观察池 -> StagePipeline -> 再分析 -> 回测/跟踪
```

必须记录：

- 进入观察池的规则。
- 观察池来源版本。
- 候选池快照。
- 重新分析时使用的 L1/L3/L4 版本。

关键规则：

```text
进入观察池的规则本身也是 CandidatePoolPolicy 的一部分。
```

待建设文档：

```text
docs/workflows/004-observation-pool-tracking.md
```

### 5.5 策略草案、回测和审批 workflow

目标：

```text
候选 StrategyDSL -> 自动回测 -> 人工审批 -> test_tracking 或 approved
```

必须保留：

- 策略版本。
- 依赖标签版本。
- 回测 profile。
- 回测结果。
- 审批记录。
- 进入观察池的决策。

待建设文档：

```text
docs/workflows/005-strategy-draft-backtest-approval.md
```

## 6. workflow 准入

新增或修改 workflow 前必须满足：

- 已确定业务目标。
- 已列出经过的层级。
- 已确认每层输入输出 artifact。
- 已确认哪些配置可变、哪些契约不可变。
- 已确认人工审批点。
- 已确认不会在 workflow 内绕过层级能力。

如果 workflow 需要的层级 artifact 尚未准出，应把 workflow 状态标为：

```text
design_only
research_only
blocked_by_layer_gate
```

不能伪造下游结果。

## 7. workflow 准出

workflow 可被视为可执行切片前必须满足：

- 有文档说明业务目标和层级路径。
- 有配置样例或输入样例。
- 有可重复运行的入口或明确的手动步骤。
- 有 `run_id` 或等价运行记录。
- 有最小验证。
- 失败时能定位到具体层级或契约缺口。
- 如果涉及策略升级或观察池，已保留人工审批点。

## 8. workflow 与层级的分工

| 事项 | 层级负责 | workflow 负责 |
| --- | --- | --- |
| schema 定义 | 是 | 只引用 |
| registry 状态 | 是 | 只检查和报告 |
| primitive 计算 | L2 | 调用 |
| label 派生 | L3 | 调用 |
| StrategyDSL 校验 | L4 | 调用 |
| 信号生成 | L5 | 调用 |
| 回测指标 | L6 | 调用 |
| 业务链路顺序 | 否 | 是 |
| run_id 和执行证据 | 各层输出一部分 | 汇总 |
| 人工审批材料 | 提供证据 | 汇总和呈现 |

## 9. workflow 文件所有权

workflow 会话默认可以修改：

```text
docs/workflows/
workflows/
interfaces/cli/ 中与 workflow 直接相关的入口
tests/workflows/ 或对应 workflow 测试
configs/ 中该 workflow 的样例配置
```

workflow 会话默认不应修改：

```text
stock_lobster/l0_data_access/
stock_lobster/l1_analysis_snapshot/
stock_lobster/l2_primitives/
stock_lobster/l3_labels/
stock_lobster/l4_strategy_dsl/
stock_lobster/l5_signal_engine/
stock_lobster/l6_backtest_engine/
```

如果必须修改层内代码，应拆成层建设任务，并按 `007-layer-construction-gates.md` 重新确认准入准出。

## 10. 最小验收

每条 workflow 的第一版最小验收是：

- 能说明清楚从哪里开始，到哪里结束。
- 能列出经过的层级和 artifact。
- 能明确至少一个成功路径和一个失败路径。
- 能说明人工审批点。
- 能说明当前阻塞在哪个层级或决策。

不要为了让 workflow 闭环而把未成熟的层级规则写死。
