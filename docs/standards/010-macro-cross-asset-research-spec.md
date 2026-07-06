# Standard 010：宏观大类资产投研系统 Spec

## 目的

本文定义宏观大类资产投研系统的技术 spec。它把 `docs/product/001-macro-cross-asset-research-prd.md` 转化为可实现的分层对象、数据契约、分析流水线、置信结论路径和验收门。

本 spec 遵守现有规则：Stock Lobster 不生产权威事实数据，所有市场和宏观事实都必须来自外部 DataAsset 契约。

## 1. 分层映射

```text
External macro and market data
-> L0 MacroDataAsset contract
-> L1 MacroAnalysisSnapshot / AssetStateSnapshot / CrossAssetSnapshot
-> L2 MacroPrimitive
-> L3 MacroLabelSnapshot
-> research MacroResearchConclusion
-> app/report DrilldownTask and DailyBrief
-> optional L4 StrategyDSL context for approved A-share strategies
```

规则：

- L0 只描述和读取外部契约，不采集、不清洗、不修复事实数据。
- L1 只构建可复现快照，记录数据依赖、查询窗口和版本。
- L2 只能是作用于 L1 快照的纯函数。
- L3 只能由 L2 原语结果生成确定性标签。
- 研究结论可以由规则和 Agent 辅助生成，但必须标记为候选，且不能替代事实。
- A 股策略只能引用已批准的 L3 宏观标签或 approved metadata，不得直接读取宏观原始表。

## 2. 数据契约设计

### 2.1 `MacroDataAsset`

建议字段：

| 字段 | 含义 |
| --- | --- |
| `asset_id` | 全局唯一资产契约 id，例如 `macro.fred.dgs10.daily` |
| `provider` | 外部来源，例如 `fred`、`eia`、`fiscaldata`、`coingecko` |
| `source_url` | API 或文件入口 |
| `asset_group` | `rates`、`commodities`、`crypto`、`equity_index`、`macro` |
| `symbol` | 外部标识，例如 `DGS10`、`BTC`、`WTI` |
| `frequency` | `daily`、`weekly`、`monthly`、`event` |
| `calendar` | `us_business_day`、`cn_trading_day`、`crypto_24_7` |
| `field_schema` | 日期、数值、单位、币种、修订字段 |
| `quality_contract` | 延迟、缺失、异常、修订和许可要求 |
| `revision_policy` | 是否有历史修订，以及是否需要 vintage |
| `owner_layer` | 必须为 `L0` |

### 2.2 第一批候选来源

| 数据域 | 候选来源 | 用途 | 接入建议 |
| --- | --- | --- | --- |
| 美国宏观和利率 | FRED | CPI、PCE、就业、Fed funds、收益率、实际利率、信用利差代理 | 优先作为宏观时序和美债因子来源，注意 vintage/revision |
| 能源 | EIA Open Data | 原油库存、产量、消费、油价相关时序 | 用于油价驱动和供需解释 |
| 美国财政数据 | U.S. Treasury FiscalData | Treasury 相关利率、债务和财政数据 | 用于财政和利率上下文 |
| Crypto 价格和市场 | CoinGecko 或 Coin Metrics | BTC/ETH 价格、市值、成交、链上或市场指标 | 需要单独处理 24/7 日历 |
| 商品价格 | World Bank Commodity Markets、Nasdaq Data Link、交易所或商业源 | 大宗商品价格指数和单品种价格 | 免费源用于 MVP，商业源用于稳定生产 |
| A 股和行业 | 现有外部事实生产者的 `pub_*` 产品 | A 股宽基、行业、风格和策略下钻 | 继续通过现有 L0 DataAsset 消费 |
| 中国债券 | 中债、交易所、商业数据商或已授权内部源 | 国债收益率曲线和期限利差 | 生产前必须确认许可和字段契约 |

商业源候选包括 Wind、Choice、Bloomberg、Refinitiv、CEIC、S&P Global、Quandl/Nasdaq Data Link。它们适合作为生产级覆盖补齐，但必须先明确授权、字段、延迟和重分发限制。

