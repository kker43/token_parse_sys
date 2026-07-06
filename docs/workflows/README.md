# Workflows 工作流索引

## 1. 定位

`docs/workflows/` 存放横向业务流程文档。

workflow 负责把多个层级串成业务闭环，但不拥有层级内部契约。层级建设请先阅读：

```text
docs/standards/007-layer-construction-gates.md
docs/standards/008-workflow-construction-standard.md
docs/standards/009-parallel-session-delivery-standard.md
```

## 2. 已有 workflow

| 编号 | 文档 | 状态 | 说明 |
| --- | --- | --- | --- |
| 001 | `001-data-foundation-mvp.md` | v0.1 | 外部事实数据契约、DataAsset、L0/L1 接入切片 |
| 002 | `002-single-stock-strategy-research-skill.md` | v0.1 | 个股研究样本沉淀到 L2/L3/L4 候选的 workflow |
| 003 | `003-research-sample-accumulation.md` | v0.1 | 研究样本积累、覆盖门槛和扩样本检查 |
| 004 | `004-theme-lifecycle-research.md` | topic_backlog v0.1 | 把主题生命周期观点先沉淀为研究课题，排优先级后再进入研究 |

## 3. 待建设 workflow

| 编号 | 建议文档 | 目标 |
| --- | --- | --- |
| 005 | `005-full-market-screening.md` | 全 A 股票池分层筛选 |
| 006 | `006-observation-pool-tracking.md` | 异动观察池再分析和未来跟踪 |
| 007 | `007-strategy-draft-backtest-approval.md` | 候选策略、自动回测、人工审批和观察池准入 |

## 4. 新增 workflow 模板

```text
# Workflow NNN: <name>

## 1. 业务目标

## 2. 层级路径

CandidatePoolPolicy
-> AnalysisSnapshot
-> StagePipeline
-> StrategyDSL
-> Signal Engine
-> Backtest Engine
-> Observation Tracking

## 3. 输入

## 4. 输出

## 5. 准入

## 6. 准出

## 7. 配置面

## 8. 运行记录

## 9. 人工审批点

## 10. 禁止捷径

## 11. 待决策
```

## 5. 编写规则

- 先定义业务目标，再定义层级路径。
- 先引用层级 artifact，再定义 workflow 编排。
- 不在 workflow 文档里创造新的层级职责。
- 未成熟的层级能力应标记为缺口，不应在 workflow 中临时补齐。
- 涉及策略升级、观察池、正式信号时必须保留人工审批点。
