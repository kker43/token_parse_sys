# Standard 009: Parallel Session Delivery Standard 并行会话交付规范

## 1. 目的

本文档定义多个 Codex 会话或多人并行建设时的分工、文件所有权和交付规则。

它回答：

```text
谁能改什么？
哪些任务可以并行？
什么时候必须串行？
如何避免 workflow 为了跑通而打穿层级边界？
```

## 2. 分工原则

- 按所有权边界拆分会话，不按模糊功能名拆分。
- 层级会话负责层内契约、代码、测试和 registry。
- workflow 会话负责跨层编排、样例、运行证据和业务闭环。
- 架构控制会话负责标准、计划、未决决策和边界变更。
- 审阅会话负责导入边界、准入准出、测试缺口和回归风险。

## 3. 推荐会话类型

| 会话 | 职责 | 默认可改 |
| --- | --- | --- |
| S0 架构控制 | 标准、计划、决策、边界 | `docs/standards/`, `docs/decisions/`, `PLANS.md`, `requirements.md`, `sys_command.md` |
| S1 数据契约侦察 | 外部表、字段、质量状态发现 | 只读；必要时写 `docs/` 草稿 |
| S2 工程脚手架 | 包结构、测试框架、导入边界 | `stock_lobster/` 空包、`tests/`, `pyproject` 类配置 |
| S3 数据基础和 L0/L1 | `DataAsset`、L0、L1、快照 | `data_foundation/`, `stock_lobster/l0_*`, `stock_lobster/l1_*`, 对应测试和配置 |
| S4R 形态研究 | 样本、经验观察、候选缺口 | `stock_lobster/research/`, `docs/examples/`, `configs/research*`, 对应 workflow |
| S4 L2/L3 | 原语、标签、registry | `stock_lobster/l2_*`, `stock_lobster/l3_*`, `configs/primitives/`, `configs/labels/` |
| S5 L4 | DSL、候选池、阶段流水线 | `stock_lobster/l4_*`, `configs/strategies/` |
| S6 L5 | 信号执行、解释、排序 | `stock_lobster/l5_*`, signal configs/tests |
| S7 L6 | 回测口径、指标、结果 | `stock_lobster/l6_*`, backtest configs/tests |
| S8 观察/app | 审批、观察池、CLI/报告 | `stock_lobster/app/`, `interfaces/`, `workflows/` |
| S9 审阅 | 架构、依赖、测试、回归 | 默认只读；修复需按对应层所有权拆分 |

## 4. 可以并行的工作

通常可以并行：

- S0 文档标准与 S1 只读侦察。
- S2 脚手架与 S0 标准细化。
- S4R 研究样本与 S3 L0/L1 建设，前提是研究只使用已声明的样例或明确标记缺口。
- S4 L2/L3 与 S5 L4 设计文档，前提是 L4 不依赖未批准字段做生产实现。
- S6/L5 设计与 S7/L6 交易假设文档，前提是不写正式执行逻辑。

## 5. 必须串行或设门禁的工作

必须等待上游准出的情况：

- L1 快照 schema 未定时，不应实现正式 L2/L3。
- L2 primitive 未注册时，不应把 L3 标签升级为生产。
- L3 字段未批准时，不应让 L4 `StrategyDSL` 正式依赖。
- L4 策略未校验时，不应由 L5 生成正式信号。
- L5 信号不可回放时，不应由 L6 生成正式回测。
- L6 回测未达准入时，不应进入观察池或升级策略状态。
- 用户未确认时，不应发布正式信号、替换已批准策略或进入观察池。

## 6. 文件冲突规则

同一时间不应让两个会话修改同一批文件。

如果发现目标文件已有未提交修改：

- 先判断是否属于当前任务。
- 如果是他人或其他会话的相关修改，读懂后在其基础上追加，不回滚。
- 如果是不相关修改，保持不动。
- 如果无法判断，停止修改该文件，改写新增文档或向用户说明阻塞。

禁止：

- 为了清理工作区执行破坏性回滚。
- 把无关格式化混进当前交付。
- 在 workflow 会话里顺手改层级核心 schema。
- 在层级会话里顺手改业务 workflow 决策。

## 7. 交付切片

每个会话应交付一个清楚切片：

```text
标准切片：新增或更新施工规范，不写业务代码。
层级切片：一个层级的 schema/code/test/registry 同步变更。
workflow 切片：一条业务链路的编排、样例和验收。
修复切片：一个明确 bug 或测试失败的最小修复。
审阅切片：发现项、风险、测试缺口和建议拆分。
```

不要在一个切片里同时完成：

- 大范围标准变更。
- 多层核心实现。
- workflow 编排。
- 生产晋升。
- 观察池审批。

这些应拆为多个顺序明确的会话。

## 8. 交接记录

较大交接应写清楚：

```text
Scope:
Touched files:
Layer ownership:
Workflow ownership:
Completed gates:
Blocked gates:
Tests run:
Tests not run:
Next session should:
Do not touch:
```

如果交接给另一个会话，应优先引用：

- 本层标准。
- 对应 workflow 文档。
- 相关 decision。
- 当前 artifact 状态。

## 9. 并行建设看板

建议在 `PLANS.md` 或临时交接说明中维护：

| Work item | Owner session | Layer/workflow | Status | Blocks | Allowed files |
| --- | --- | --- | --- | --- | --- |
| L0 DataAsset catalog | S3 | L0 | candidate | external contract | `configs/data_assets/`, `stock_lobster/l0_data_access/` |
| L3 trend labels | S4 | L3 | blocked_by_L2 | primitive registry | `stock_lobster/l3_labels/`, `configs/labels/` |
| full-market screening | S5/S8 | workflow | design_only | L4/L5 | `docs/workflows/003-*` |

## 10. 审阅门禁

进入下一阶段前，S9 或架构控制会话应检查：

- 是否有跨层反向导入。
- 是否有 workflow 内联层级逻辑。
- 是否有未批准字段进入策略。
- 是否有 Agent 或脚本生产事实数据。
- 是否有策略绕过回测或人工审批。
- 是否有 registry、配置、测试不同步。
- 是否有旧状态词或自造同义状态。

发现问题时，优先退回到对应层级或 workflow 会话修复。
