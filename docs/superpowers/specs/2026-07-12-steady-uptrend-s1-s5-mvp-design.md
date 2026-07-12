# 稳健上升趋势 S1-S5 MVP 设计

## 1. 目标与状态

- 目标：在一天内形成一条确定性、可回放、可解释的 A 股稳健上升趋势 MVP 选股链路。
- 状态：候选设计，用户确认书面版本后进入实现。
- 业务层级：本文使用 `S1-S5` 表达策略筛选步骤，不改变系统技术架构 `L0-L6`。
- 数据边界：Stock Lobster 只消费外部事实数据和指标契约，不采集、修复或生产权威事实数据。

## 2. MVP 链路

```text
数据与指标可用性检查
-> S1 硬性质量过滤
-> S2 成熟趋势过滤
-> S3 形态结构召回
-> S4 股性稳健性精筛
-> S5 介入层筛选
-> 按行业汇总输出
```

标准标识：

| 层级 | 中文名称 | 标识 |
| --- | --- | --- |
| S1 | 硬性质量过滤 | `quality_filter` |
| S2 | 成熟趋势过滤 | `mature_trend_filter` |
| S3 | 形态结构召回 | `structure_recall` |
| S4 | 股性稳健性精筛 | `stability_refinement` |
| S5 | 介入层筛选 | `entry_selection` |

## 3. 日期和复权约定

- `t` 是信号日。
- “前 N 个完整交易日”使用 `[t-N, t-1]`，不包含信号日。
- 当前状态条件可以使用信号日收盘后已发布的数据。
- 日线 OHLC、前收盘价和 MA 必须来自同一个可复现复权口径。
- 周线使用 `period_end_date <= signal_date` 的最新已完成周线；周五收盘后可使用本周周线，非周五使用上一条已完成周线。
- 行业、概念、指数价格和成分关系全部按信号日对齐，不使用未来数据。

## 4. S1 硬性质量过滤

全部通过才进入 S2：

```text
数据完整且质量状态可用
正常上市
非 ST
total_mv >= 1,000,000 万元，即 100 亿元
avg_amount_20d >= 200,000 千元，即 2 亿元
```

S1 不包含趋势、K 线形态、量比、行业或概念判断。

## 5. S2 成熟趋势过滤

日线条件全部通过：

```text
close_t > MA20_t > MA60_t
close_t / close_t-60 - 1 >= 5%
最近 60 日至少 30 日 close > 当日 MA60
MA60_t > MA60_t-20
最近 60 日收盘价最大回撤绝对值 <= 50%
```

周线条件全部通过：

```text
weekly_close > weekly_MA20
weekly_MA10 > weekly_MA20
weekly_MA20_t > weekly_MA20_t-4
weekly_MA10 > weekly_MA30 > weekly_MA60
最近 26 周收盘价最大回撤绝对值 <= 50%
```

MVP 只研究成熟趋势，不加入趋势修复、早期反转或筑底分支。

## 6. S3 形态结构召回

S3 是 OR 召回。一只股票可以同时命中多个结构；至少命中一个结构才进入 S4。

### 6.1 S3-A 高位平台或首次突破

```text
close_t / high_close_60d - 1 >= -10%
```

该结构只表达接近 60 日高位，不在 S3 判断平台是否成熟。

### 6.2 S3-B 回调后恢复

在信号日前 20 个交易日识别最近一次相对滚动前高回撤至少 5% 的回调段，并取段内最深收盘价作为低点。

回调条件：

```text
-20% <= pullback_depth <= -5%
```

支撑条件满足任意一种：

```text
低点收盘价距离当日 MA20 或 MA30 不超过 3%
OR
低点收盘价高于当日 MA20 0% 到 15%
```

从低点到信号日不得出现有效 MA60 跌破：

```text
任一日 close < 0.97 * MA60
OR
连续至少 2 日 close < MA60
=> 有效跌破，S3-B 不通过
```

当前恢复条件：

```text
close_t > MA20_t
MA5_t > MA10_t
return_5d > 0
close_t / trough_close - 1 >= 3%
```

S3-B 不强制 10 日平台，不在本层判断恢复是否过陡。

### 6.3 S3-C 均线稳步上行

```text
MA5 >= MA10 >= MA20 > MA60
MA10_t > MA10_t-10
MA20_t > MA20_t-20
return_20d > 0
最近 10 日收盘价振幅 <= 15%
最近 10 日收盘价最大回撤绝对值 <= 10%
最近 10 日至少 7 日满足 MA5 >= MA10 >= MA20
NOT wide_swing_rebound
```

宽幅下跌反弹定义：

```text
前 5 日收益 <= -5%
AND 后 5 日收益 >= 20%
```

## 7. S4 股性稳健性精筛

S4 只判断股票的中短期股性是否稳定，不判断当前平台成熟度、行业时效或价格是否适合追高。

任一硬风险分支命中即剔除。

### 7.1 S4-A 影线噪声和均线反复组合

单日上影线结构比例：

```text
upper_shadow_ratio
= (high - max(open, close))
  / (high - min(open, close))
```

当分母小于等于 0 时，该日比例记为 0。这里不增加“真实上影线幅度”条件。

总影线占比：

```text
total_shadow_share
= ((high - low) - abs(close - open))
  / (high - low)
```

当 `high <= low` 时，该日占比记为 0。

均线排列状态：

```text
ma_alignment_state = MA5 >= MA10 >= MA20
```

在前 60 个完整交易日中，相邻交易日状态从真变假或从假变真，各计 1 次切换。

组合硬过滤：

```text
前 20 个完整交易日 upper_shadow_ratio >= 60% 的天数 >= 5
AND
前 60 个完整交易日 total_shadow_share 平均值 >= 56%
AND
前 60 个完整交易日 ma_alignment_state 切换次数 >= 5
=> 剔除
```

