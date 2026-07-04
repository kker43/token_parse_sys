# Standard 004: L2 原子状态原语与 L3 语义标签标准

## 1. 目的

本文档定义 Stock Lobster 从 L1 `AnalysisSnapshot` 继续沉淀经验类数据的标准。

这套标准用于后续“基于个股样本研究形态、沉淀原语、形成标签、再进入策略候选”的 workflow skill。

核心链路是：

```text
L1 AnalysisSnapshot
-> L2 AtomicStatePrimitive
-> L3 SemanticLabel
-> L4 StrategyDSL
```

中文解释：

- L1 是“可观察事实和基础因子快照”。
- L2 是“单一维度的原子状态判断”。
- L3 是“多个原子状态组合出来的业务语义标签”。
- L4 才是“用标签做召回、过滤、排序、信号和回测”。

最重要的边界：

```text
L2 不表达完整形态。
L3 不表达买卖动作。
L4 才表达策略使用方式。
```

## 2. 层级功能定义

### 2.1 L1 AnalysisSnapshot

L1 是基础数据和基础因子的快照层。

它回答：

```text
某只股票在某个日期，可以观察到哪些事实和基础因子？
```

例子：

```text
pub_stock_daily_kline.close
pub_stock_daily_kline.amount
pub_stock_daily_indicator.indicator_name
pub_stock_daily_indicator.indicator_value
pub_stock_daily_basic.pb
pub_stock_asset_basic.industry
```

L1 不判断形态，也不表达策略。

### 2.2 L2 AtomicStatePrimitive

L2 是原子状态原语层。

它回答：

```text
某只股票在某个日期，某个单一维度状态是否成立，或处于什么数值/类别状态？
```

L2 的特点：

- 只消费 L1 `AnalysisSnapshot`。
- 不查询 MySQL、文件、API 或外部服务。
- 不知道策略名。
- 不表达买入、卖出、召回、排序。
- 尽量原子化，可独立计算、独立解释、独立测试。
- 每个原语必须有唯一主分类，辅助标签可以另加，但主分类不能多个。

例子：

```text
trend.uptrend
trend.downtrend
volume_liquidity.amount_ratio_20d_high
volatility.low_volatility
level_breakout.close_new_high_60d
structure.ma_5_10_20_converged
fundamental_value.pb_low
context_industry.relative_strength_high
risk.short_term_overheated
```

### 2.3 L3 SemanticLabel

L3 是语义标签层。

它回答：

```text
一组 L2 原子状态组合起来，代表什么可复用的业务语义？
```

L3 可以是技术形态，也可以是基本面画像、环境状态、风险状态、复合准备态。

L3 的特点：

- 消费 L2 primitive 输出。
- 表达可复用的业务语义。
- 仍然不表达买卖动作。
- 可以作为 L4 策略召回、过滤、排除、排序的输入。
- 必须版本化、可复现、可解释。

例子：

```text
technical_pattern.uptrend_consolidation_breakout
technical_pattern.downtrend_bottoming
fundamental_profile.quality_value
context_regime.industry_relative_strength
risk_state.high_volatility_extension
composite_setup.low_valuation_bottoming_reversal
```

### 2.4 L4 StrategyDSL

L4 是策略组合层。

它回答：

```text
如何使用 L3 标签进行召回、过滤、排除、排序和回测？
```

L4 才可以表达：

```text
召回
过滤
排除
排序
入池
信号候选
回测口径
```

## 3. L2 分类标准

L2 按 MECE 原则划分为以下主类。每个 L2 原语只能选择一个主类。

