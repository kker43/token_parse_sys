# Research Topic Module PRD v0.1

## 1. 产品定位

课题研究模块用于管理尚未进入正式策略研究链路的想法、课题和参考文献。

它位于 `stock_lobster.research` 的上游：

```text
Idea / Reference
-> ResearchTopic
-> TopicSchedule
-> LiteratureNote
-> ResearchPlan
-> ResearchOutcome
-> research_only workflow
```

它解决的问题不是“马上生成策略”，而是把分散的文章、观点、样本灵感和系统能力缺口沉淀成可排期、可复盘、可晋升或可拒绝的研究课题。

## 2. 不做什么

课题研究模块不做：

- 不生产权威事实数据。
- 不直接生成 `StrategySignal`。
- 不直接生成正式 `BacktestResult`。
- 不直接注册 approved L2/L3/L4 artifact。
- 不把文章观点当成事实字段。
- 不绕过人工审批进入观察池或生产策略。

## 3. 目标用户

主要用户是策略研究者和 Codex/Agent 会话。

典型输入包括：

- 新文章、新研报、新观点。
- 用户临时想到的策略方向。
- 已有策略运行中的失败案例。
- 样本复盘中发现的新形态。
- 系统能力缺口，例如题材数据、资金流、财报预期、宏观上下文。

## 4. 核心场景

### 4.1 记录新想法

用户提出一个未成熟想法时，系统先登记为 `ResearchTopic`，而不是直接创建策略。

最低记录：

- topic_id
- title
- source_type
- summary
- why_keep
- blocked_by
- priority
- status

### 4.2 绑定参考文献

每个课题可以绑定多条 `ReferenceNote`。

参考文献只保存必要元数据和摘要，不保存大段原文：

- 标题、作者、链接、发布日期。
- 核心观点的转述。
- 与课题的关系。
- 需要验证的断言。
- 不确定性和反证点。

### 4.3 排期研究

课题进入排期前必须有优先级。

优先级不是收益判断，而是研究投入顺序：

| 优先级 | 含义 |
| --- | --- |
| P0 | 已有样本和数据，可立刻进入 research_only workflow |
| P1 | 重要且与当前策略方向强相关，但缺少关键输入 |
| P2 | 有启发，暂存等待更多样本或数据 |
| P3 | 长期观察，不主动推进 |

### 4.4 转成研究计划

被排期的课题必须拆成研究计划：

- 要回答的问题。
- 需要的 DataAsset 或人工样本。
- 候选 L2/L3/L4 方向。
- 正反样本要求。
- 验收口径。
- 不推进条件。

### 4.5 产出和晋升

课题完成后只能产出以下结果之一：

- `keep_backlog`：继续保留，证据不足。
- `reject`：明确不做。
- `research_only`：进入样本研究或主题研究 workflow。
- `data_requirement`：先补外部数据契约。
- `framework_requirement`：补系统能力，例如标签族、评估口径、审批流程。

## 5. 和现有系统的关系

课题研究模块不替代现有 research workflow。

关系如下：

```text
ResearchTopic
-> PriorityReview
-> ResearchPlan
-> PatternCase / FactorObservation / PrimitiveBuildRequirement
-> LabelBuildRequirement / StrategyCandidate
```

只有进入 `research_only` 后，才允许使用现有 `stock_lobster.research` 对象。

## 6. 初始交付

v0.1 只交付文档和配置契约：

- PRD：本文档。
- Spec：`docs/standards/012-research-topic-module-spec.md`。
- 配置样例：`configs/research_topics/research_topic_registry.example.json`。

不在 v0.1 中实现 CLI、数据库表或前端。

## 7. 成功标准

v0.1 成功标准：

- 新想法可以被稳定记录，不丢失上下文。
- 参考文献可以绑定到课题，但不会污染事实层。
- 每个课题都有优先级、阻塞项和下一次评审触发条件。
- 课题必须经过人工排期后，才能进入 `research_only`。
- 所有晋升路径都保留 L0-L6 边界和审批边界。