## 3. 快照模型

### 3.1 `MacroAnalysisSnapshot`

面向宏观环境：

```text
snapshot_date
analysis_version
run_id
growth_state
inflation_state
liquidity_state
policy_state
usd_state
risk_appetite_state
source_dependencies
```

### 3.2 `AssetStateSnapshot`

面向单资产：

```text
snapshot_date
asset_id
asset_group
analysis_version
run_id
price_return_windows
trend_features
volatility_features
volume_or_liquidity_features
valuation_or_curve_features
relative_strength_features
source_dependencies
```

不同资产允许字段稀疏，但字段缺失必须显式记录，不得用 Agent 补齐。

### 3.3 `CrossAssetSnapshot`

面向联动：

```text
snapshot_date
analysis_version
run_id
asset_pair_or_basket
correlation_window
relative_strength
divergence_score
regime_alignment
lead_lag_hint
source_dependencies
```

`lead_lag_hint` 只能作为研究提示，不能直接成为交易信号。

## 4. L2 原语清单

第一批原语应覆盖五类。

### 4.1 趋势原语

- `is_above_moving_average`
- `is_multi_window_momentum_positive`
- `is_trend_strength_rising`
- `is_drawdown_repairing`

### 4.2 异动原语

- `is_return_zscore_extreme`
- `is_volatility_breakout`
- `is_volume_or_liquidity_expanding`
- `is_curve_move_extreme`

### 4.3 宏观 regime 原语

- `is_growth_improving`
- `is_inflation_pressure_rising`
- `is_liquidity_tightening`
- `is_policy_rate_expectation_shifting`
- `is_usd_strengthening`

### 4.4 跨资产一致性原语

- `is_gold_confirmed_by_real_rate`
- `is_oil_confirmed_by_inventory`
- `is_equity_confirmed_by_credit_and_volatility`
- `is_btc_confirmed_by_risk_appetite`
- `is_cn_equity_confirmed_by_cn_rates_and_liquidity`

这些原语名称表达研究含义，但实现必须只读取 L1 快照字段。

### 4.5 反证原语

- `has_counter_signal_from_usd`
- `has_counter_signal_from_real_rate`
- `has_counter_signal_from_credit_spread`
- `has_counter_signal_from_curve`
- `has_counter_signal_from_cross_asset_divergence`

反证原语是置信结论的必要输入，不能只输出支持证据。

## 5. L3 标签设计

标签示例：

| 标签 | 说明 |
| --- | --- |
| `macro_regime_growth_up_inflation_down` | 增长改善且通胀压力缓和 |
| `macro_regime_liquidity_tightening` | 流动性趋紧 |
| `asset_trend_up_confirmed` | 资产趋势向上且多窗口确认 |
| `asset_trend_up_unconfirmed` | 价格趋势向上但驱动因素不一致 |
| `asset_anomaly_positive_return` | 正向价格异动 |
| `asset_anomaly_curve_steepening` | 曲线陡峭化异动 |
| `cross_asset_divergence_gold_real_rate` | 黄金与实际利率背离 |
| `risk_appetite_recovering` | 风险偏好修复 |

每个标签必须包含：

```text
label_id
label_version
run_id
snapshot_date
input_snapshot_ids
primitive_results
supporting_evidence
counter_evidence
quality_status
```

## 6. 置信结论路径

系统不能输出“因为 Agent 认为所以置信”的结论。置信度必须由结构化证据生成。

### 6.1 结论结构

```text
conclusion_id
conclusion_type
subject_asset_or_regime
direction
time_horizon
summary
confidence_score
confidence_grade
supporting_evidence
counter_evidence
missing_evidence
source_dependencies
label_dependencies
generated_by
review_status
```

`generated_by` 可以是 rule、agent_assisted 或 human，但 `review_status` 未通过前不能进入 approved 研究库。

### 6.2 置信度分解

建议初始权重：