### 7.2 S4-B 红绿比异常

```text
red_k = close >= open
red_k_ratio_60d = 前 60 个完整交易日 red_k 天数 / 60

red_k_ratio_60d < 45%
=> 剔除
```

`close == open` 按红 K 处理，与现有样本记录保持一致。

### 7.3 S4-C 极端阴柱频发

单日极端阴柱：

```text
close_t < open_t
AND
(prev_close - close_t) / prev_close >= 7%
```

`prev_close` 是前一个交易日同复权口径收盘价。

```text
前 10 个完整交易日 extreme_bearish_day 数量 >= 3
=> 剔除
```

不要求 3 日连续。该分支是低频极端风险兜底。

## 8. S5 介入层筛选

### 8.1 S5-A 强势行业或题材过滤

```text
strong_industry_hit
OR strong_concept_hit
=> 通过
```

强势指数是趋势强势和热度强势的并集。

趋势强势：

```text
行业指数和概念指数分别计算近 20 日收益率排名
return_rank_pct <= 30%
AND index_close > index_MA20
AND index_close > index_MA60
```

热度强势：

```text
每天取正常上市、非 ST 股票涨幅前 200 名
按指数成分股命中比例和命中数量排序
行业指数和概念指数分别取每日 Top5
最近 20 日进入 Top5 至少 3 次
且最近 5 日进入 Top5 至少 1 次
```

股票在信号日属于任一强势行业指数时，`strong_industry_hit=true`；属于任一强势概念指数时，`strong_concept_hit=true`。两者均未命中或上下文缺失时，不进入最终介入候选。

### 8.2 S5-B MA20 偏离度提醒

```text
ma20_deviation_pct = close_t / MA20_t - 1
```

偏离度不参与过滤，只提供提醒和排序字段：

| 区间 | 等级 | 提示 |
| --- | --- | --- |
| `< 20%` | 正常 | 未明显偏离 MA20 |
| `[20%, 30%)` | 20 级 | 价格开始偏高 |
| `[30%, 40%)` | 30 级 | 偏离较大，注意追高 |
| `[40%, 50%)` | 40 级 | 高位偏离，谨慎介入 |
| `>= 50%` | 50 级 | 严重偏离，仅作风险提示 |

边界值进入更高一级，例如正好 30% 进入 30 级。

## 9. 最终排序和输出

每只股票只在股票基础资料中的规范行业字段下出现一次。概念不单独建立分组，只在个股维度展示。

行业分组顺序：

```text
该行业内 strong_industry_hit=true 的介入候选数量降序
-> 该行业全部介入候选数量降序
-> 行业名称升序
```

组内排序：

```text
strong_industry_hit=true 优先
-> ma20_deviation_pct 升序
-> asset_id 升序
```

仅命中强势概念的股票仍按基础行业汇总，排在同一行业中强势行业命中股票之后。

展示格式：

```text
半导体：
江丰电子（偏离 8.2%，正常；概念：先进封装、光刻机）
北方华创（偏离 17.5%，正常；概念：芯片设备）
杰华特（偏离 24.1%，20 级；概念：第三代半导体）
```

没有命中强势概念时省略概念字段。

机器可读输出至少包含：

```text
trade_date
asset_id
name
industry
matched_structures
strong_industry_hit
strong_industry_names
strong_concept_hit
strong_concept_names
close
ma20
ma20_deviation_pct
ma20_deviation_level
s1_pass
s2_pass
s3_pass
s4_pass
s5_pass
blockers
```

JSON 是事实来源，同时输出便于人工检查的 Markdown；需要时可以附加 CSV。

## 10. MVP 明确不做

- 形态成熟度状态机。
- 行业或个股综合评分。
- 市场环境过滤。
- 动态 TopN。
- cooldown。
- 排名后补位或 `no-refill`。
- MA20 偏离度硬过滤。
- Agent 直接产生事实指标或绕过 StrategyDSL/L5 信号引擎。

## 11. 审计和错误处理

- 每层必须输出输入数量、通过数量、剔除数量和阻断原因计数。
- 每只股票保留首个阻断层和全部阻断条件。
- S5 行业或概念上下文缺失时记录 `context_strength_unavailable` 并按不通过处理。
- MA20 不可用时记录 `ma20_deviation_unavailable`；该股票不得生成缺少关键解释字段的正式介入候选。
- 所有输出携带策略版本、信号日、数据依赖版本和 `run_id`。

## 12. 当前研究证据

以 `20260710` 临时全市场复权回放为参考：

```text
全市场：5521
S1：1526
S2：166
S3：107
S4：91（剔除 16）
```

这些数字是研究证据，不是生产验收常量。S5 数量取决于信号日强势行业和概念上下文。

样本约束：

- 强瑞技术 `20260608` 应被 S4 影线噪声和均线反复组合剔除。
- 麦格米特 `20260429` 应被 S4 红绿比异常识别；在完整链路中也可能更早被 S2 剔除。
- 铜冠铜箔 `20260609`、宏和科技已确认正样本不得仅因上影线次数被 S4 剔除。
- 极端阴柱分支当前是低频兜底，不要求在现有样本中强制命中。

## 13. 实现边界

- L2 原语负责本文中的确定性数值和布尔计算。
- L3 标签负责形成版本化的趋势、结构、稳定性和上下文标签。
- L4 StrategyDSL 负责组合 S1-S5 业务阶段。
- L5 是唯一生成最终介入候选信号的层。
- L6 回放必须复用同一 StagePipeline，不能复制一套研究专用判断。
- 研究工作流可以输出候选配置和验证报告，但在用户批准前保持候选或测试跟踪状态。
