# Standard 012: 课题研究模块 Spec

## 1. 目的

本文定义课题研究模块的工程契约。

该模块用于承接未成熟的投资想法、文章启发、参考文献和系统能力缺口，并把它们排期为可执行研究。

## 2. 所属边界

课题研究模块属于 research 上游的编排能力。

它可以放在：

```text
configs/research_topics/
docs/product/
docs/standards/
docs/research_reports/
```

未来如需代码实现，可放在：

```text
stock_lobster/research/topic_registry.py
workflows/jobs/research_topic_review.py
```

但 v0.1 不要求实现代码。

## 3. 核心对象

### 3.1 ResearchTopic

课题登记对象。

字段：

```text
topic_id
title
status
priority
source_type
summary
why_keep
research_questions
blocked_by
references
candidate_outputs
next_review_trigger
created_at
updated_at
```

规则：

- `topic_id` 必须稳定。
- 默认 `status = topic_backlog`。
- 默认 `priority = unranked`。
- 未排优先级前不得创建正式 research workflow。

### 3.2 ReferenceNote

参考文献记录。

字段：

```text
reference_id
source_type
title
author
url
published_at
captured_at
relevance
paraphrased_claims
claims_to_verify
counterpoints
copyright_policy
```

规则：

- 不保存全文。
- 不保存大段原文摘录。
- 只保存转述、摘要、待验证断言和反证点。
- 文献观点不能作为事实数据。

### 3.3 TopicSchedule

排期记录。

字段：

```text
priority
target_review_window
owner_session
entry_gate
exit_gate
decision
decision_reason
```

规则：

- `priority = unranked` 时不能进入主动研究。
- 排期只代表研究顺序，不代表策略判断。

### 3.4 ResearchPlan

研究计划。

字段：

```text
plan_id
topic_id
questions
required_samples
required_data_assets
candidate_l2_primitives
candidate_l3_labels
candidate_l4_strategies
validation_method
stop_conditions
```

规则：

- 计划必须写清楚缺少什么。
- 缺少事实数据时，只能登记 DataAssetRequirement，不能在本系统内生产事实。

### 3.5 ResearchOutcome

课题评审结果。

可选结果：

```text
keep_backlog
reject
research_only
data_requirement
framework_requirement
```

规则：

- `research_only` 才能进入现有样本研究或策略研究 workflow。
- `data_requirement` 应转成外部事实数据契约需求。
- `framework_requirement` 应转成系统能力待办，例如标签族、评估口径或审批流程。

## 4. 状态机

课题状态：

```text
topic_backlog
prioritized
scheduled
active_research
evidence_review
promoted_to_research_only
closed_rejected
closed_archived
```

这些状态只属于课题管理，不是 L0-L6 生产 artifact 状态。

层级 artifact 仍使用 `docs/standards/000-standards-map.md` 中的状态词。

## 5. 优先级规则

优先级：

```text
unranked
P0
P1
P2
P3
```

判断口径：

- P0：已有样本、数据和明确研究路径。
- P1：重要且相关，但缺关键样本或数据。
- P2：有启发，等待更多上下文。
- P3：长期观察。

## 6. 配置契约

配置文件建议：

```text
configs/research_topics/research_topic_registry.example.json
```

顶层结构：

```text
registry_id
version
status
intake_policy
priority_rubric
topics
```

每个 topic 必须包含：

```text
topic_id
title
status
priority
summary
why_keep
blocked_by
references
next_review_trigger
```

## 7. 晋升门

从 `topic_backlog` 晋升到 `research_only` 前必须满足：

- 已排优先级。
- 已有最小研究问题。
- 已有至少一条参考文献、样本观察或人工说明。
- 已列出阻塞项。
- 已说明需要的 DataAsset、L2/L3/L4 或系统能力。
- 用户或研究者明确允许进入研究。

## 8. 禁止事项

禁止：

- 从 topic 直接生成正式信号。
- 从参考文献直接生成事实字段。
- 未排优先级就写入样本库。
- 未经审批就注册 approved L2/L3/L4。
- 把课题排期当成交易建议。

## 9. 和现有 workflow 的连接

课题可以连接到：

```text
docs/workflows/002-single-stock-strategy-research-skill.md
docs/workflows/003-research-sample-accumulation.md
docs/workflows/004-theme-lifecycle-research.md
```

连接方式：

- topic 提供研究问题和参考文献。
- workflow 负责具体样本、候选、回测和审批。
- workflow 结果回写为 `ResearchOutcome`。

## 10. Agent 检查清单

- [ ] 是否只是课题待办，而不是策略实现。
- [ ] 是否记录了参考文献但没有复制全文。
- [ ] 是否明确了阻塞项。
- [ ] 是否保持 `priority = unranked`，除非用户明确排序。
- [ ] 是否没有触碰事实数据生产。
- [ ] 是否没有生成正式信号、回测或观察池记录。
