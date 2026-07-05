# Standard 007: Layer Construction Gates 层级施工准入准出

## 1. 目的

本文档定义 L0-L6 和相关支撑层的统一施工口径。

它回答：

```text
一层什么时候可以开工？
一层产物什么时候可以交给下游？
哪些行为会破坏分层边界？
```

本文档是施工级 v0.1 标准。已确定的边界必须遵守；未沉淀完的业务细节以 `TBD` 或待决策记录保留。

## 2. 总原则

- 层级建设按契约推进，不按临时代码推进。
- 下游只能消费上游已准出的 artifact。
- workflow 可以串联多个层级，但不能替代任何层级的准入准出。
- Agent 可以编排、解释、起草候选项和提出缺口，不能生产事实数据，也不能批准正式 artifact。
- Stock Lobster L0-L6 不生产权威事实数据；事实数据来自外部数据生产契约。
- 每个影响策略行为的 artifact 都应具备版本，适用时还应具备 `run_id`。

## 3. 统一状态

层级 artifact 优先使用 `000-standards-map.md` 中定义的状态词：

```text
research_only
candidate
production_candidate
approved_production
test_tracking
active_production
deprecated
```

补充规则：

- `research_only` 可以用于探索，但不能被 L5 正式信号或 L6 正式回测依赖。
- `candidate` 可以进入候选比较，但不能进入观察池。
- `production_candidate` 必须有准入证据，等待审阅或回测。
- `approved_production` 才能作为正式下游依赖。
- `test_tracking` 适用于策略和观察，不等同于正式生产信号。
- `deprecated` 不能被新增 workflow 引用。

## 4. 通用准入

任一层开始实现前，必须满足：

- 已阅读对应层标准文档。
- 已确认本次工作所属层级和文件所有权。
- 已确认输入 artifact 的状态。
- 已确认不会引入上层依赖。
- 已确认不会绕过 registry、schema 或配置契约。
- 如果需要跨层串联，必须先找到或新增 workflow 文档。

如果以上任一项不满足，本次工作只能产出：

- 缺口说明。
- 待决策记录。
- 研究态样例。
- 文档草案。

不能直接产出生产态实现。

## 5. 通用准出

任一层 artifact 交给下游前，必须满足：

- 字段、schema 或配置结构可被稳定读取。
- 版本和来源依赖可追溯。
- 失败路径可解释。
- 最小相关测试或验证已记录。
- registry 或目录已同步。
- 状态升级有证据。
- 变更没有破坏导入边界。

准出证据应写入下列位置之一：

```text
测试结果
配置 diff
registry 变更
workflow 运行记录
docs/decisions/
PR 或会话收尾说明
```

## 6. 层级准入准出矩阵

| 层级 | 准入条件 | 准出条件 | 关键测试 | 禁止事项 |
| --- | --- | --- | --- | --- |
| data_foundation | 外部事实数据契约明确，来源路径和质量状态可追溯 | 可导出 L0 可消费的 `DataAsset` 或质量状态 | contract/schema/readiness tests | 把 Stock Lobster 策略语义写入事实数据生产 |
| L0 Data Access | `DataAsset` 已注册，连接和查询字段受控 | 返回稳定行数据和查询依赖信息 | asset contract tests, adapter tests | 绕过契约读未知表，计算指标或策略 |
| L1 Analysis Snapshot | L0 输出稳定，快照字段模型已定义 | `AnalysisSnapshot` 可版本化、可复现、可追溯 | snapshot replay tests, schema tests | 成为权威事实数据源，静默改写事实 |
| L2 Primitive | L1 字段满足输入需求，原语命名和 registry 可用 | 纯函数可复现，输入输出类型稳定 | pure function tests, registry tests | 直接读取原始表，写状态，依赖 L3-L6 |
| L3 Label | L2 依赖已注册，标签 schema 已定义 | `LabelSnapshot` 可复现，可被 L4 白名单引用 | determinism tests, label schema tests | 在标签里写策略排序或信号生成 |
| L4 Strategy DSL | L3 字段批准，候选池和阶段语义明确 | `StrategyDSL` 可校验、可回测、版本锁定 | DSL validator tests, dependency tests | 引用 raw 字段，绕过 L3 或回测 |
| L5 Signal Engine | L4 策略状态允许执行，L1/L3 依赖可回放 | `StrategySignal` 可解释、可排序、可追溯 | signal generation tests, explain tests | 重新定义策略语义或直接修改策略 |
| L6 Backtest Engine | L5 信号或 L4 策略可回放，交易假设明确 | `BacktestResult` 可复现，指标口径锁定 | replay tests, metric tests | 临时改变交易假设，美化结果 |
| observation | 策略已批准或进入 `test_tracking` | `ObservationRecord` 可追踪未来表现和人工决策 | observation lifecycle tests | 自动替代用户审批 |
| research | 样本、日期、假设和使用字段清楚 | 产出候选建设需求或候选 DSL，不直接升级生产 | workflow tests, evidence checks | 把经验观察冒充事实数据 |

## 7. 层内建设模板

每个层级实现任务应先写清楚：

```text
Layer:
Scope:
Inputs:
Outputs:
Entry gate:
Exit gate:
Allowed files:
Forbidden files:
Required tests:
Open decisions:
```

示例：

```text
Layer: L3 Label Snapshot
Scope: 新增 trend_strength 标签
Inputs: approved L2 primitives, L1 AnalysisSnapshot fields
Outputs: label registry entry, deterministic label calculation
Entry gate: primitive 已注册且测试通过
Exit gate: LabelSnapshot 字段可被 L4 白名单引用
Allowed files: stock_lobster/l3_labels/, configs/labels/, tests/l3_labels/
Forbidden files: stock_lobster/l4_strategy_dsl/, workflows/jobs/production*
Required tests: label determinism, registry schema
Open decisions: 阈值是否按行业分层
```

## 8. 跨层依赖规则

允许：

```text
L1 -> L0
L2 -> L1
L3 -> L2, L1
L4 -> L3
L5 -> L4, L3, L1
L6 -> L5, L4
workflows -> 各层公开服务
research -> 各层公开服务
app/interfaces -> workflows 或公开应用服务
```

禁止：

```text
L0 -> L1-L6
L1 -> L2-L6
L2 -> L3-L6
L3 -> L4-L6
L4 -> L5-L6
L0-L6 -> stock_lobster.research
L0-L6 -> stock_lobster.app
L4/L5/L6 -> 外部事实数据表
Agent -> 事实数据生产或正式审批
```

## 9. 准入失败处理

如果准入失败，应按类型处理：

| 失败类型 | 处理方式 |
| --- | --- |
| 上游 artifact 缺失 | 输出 BuildRequirement 或 DataAssetRequirement |
| schema 不稳定 | 记录待决策，不进入生产实现 |
| 样本不足 | 保持 `research_only` 或 `candidate` |
| 回测证据不足 | 保持 `draft` 或 `production_candidate` |
| 跨层依赖不清 | 新增或更新 workflow 文档 |
| 人工审批缺失 | 不进入观察池，不发布正式信号 |

## 10. 会话收尾要求

实现会话必须按 `AGENTS.md` 收尾格式报告：

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

其中 `Layer boundary check` 必须明确说明：

- 本次修改属于哪些层。
- 是否新增跨层 workflow。
- 是否触碰了事实数据生产边界。
- 是否有未满足的准入或准出条件。
