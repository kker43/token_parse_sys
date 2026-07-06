# Workflow 004: 主题生命周期研究

## 1. 业务目标

把外部研究观点、文章或人工复盘中的“投资哲学”先转成可保存、可排优先级、可拒绝的研究课题。

默认状态是 `topic_backlog`，不是 `research_only`。只有经过课题研究模块的优先级评审后，才进入后续 research workflow。

通用课题研究模块定义见：

```text
docs/product/002-research-topic-module-prd.md
docs/standards/012-research-topic-module-spec.md
configs/research_topics/research_topic_registry.example.json
```

本 workflow 的第一版样例是：

```text
AI/科技交易从 buy everything beta
-> 进入拥挤消化和业绩验证
-> 再筛选质量兑现和二阶扩散机会
```

该 workflow 不直接产生正式买入、卖出、观察池准入、回测任务或生产信号。

## 2. 层级路径

```text
ResearchTopic
-> ReferenceNote
-> PriorityReview
-> research_only workflow activation
```

只有排优先级后，才允许进入：

```text
PatternCase
-> FactorObservation
-> PrimitiveBuildRequirement
-> LabelBuildRequirement
-> CandidatePoolPolicy
-> StagePipeline
-> StrategyCandidate draft
```

只有当缺失的 DataAsset、L2 原语、L3 标签和 L6 回测证据补齐后，更后续版本才能进入：

```text
StrategyDSL candidate
-> BacktestEvidence
-> ApprovalDecision
-> test_tracking
```

## 3. 输入

- 外部研究观点或文章链接。
- 研究者对主题生命周期的中文解释。
- 明确的市场和主题范围，例如 `CN_A`、AI、半导体、算力、电力设备、机器人。
- 可复现的候选池来源；如果暂时没有，只能记录为候选池缺口，不能直接进入研究执行。

课题登记配置：

```text
configs/research_topics/research_topic_registry.example.json
```

单个课题草案配置：

```text
configs/research_workflows/theme_lifecycle_ai_decrowding.example.json
```

## 4. 输出

`topic_backlog` 阶段只允许输出：

- `ResearchTopic`：课题标题、来源、摘要、保留原因和阻塞项。
- `ReferenceNote`：参考文献摘要、待验证断言和反证点。
- `BacklogItem`：状态、未排序优先级、后续触发条件。

排优先级并激活后，才允许输出：

- `PatternCase`：观点来源、日期、主题假设和非信号声明。
- `FactorObservation`：对已有 L1 字段或人工备注的解释。
- `PrimitiveBuildRequirement`：需要建设或复用的 L2 原语。
- `LabelBuildRequirement`：需要建设或复用的 L3 标签。
- `CandidatePoolPolicy` 草案。
- `StagePipeline` 草案。
- `StrategyCandidate draft`。

禁止输出：

- 未排优先级前的 `PatternCase` 或 `StrategyCandidate`。
- 正式 `StrategySignal`。
- 用于晋升的正式 `BacktestResult`。
- 自动观察池准入。
- 事实数据生产任务。

## 5. 准入

进入本 workflow 前必须满足：

- 明确这是一条 `topic_backlog` 课题记录。
- 文章或观点只能作为研究证据，不能作为事实来源。
- 候选池来源、样本日期和主题范围必须写清楚。
- 缺失数据必须登记为缺口，不能由 Agent 临时编造。

如果题材成员、资金流、capex 或订单数据没有稳定 DataAsset，只能记录为 `missing_inputs`。

## 6. 准出

`topic_backlog` 阶段的准出只代表“课题已被保存，未来可以排优先级”，不代表可以继续施工。

待办准出最低要求：

- 有 `topic_id`、标题、来源、摘要和保留原因。
- 如果有参考文献，必须只记录摘要和转述，不保存全文。
- 写清楚阻塞项，例如样本、DataAsset、指标口径或人工审批缺失。
- 标记 `priority = unranked`，除非用户明确排优先级。
- 不能触发样本库写入、回测或 registry 变更。

激活为 `research_only` 后，准出最低要求：

- 每个候选 L2 原语都能归入 `docs/standards/004-experience-primitive-label-standard.md` 的分类。
- 每个候选 L3 标签都不表达买卖动作。
- `CandidatePoolPolicy` 说明 as-of 和回放要求。
- `StagePipeline` 明确哪些阶段只是观察，哪些阶段未来可能过滤或排序。
- 对缺失 DataAsset 写明目标层级和当前状态。

## 7. 配置面

主题生命周期配置应包含：

```text
topic_id
status
priority
summary
why_keep
blocked_by
references
next_review_trigger
```

激活后的主题生命周期配置应包含：

```text
source_research_case
candidate_pool_policy
stage_pipeline
artifact_plan
next_data_requirements
```

其中 `stage_pipeline` 建议拆成：

- 主题归属。
- 去拥挤风险。
- 质量和执行验证。
- 财报或订单验证窗口。
- 二阶扩散排序。

## 8. 运行记录

第一阶段只做待办登记。

后续如果排优先级并进入 research_only，有样本库时再把正负样本放入：

```text
configs/research_samples/
```

报告放入：

```text
docs/research_reports/
```

## 9. 人工审批点

需要人工确认的点：

- 这篇文章或观点是否值得从 `topic_backlog` 升级为 `research_only`。
- 它相对其它 idea 的优先级。
- 是否值得进入样本库。
- 主题候选池是否合理。
- 哪些缺口值得补 DataAsset 或 L2/L3。
- 是否允许把 `topic_backlog` 升级为 `research_only`。
- 是否允许把 `research_only` 升级为 `candidate`。
- 回测通过后是否允许进入 `test_tracking`。

## 10. 禁止捷径

- 不允许把文章观点直接写成 `StrategySignal`。
- 不允许未排优先级就创建正式研究 workflow 任务。
- 不允许让 Agent 根据文章直接生产事实数据。
- 不允许把人工主题判断伪装成 L0/L1 事实字段。
- 不允许 L4 直接引用原始行情或外部文章文本。
- 不允许在验证窗口前把“等待确认”改写成“买入确认”。

## 11. 待决策

- 新 idea 的默认记录格式是否需要进一步抽象成脚本或 CLI。
- A 股 AI/半导体/算力/机器人/电力设备的主题成员 DataAsset 由哪个外部契约提供。
- 拥挤度先用哪些可复现代理指标。
- capex、订单、财报预期是否进入 L0/L1，还是长期停留在人工研究备注。
- 主题生命周期标签是否作为宏观/行业上下文标签，还是作为策略专属研究标签。