| 主类 | 中文含义 | 典型问题 | 典型输出 |
| --- | --- | --- | --- |
| `data_quality` | 数据质量/快照可用性 | 这个快照能不能被消费？ | boolean |
| `tradability` | 可交易性/交易状态 | 是否停牌、流动性是否足够？ | boolean, category |
| `price_position` | 价格位置 | 当前价格在区间高位/低位/支撑附近吗？ | boolean, numeric, category |
| `return_momentum` | 收益动量 | 近 N 日涨跌幅、相对强弱是否突出？ | boolean, numeric |
| `trend` | 趋势方向 | 上升、下降、横盘、趋势转强/转弱？ | boolean, category |
| `moving_average` | 均线状态 | 是否站上均线、均线多头、均线收敛？ | boolean, numeric |
| `volume_liquidity` | 成交量/成交额/流动性 | 是否放量、缩量、量能衰减？ | boolean, numeric |
| `volatility` | 波动率状态 | 波动是否压缩、扩张、过高、过低？ | boolean, numeric |
| `level_breakout` | 支撑/压力/突破/跌破 | 是否突破平台、新高、跌破支撑？ | boolean |
| `structure` | 局部结构 | 是否平台整理、回踩、收敛、箱体？ | boolean, numeric, category |
| `fundamental_value` | 估值状态 | PE/PB/PS 是否低估或高估？ | boolean, numeric |
| `fundamental_quality` | 财务质量 | 盈利质量、ROE、现金流质量如何？ | boolean, numeric |
| `fundamental_growth` | 成长状态 | 收入/利润增长是否改善？ | boolean, numeric |
| `capital_structure` | 市值/股本/筹码结构 | 市值、流通盘、集中度处于什么状态？ | boolean, numeric, category |
| `context_market` | 市场环境 | 市场是否 risk-on/risk-off？ | boolean, category |
| `context_industry` | 行业/板块环境 | 行业是否强于市场？ | boolean, numeric, category |
| `context_theme` | 题材/概念/热度环境 | 题材热度是否上升？ | boolean, numeric, category |
| `risk` | 风险状态 | 是否过热、波动失控、流动性不足？ | boolean, category |

### 3.1 L2 命名规则

```text
<category>.<atomic_state_name>
```

例子：

```text
trend.uptrend
moving_average.close_above_ma20
volume_liquidity.amount_ratio_20d_high
volatility.low_volatility
level_breakout.close_new_high_60d
structure.ma_5_10_20_converged
fundamental_value.pb_low
risk.short_term_overheated
```

不允许：

```text
buy_signal
strong_buy
dragon_head_candidate
strategy_selected
```

原因：这些已经带有策略意图，应放到 L4 或更后面。

### 3.2 L2 注册字段

每个 L2 原语必须记录：

```text
primitive_id
version
status
category
output_type
input_features
params
calculation
valid_when
missing_policy
evidence
owner
notes
```

字段解释：

- `primitive_id`：原语唯一标识。
- `version`：计算口径版本。
- `status`：`candidate`、`approved`、`deprecated`。
- `category`：必须来自 L2 主类。
- `output_type`：`boolean`、`numeric`、`category`。
- `input_features`：依赖的 L1 特征或基础因子。
- `params`：阈值、窗口、指标名等参数。
- `calculation`：白盒计算口径。
- `valid_when`：什么条件下这个原语有效。
- `missing_policy`：缺失数据如何处理。
- `evidence`：样本证据、验证记录、研究记录引用。
- `owner`：负责维护的模块或人。
- `notes`：中文说明。

## 4. L3 分类标准

L3 按 MECE 原则划分为以下主类。每个 L3 标签只能选择一个主类。

| 主类 | 中文含义 | 典型问题 | 是否仅技术 |
| --- | --- | --- | --- |
| `quality_gate` | 质量/可消费门控 | 是否允许进入研究或策略链路？ | 否 |
| `technical_pattern` | 技术形态语义 | 多个技术状态组合成什么形态？ | 是 |
| `fundamental_profile` | 基本面画像 | 估值、质量、成长组合成什么画像？ | 否 |
| `context_regime` | 市场/行业/题材环境 | 当前环境对该股票是否有利？ | 否 |
| `risk_state` | 风险语义 | 是否存在需要排除或降权的风险？ | 否 |
| `composite_setup` | 复合准备态 | 技术、基本面、环境共同形成什么机会准备态？ | 否 |

结论：

```text
L3 不仅包含技术形态标签。
L3 也包含基本面画像、环境标签、风险标签、复合准备态标签。
```

### 4.1 L3 技术形态类

主类：

```text
technical_pattern
```

例子：

```text
technical_pattern.trend_continuation
technical_pattern.uptrend_consolidation_breakout
technical_pattern.low_volatility_convergence
technical_pattern.pullback_support_confirmed
technical_pattern.downtrend_bottoming
technical_pattern.bottoming_reversal
technical_pattern.volume_breakout
technical_pattern.high_level_distribution
technical_pattern.exhaustion_after_rally
```

### 4.2 L3 基本面画像类

主类：

```text
fundamental_profile
```

例子：

```text
fundamental_profile.low_valuation
fundamental_profile.quality_value
fundamental_profile.high_growth
fundamental_profile.profitable_growth
fundamental_profile.valuation_repair
fundamental_profile.weak_fundamental_risk
```

### 4.3 L3 环境类

主类：

```text
context_regime
```

例子：

```text
context_regime.market_risk_on
context_regime.market_risk_off
context_regime.industry_relative_strength
context_regime.theme_attention_rising
context_regime.style_small_cap_preferred
```

