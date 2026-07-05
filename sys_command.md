# Stock Lobster 系统契约

## 1. 架构分层（严格遵守）

L0 数据访问契约层（Data Access Contract Layer）
L1 分析快照层（Analysis Snapshot Layer）
L2 原语函数层（Primitive Function Layer）
L3 标签快照层（Label Snapshot Layer）
L4 策略 DSL 层（Strategy DSL Layer）
L5 信号引擎层（Signal Engine Layer）
L6 回测引擎层（Backtest Engine Layer）

规则：

- 下层不得依赖上层。
- 上层只能消费下层产物。
- 不允许跨层绕行。
- 本系统不生产权威事实数据。
- 所有事实数据都必须来自外部数据生产契约。

---

## 2. 核心数据资产

### 外部数据契约（ExternalDataContract）

- 描述可用的外部数据资产。
- 包含表、字段、日期格式、更新频率和质量状态。
- 由外部数据生产系统产出。
- 只能由 L0 消费。

### 分析快照（AnalysisSnapshot）

- 基于外部数据契约构建的版本化分析视图。
- 可以包含均线、ATR、相对强弱、波动率、成交量、基本面、宏观、行业等字段。
- 不是权威事实数据源。
- 必须记录外部数据依赖。

### 标签快照（LabelSnapshot）

- 确定性的形态评估结果。
- 必须版本化。
- 必须可复现。

### 策略 DSL（StrategyDSL）

- 只能引用 LabelSnapshot 字段。
- 不允许直接引用原始价格数据。

### 策略信号（StrategySignal）

- 只能由 L5 生成。

### 回测结果（BacktestResult）

- 只能由 L6 生成。

---

## 3. 原语规则（L2）

- 必须是纯函数。
- 输入：只能是 AnalysisSnapshot。
- 输出：boolean 或 score。
- 不允许保存状态。
- 不允许直接访问外部数据。

---

## 4. 标签规则（L3）

- 由原语派生。
- 必须基于快照。
- 必须包含 `label_version` 和 `run_id`。

---

## 5. 策略规则（L4）

- 只能作用于 LabelSnapshot。
- 必须确定性执行。
- 必须支持版本化。

---

## 6. Agent 规则（如果使用 L7/L8）

- Agent 不能生产事实数据。
- Agent 不能修改外部数据。
- Agent 不能成为事实来源。
- Agent 不能计算权威特征。
- Agent 不能修改原语。
- Agent 不能绕过 DSL 或回测引擎。
- Agent 可以提出候选原语、标签和策略。
- Agent 只能编排工具、数据访问、分析、解释和审阅工作流。