| 维度 | 权重 | 说明 |
| --- | --- | --- |
| 数据质量 | 25% | 来源是否就绪、缺失率、延迟、修订风险 |
| 信号一致性 | 25% | 趋势、波动、成交、期限结构等是否同向 |
| 跨资产一致性 | 20% | 相关资产、利率、美元、信用、风险偏好是否支持 |
| 历史可验证性 | 15% | 相似标签组合历史表现是否稳定 |
| 时效性 | 10% | 数据是否足够新，事件是否仍有效 |
| 反证压力 | -20% 到 0% | 反证越强，扣分越多 |

得分约束：

- 任一核心 DataAsset 质量失败，结论最高只能为 `low`。
- 只有支持证据但没有反证检查，结论最高只能为 `medium_low`。
- 存在跨资产强背离时，结论不能为 `high`。
- 没有历史验证时，结论可以是研究提示，但不能标为高置信趋势。

### 6.3 等级映射

| 分数 | 等级 | 含义 |
| --- | --- | --- |
| `>= 80` | `high` | 多维证据一致，反证弱，数据质量通过 |
| `65-79` | `medium_high` | 主要证据成立，但存在轻微缺口 |
| `50-64` | `medium` | 可关注，需要下钻确认 |
| `35-49` | `medium_low` | 仅作为异动或研究提示 |
| `< 35` | `low` | 不形成有效结论 |

## 7. 异动提醒规则

异动事件必须保存：

```text
event_id
event_type
subject_asset
triggered_at
snapshot_date
trigger_rule_version
observed_value
threshold
history_percentile
lookback_window
supporting_labels
counter_labels
confidence_score
next_drilldown_tasks
```

第一批事件：

- 单日或三日收益率 z-score 异动。
- 波动率突破过去 60/120 日分位。
- 美债 2Y、10Y、30Y 单日 bp 变化异动。
- 2Y-10Y 或 10Y-30Y 曲线斜率异动。
- 黄金与实际利率/美元背离。
- 油价与库存/期限结构背离。
- BTC 与纳指、美元流动性或风险偏好背离。

## 8. 下钻路径

每条结论或提醒都应给出下一步路径：

```text
asset_group
-> single_asset
-> driver_family
-> evidence_panel
-> counter_evidence_panel
-> historical_analog
-> impact_to_a_share_universe
```

A 股影响只能输出为研究上下文或候选池提示：

- 宽基风险偏好。
- 风格倾向：成长、价值、红利、小盘、大盘。
- 行业方向：资源、科技、出口、消费、金融等。
- 策略开关建议：只能成为候选，不得自动修改 approved StrategyDSL。

## 9. 文件和配置建议

推荐后续落地路径：

```text
configs/data_assets/macro_cross_asset_data_assets.example.json
configs/labels/macro_label_registry.example.json
configs/research_workflows/macro_cross_asset_daily_brief.example.json
stock_lobster/l1_analysis_snapshot/macro_schema.py
stock_lobster/l2_primitives/macro.py
stock_lobster/l3_labels/macro_registry.py
stock_lobster/research/macro_cross_asset.py
docs/product/001-macro-cross-asset-research-prd.md
docs/standards/010-macro-cross-asset-research-spec.md
```

代码实现前，应先补 `configs/data_assets/` 契约和 L1 schema 的合成测试。

## 10. 验收标准

P0 文档验收：

- PRD 明确资产范围、场景、非目标和 MVP。
- Spec 明确 L0-L6 分层映射、对象、置信结论路径。
- DataAsset 示例不包含 secret，不暗示本系统生产事实数据。

P1 工程验收：

- 至少 5 个宏观或大类资产 DataAsset 可以被 L0 catalog 读取。
- L1 可以用合成输入构建三类快照。
- 快照记录全部来源依赖。

P2 分析验收：

- 趋势、异动、跨资产一致性和反证原语都是纯函数。
- 相同输入生成相同 L3 标签。
- 异动提醒包含规则版本、阈值、历史分位和反证。

P3 产品验收：

- 每日简报可生成，且结论可追溯到 DataAsset、Snapshot、Primitive 和 Label。
- 置信度分解可解释，不是黑盒 Agent 打分。
- 未审批结论不会进入正式策略或观察池。