### 4.4 L3 风险类

主类：

```text
risk_state
```

例子：

```text
risk_state.short_term_overheated
risk_state.high_volatility_extension
risk_state.liquidity_insufficient
risk_state.breakout_failure_risk
risk_state.fundamental_deterioration
```

### 4.5 L3 复合准备态类

主类：

```text
composite_setup
```

例子：

```text
composite_setup.quality_growth_breakout
composite_setup.low_valuation_bottoming_reversal
composite_setup.industry_strength_volume_breakout
composite_setup.low_volatility_uptrend_continuation
```

注意：

复合准备态可以描述“机会准备状态”，但不能直接命名为：

```text
buy_candidate
strong_buy
tomorrow_signal
high_win_rate_strategy
```

这些属于 L4 策略或 L5 信号。

### 4.6 L3 注册字段

每个 L3 标签必须记录：

```text
label_id
version
status
category
primitive_refs
logic
output_fields
valid_when
evidence
promotion_policy
owner
notes
```

字段解释：

- `label_id`：标签唯一标识。
- `version`：标签逻辑版本。
- `status`：`candidate`、`approved`、`deprecated`。
- `category`：必须来自 L3 主类。
- `primitive_refs`：引用的 L2 原语及版本。
- `logic`：白盒组合逻辑。
- `output_fields`：标签输出字段，如 `matched`、`score`、`confidence`。
- `valid_when`：什么条件下标签有效。
- `evidence`：样本证据、验证记录、回测记录引用。
- `promotion_policy`：从 candidate 到 approved 的标准。
- `owner`：负责维护的模块或人。
- `notes`：中文说明。

## 5. L2 和 L3 的边界示例

### 示例一：上升趋势中继盘整突破

L2 原子状态：

```text
trend.uptrend == true
structure.consolidation_range == true
volatility.low_volatility == true
volume_liquidity.amount_expansion == true
level_breakout.platform_breakout == true
risk.short_term_overheated == false
```

L3 语义标签：

```text
technical_pattern.uptrend_consolidation_breakout
```

L4 策略用法：

```text
召回 technical_pattern.uptrend_consolidation_breakout
排除 risk_state.high_volatility_extension
按 volume_liquidity.amount_ratio_20d 排序
```

### 示例二：下跌趋势筑底反转

L2 原子状态：

```text
trend.prior_downtrend == true
price_position.low_position == true
volume_liquidity.selling_pressure_declining == true
volatility.volatility_contracting == true
return_momentum.momentum_recovering == true
level_breakout.short_term_resistance_break == true
```

L3 语义标签：

```text
technical_pattern.bottoming_reversal
```

### 示例三：低估值筑底修复

L2 原子状态：

```text
fundamental_value.pb_low == true
fundamental_quality.profitability_stable == true
price_position.low_position == true
trend.downtrend_decelerating == true
return_momentum.momentum_recovering == true
```

L3 语义标签：

```text
composite_setup.low_valuation_bottoming_reversal
```

## 6. 候选到批准流程

经验类数据必须先研究、再批准、再生产。

标准流程：

```text
PatternCase
-> FactorObservation
-> L2 PrimitiveCandidate
-> L2 PrimitiveEvidence
-> approved L2 PrimitiveDefinition
-> L3 LabelCandidate
-> L3 LabelEvidence
-> approved L3 LabelDefinition
-> L4 StrategyCandidate
```

L2 原语批准条件：

- 计算口径确定。
- 依赖的 L1 特征明确。
- 缺失数据处理明确。
- 至少有正样本和负样本验证。
- 有样本证据链接到 PatternCase。

L3 标签批准条件：

- 引用的 L2 原语版本明确。
- 标签逻辑白盒、确定性。
- 标签语义清楚，不与 L4 策略混淆。
- 能区分正样本和反例。
- 可以从版本化 L2 输出复现。

## 7. 第一阶段建设顺序

建议按这个顺序建设：

1. `data_quality` 和 `quality_gate`。
2. `trend`、`moving_average`。
3. `volume_liquidity`、`volatility`。
4. `price_position`、`return_momentum`。
5. `level_breakout`、`structure`。
6. `risk` 和 `risk_state`。
7. `fundamental_value`、`fundamental_quality`、`fundamental_growth`。
8. `context_market`、`context_industry`、`context_theme`。
9. `technical_pattern`、`fundamental_profile`、`context_regime`。
10. `composite_setup`。
11. L4 StrategyDSL。

这样可以保证：

```text
先有原子状态
再有语义标签
最后才有策略组合
```
