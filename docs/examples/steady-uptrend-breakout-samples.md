# 样本组：稳健上升趋势突破

## 1. 样本来源

用户提供了十一组 A 股截图样本：

- `603256.SH` 宏和科技
- `301217.SZ` 铜冠铜箔
- `688017.SH` 绿的谐波
- `002384.SZ` 东山精密
- `600105.SH` 永鼎股份
- `301526.SZ` 国际复材
- `001896.SZ` 豫能控股
- `600188.SH` 兖矿能源
- `002378.SZ` 章源钨业
- `301128.SZ` 强瑞技术
- `002851.SZ` 麦格米特

红色箭头表示用户认为“这个级别可以介入或需要及时关注”的位置。永鼎股份样本中，`20260624` 收盘后召回被标记为反例，用于沉淀排除条件和风险降权规则。豫能控股、兖矿能源当前先作为边界负样本，不直接作为硬负样本。章源钨业当前作为形态族外硬负样本，因为它更像下跌趋势后的筑底尝试，不属于本形态族。强瑞技术、麦格米特当前作为趋势质量硬负样本，因为它们仍在上升趋势突破的大框里，但日级别走势质量不够稳健，存在上下影线多、历史回撤大、绿 K 偏多、红绿比弱或均线破位等问题。

## 2. 形态理解

这些样本共同表达的不是简单追高，而是一个更窄的形态族：

```text
上升趋势强势股
-> 再次向上突破
-> 量能确认
-> 进入关注或测试策略召回
```

如果突破前存在整理、均线靠拢或平台蓄势，则可以进一步归入“趋势中继整理突破”子形态；但第一版策略准备态不把“均线收敛”作为硬条件，避免漏掉已经进入主升趋势后的继续突破样本。

从图形观察看，关键特征包括：

- 股票已经处于上升趋势，而不是底部刚启动。
- 均线系统呈现多头排列，价格大多数时间运行在中短期均线上方。
- 回撤相对可控，趋势推进比较稳健。
- 突破前有整理、均线靠拢或平台蓄势。
- 突破发生时，价格向上离开整理区，并且量能或动量有确认。

随着样本扩展，当前形态族可以拆成三个正向子场景和一个风险场景：

- `长期盘整后早期突破`：例如东山精密 `20260226`，价格刚从长期底部或平台走出，周级别加速仍在初期。
- `趋势中继突破`：例如宏和科技、铜冠铜箔，股票已经处于趋势内，整理后继续向上。
- `高位平台反复试探后突破`：例如绿的谐波第二个箭头、永鼎股份 `20260401`，价格在高位盘整并多次挑战前高。
- `高位过热或趋势质量不足`：例如永鼎股份 `20260624`，价格可能已经过高，后续回撤较多，经常跌破 MA30，不能简单按正向突破召回。

## 3. L2 原语候选

第一批 L2 原语候选：

```text
moving_average.close_above_ma20
moving_average.close_above_ma60
moving_average.ma20_above_ma60
moving_average.ma60_above_ma120
trend.ma20_rising_20d
risk.max_drawdown_60d_controlled
structure.ma_5_10_20_converged
level_breakout.close_new_high_60d
volume_liquidity.amount_ratio_20d_high
```

其中部分原语依赖当前基础数据层还没有例行生产的指标：

```text
ma60
ma120
ma20_slope_20d
max_drawdown_60d
close_new_high_60d_flag
convergence_5_10_20_pct
```

## 4. L3 标签候选

第一批 L3 标签候选：

```text
technical_pattern.steady_uptrend_stock
technical_pattern.steady_uptrend_new_high_breakout
technical_pattern.uptrend_consolidation_breakout
technical_pattern.volume_breakout
composite_setup.steady_uptrend_breakout_watch
```

中文解释：

- `steady_uptrend_stock`：刻画“稳健趋势股”。
- `steady_uptrend_new_high_breakout`：刻画“稳健趋势股再次向上突破”。
- `uptrend_consolidation_breakout`：刻画“上升趋势中的中继整理后突破”。
- `volume_breakout`：刻画“价格突破时量能确认”。
- `steady_uptrend_breakout_watch`：把趋势质量、新高突破和量能确认组合成 L4 可用的关注准备态。

新增样本后，后续可研究扩展的 L3 标签包括：

```text
technical_pattern.pre_breakout_accumulation_in_uptrend
technical_pattern.high_level_w_base_breakout_watch
technical_pattern.long_base_early_trend_breakout
technical_pattern.weekly_early_acceleration_breakout
technical_pattern.high_level_base_breakout
technical_pattern.high_level_trend_extension
technical_pattern.pullback_reacceleration_breakout
technical_pattern.low_drawdown_rebreakout_after_volume_breakout
risk_state.short_rest_breakout_failure_risk
risk_state.fishtail_acceleration_risk
risk_state.breakout_followthrough_uncertain
risk_state.high_level_breakout_failure_risk
technical_pattern.overextended_unstable_breakout
technical_pattern.high_level_rest_after_breakout_continuation
technical_pattern.steady_ma10_walkup_new_high_acceleration
technical_pattern.steady_late_acceleration_breakout
risk_state.weekly_overextension_watch
risk_state.high_level_consolidation_failure_watch
risk_state.theme_dependent_breakout_failure
risk_state.high_volume_spike_a_drop_risk
risk_state.out_of_family_downtrend_base
risk_state.prior_drawdown_too_large
technical_pattern.bottoming_attempt_not_steady_uptrend
risk_state.noisy_candlestick_unstable_breakout
risk_state.ma_convergence_breakdown_after_breakout
risk_state.trend_quality_hard_negative
risk_state.weekly_uptrend_daily_quality_failed
risk_state.red_green_ratio_unhealthy
```

这些标签当前仍属于研究候选，不直接进入生产注册。只有当正反例数量、基础数据复核、回测结果和人工口径评审都通过后，才可以进入正式 L3 registry。

## 4.1 样本知识库

本主题的结构化样本库已经落盘：

```text
configs/research_samples/steady_uptrend_breakout_samples.json
```

图片证据已经从临时目录复制到仓库：

```text
docs/assets/research_samples/steady_uptrend_breakout/
```

当前样本库包含：

| 股票 | 样本性质 | 已确认日期 | 关键经验 |
| --- | --- | --- | --- |
| `603256.SH` 宏和科技 | 分层正例 | `20260409`、`20260429`、`20260522`、`20260611` | `20260409`、`20260522` 是高价值正样本；`20260429`、`20260611` 是中价值正样本，后者可能偏鱼尾行情。 |
| `301217.SZ` 铜冠铜箔 | 正例 + 弱/排除候选 | `20260427`、`20260526`、`20260609` | `20260427` 是长期盘整后突破；`20260526` 休整太短、可考虑不作为正样本；`20260609` 是低回撤缩量回落后再突破的高质量点。 |
| `688017.SH` 绿的谐波 | 正例 | 待补齐 | 第一个点是慢涨放量接近高位，第二个点是高位 W 形态挑战前高。 |
| `002384.SZ` 东山精密 | 正例 | `20260226`、`20260408`、`20260615` | `20260226` 是长期盘整后早期突破，优先级高；后两个属于趋势延续或高位延伸。 |
| `600105.SH` 永鼎股份 | 正反例混合 | `20260401`、`20260624` | `20260401` 是高位平台突破正例；`20260624` 是过高后召回反例，需要风险过滤。 |
| `301526.SZ` 国际复材 | 高价值正例 | `20260423`、`20260610` | `20260423` 是突破后弱回调再高位休整；`20260610` 是稳健缓涨后沿 MA10 新高加速，虽可能偏鱼尾但趋势质量很高。 |
| `001896.SZ` 豫能控股 | 边界负样本 | `20260603` | 召回形态本身未必有问题，但后续高位盘整后下跌，可能与题材或市场环境有关。 |
| `600188.SH` 兖矿能源 | 边界负样本 | `20260601` | 涨停后高位放量拉伸，随后 A 字下杀，更接近高位放量冲顶风险。 |
| `002378.SZ` 章源钨业 | 硬负样本 | `20260612` | 前期回撤太多，日级别已经偏下跌趋势，虽然有筑底迹象，但不属于稳健上升趋势突破。 |
| `301128.SZ` 强瑞技术 | 趋势质量硬负样本 | `20260608` | 上下影线多、走势噪声大，均线黏合后跌破 MA30，说明趋势推进不够稳健。 |
| `002851.SZ` 麦格米特 | 趋势质量硬负样本 | `20260429` | 周级别是上涨趋势，但日级别不够稳健，历史回撤大，绿 K 多，红绿比难看。 |

### 4.2 最初两个样本的日期校准

`301217.SZ` 铜冠铜箔：

| 日期 | 样本判断 | 经验解释 | 后续口径方向 |
| --- | --- | --- | --- |
| `20260427` | 正样本 | 常规意义的长期盘整后突破往上。 | `long_base_early_trend_breakout`。 |
| `20260526` | 弱样本 / 可排除 | 休整太短，不够稳健，后期加速后回落，不是好的关注介入点。 | `rest_duration_too_short`、`short_rest_breakout_failure_risk`。 |
| `20260609` | 高价值正样本 | 前期有两个放量突破高点，再慢慢缩量回落，回撤低且稳健，突破点质量高，后续加速。 | `volume_contracting_pullback`、`low_drawdown_rebreakout_after_volume_breakout`。 |

`603256.SH` 宏和科技：

| 日期 | 样本判断 | 经验解释 | 后续口径方向 |
| --- | --- | --- | --- |
| `20260409` | 高价值正样本 | 长期盘整后突破往上，是高价值介入点。 | `long_base_early_trend_breakout`。 |
| `20260429` | 中价值正样本 | 小加速之后继续往上，但后续涨幅可能较慢，实际短期后出现回调。 | `breakout_followthrough_uncertain`。 |
| `20260522` | 高价值正样本 | 回调之后再次加速上涨，力度比第二个点更强，后续短期涨幅更大。 | `pullback_reacceleration_breakout`。 |
| `20260611` | 中价值正样本 | 继续往上加速，但可能已经偏鱼尾行情。 | `fishtail_acceleration_risk`。 |

这次校准让样本库不再只有“正/反”两类，而是开始区分样本价值：

```text
high：高价值正样本，可作为策略核心口径校准样本。
mid：中价值正样本，可参与召回但需要较低权重或更强风控。
low_or_exclude：弱样本或排除候选，用于沉淀降权和过滤条件。
context：高周期背景样本，不直接等同于日线介入事件。
```

### 4.3 国际复材样本补充

`301526.SZ` 国际复材：

| 日期 | 样本判断 | 经验解释 | 后续口径方向 |
| --- | --- | --- | --- |
| `20260423` | 高价值正样本 | K 线从盘整向上突破后出现一点弱回调，随后高位休整，向上概率高；周级别趋势和均线偏离度需要复核，初步看没有极端夸张。 | `weak_pullback_after_breakout`、`high_level_rest_after_breakout_continuation`、`ma_deviation_not_extreme`。 |
| `20260610` | 高价值正样本 | 趋势缓步上涨后开始加速，可能已经进入鱼尾行情，但温和放量、沿 MA10 上涨、回撤低、基本不跌破 MA20、红绿比好看，随后突破新高且涨幅惊人。 | `ma10_walk_up`、`ma20_hold_ratio_high`、`mild_amount_expansion`、`steady_ma10_walkup_new_high_acceleration`。 |

这组样本修正了前面对“鱼尾行情”的简单理解：

```text
鱼尾加速不是天然低价值。
如果加速前趋势推进非常稳健，回撤低、红绿比健康、基本不破 MA20，并且量能是温和放大而不是极端脉冲，
那么鱼尾阶段也可能是高价值加速样本，只是需要更严格的回撤、乖离和退出监控。
```

### 4.4 边界负样本判断

这两个样本不建议直接作为“硬负样本”，更适合作为边界负样本：

```text
borderline_negative：召回逻辑可能合理，但后续表现失败；先用于沉淀风险口径，不直接否定召回条件。
hard_negative：形态本身就明显不应召回，或多个同类样本反复证明该条件高概率失败。
```

`001896.SZ` 豫能控股：

| 日期 | 样本判断 | 经验解释 | 后续口径方向 |
| --- | --- | --- | --- |
| `20260603` | 边界负样本 | 整体召回看起来问题不大，但后续高位盘整后下跌；失败可能和题材退潮、市场环境或高位延续不足有关。 | `high_level_consolidation_failure_watch`、`theme_dependent_breakout_failure`。 |

`600188.SH` 兖矿能源：

| 日期 | 样本判断 | 经验解释 | 后续口径方向 |
| --- | --- | --- | --- |
| `20260601` | 边界负样本，偏强风险 | 涨停之后高位放量拉伸，后续 A 字下杀，更像高位情绪冲顶或放量兑现。 | `high_volume_spike_a_drop_risk`、`overextended_unstable_breakout`。 |

当前判断：

- 豫能控股不宜太严苛地判成硬负样本，因为它可能是“召回正确但后续跟踪/退出失败”。
- 兖矿能源更接近负面风险样本，但仍建议先作为边界负样本，等更多“涨停后高位放量拉伸”样本验证。
- 这类样本更适合推动 L4 增加确认规则，例如次日不追、放量冲高后等待缩量承接、跌破 MA10/MA20 快速退出，而不是直接取消召回。

### 4.5 形态族外硬负样本

`002378.SZ` 章源钨业：

| 日期 | 样本判断 | 经验解释 | 后续口径方向 |
| --- | --- | --- | --- |
| `20260612` | 硬负样本 / 形态族外负样本 | 前期回撤太多，日级别已经是下跌趋势；虽然开始筑底，但个股不够稳健，不符合上升趋势强势突破。 | `prior_drawdown_too_large`、`daily_downtrend_context`、`bottoming_attempt_not_steady_uptrend`。 |

这个样本和豫能控股、兖矿能源不同：

```text
豫能控股、兖矿能源：召回形态可能成立，但后续失败，需要研究跟踪、确认和退出。
章源钨业：前置趋势条件就不成立，更应作为本策略的入口排除样本。
```

章源钨业不是说“筑底反转没有价值”，而是它属于另一套形态族。后续可以单独建立：

```text
下跌趋势筑底反转
超跌修复突破
底部右侧确认
```

但这些不应混入 `strategy.steady_uptrend_breakout_watch` 的正向样本池。

### 4.6 趋势质量硬负样本

`301128.SZ` 强瑞技术：

| 日期 | 样本判断 | 经验解释 | 后续口径方向 |
| --- | --- | --- | --- |
| `20260608` | 硬负样本 / 趋势质量负样本 | 走势不好看，上下影线都很多；均线黏合之后跌破 MA30，说明趋势推进不顺、承接不稳定。 | `long_shadow_ratio_high`、`upper_lower_shadow_noise_high`、`ma_convergence_then_ma30_break`、`trend_quality_hard_negative`。 |

`002851.SZ` 麦格米特：

| 日期 | 样本判断 | 经验解释 | 后续口径方向 |
| --- | --- | --- | --- |
| `20260429` | 硬负样本 / 高周期趋势成立但日线质量负样本 | 周级别是上涨趋势，但日级别走势不够稳健；历史回撤大，绿 K 多，红绿比难看。 | `weekly_uptrend_daily_quality_failed`、`historical_drawdown_large`、`green_k_ratio_high`、`red_green_ratio_weak`。 |

这个样本和章源钨业也不同：

```text
章源钨业：前置趋势条件不成立，更像下跌趋势后的筑底尝试，应作为形态族外排除。
强瑞技术：前置趋势框架大体还在，但走势质量差，应作为趋势质量过滤样本。
麦格米特：周线趋势可以，但日线入场质量不行，说明高周期趋势不能替代日级别稳健性检查。
```

强瑞技术、麦格米特对 L4 策略的价值不是否定“上升趋势突破”这个大方向，而是提醒召回不能只看周线趋势、新高、均线和突破，还要看推进过程是否干净：

```text
上下影线过多
K 线实体推进不足
短中期均线黏合后未向上发散
黏合失败后跌破 MA30
历史回撤过大
绿 K 占比偏高
红绿比偏弱
```

这类样本后续应推动 L2 增加影线噪声、K 线实体质量、均线黏合后方向确认、历史回撤和红绿比健康度等原语；L3 增加“噪声型不稳定突破”“均线黏合后破位”“周线趋势成立但日线质量失败”等风险标签。

其中，永鼎股份补充了一个重要经验原语方向：

```text
K 线红绿比
```

定义：

```text
红 K：close >= open
绿 K：close < open
```

强势趋势股通常应有更高的红 K 占比；如果绿 K 过多、频繁跌破 MA30、突破后回撤大，则应降低召回分数或直接作为排除条件。

## 5. 当前样本扫描证据

使用 `workflows/jobs/steady_uptrend_breakout_research_scan.py` 对两只股票全历史日线进行确定性扫描，第一版候选阈值为：

```text
amount_ratio_20d >= 1.5
abs(max_drawdown_60d) <= 0.40
close > ma20
close > ma60
ma20 > ma60
ma60 > ma120
ma20_slope_20d > 0
close_new_high_60d_flag == true
close > ma30
abs(max_drawdown_120d) <= 0.55
red_k_ratio_20d >= 0.45
long_shadow_ratio_20d <= 0.65
```

扫描结果：

| 股票 | 稳健趋势日期数 | 突破关注候选数 | 第一次候选日期 | 最近候选日期 |
| --- | ---: | ---: | --- | --- |
| `301217.SZ` 铜冠铜箔 | 65 | 11 | `20260428` | `20260618` |
| `603256.SH` 宏和科技 | 96 | 12 | `20260122` | `20260617` |

这些日期不是最终买卖点，而是第一版 L4 策略召回候选。后续要用精确箭头日期、更多正负样本和回测来校准阈值。

说明：`max_abs_drawdown_60d = 0.40` 是针对高弹性趋势股的候选阈值，不是最终风控口径。更稳健的低回撤版本可以另建策略变体，例如 `strategy.steady_uptrend_breakout_watch_low_drawdown`，使用 `0.25` 或更低阈值。

## 6. 事件回测结果

使用 `workflows/jobs/steady_uptrend_breakout_event_backtest.py` 对候选事件做第一版事件回测：

```text
入场：信号日后第 1 个交易日开盘
出场：持有 N 个交易日后收盘
持有期：5 / 10 / 20 日
```

两只样本股票的候选事件回测结果：

| 持有期 | 可评估样本数 | 胜率 | 平均收益 | 年化折算收益 | 最大交易回撤 | 跳过事件 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 日 | 23 | 60.87% | 7.61% | 383.46% | -22.95% | 0 |
| 10 日 | 23 | 65.22% | 6.79% | 171.06% | -27.28% | 0 |
| 20 日 | 17 | 88.24% | 39.10% | 492.72% | -30.47% | 6 |

当前准入结论：

```text
仍保持 draft，不升级 test_tracking。
```

原因：

- 20 日样本数只有 17，小于默认准入要求 30。
- 20 日最大交易回撤约 -30.47%，超过默认准入阈值 -25%。
- 这里仍是两个强样本股票的样本内验证，不能代表策略已经具备生产资格。

## 7. L4 策略候选

策略草案：

```text
strategy.steady_uptrend_breakout_watch
```

当前状态：

```text
draft
```

原因：

- 样本只有两个，尚不足以通过策略准入。
- 部分技术指标尚未在基础数据层例行生产。
- 回测样本池和负样本尚未完成。

## 8. 下一步

建议下一步执行：

1. 用户补充红色箭头对应的精确交易日期。
2. 基础数据层补齐本形态族需要的技术指标。
3. 用两个样本的箭头日期跑 `IndividualStockStrategyResearchWorkflow`。
4. 扩展正样本和反例样本。
5. 扩展更多正样本和反例样本，重新跑事件回测。
6. 若样本数、胜率、收益和回撤满足准入，再把 L4 策略升级为 `test_tracking`。

新增样本后，下一轮优先补齐：

- 已有截图但没有精确日期的箭头交易日。
- `candlestick.red_k_ratio_20d`、`candlestick.green_k_ratio_20d`、`risk.frequent_break_ma30_60d`、`price_position.extension_from_ma30` 等趋势质量和反例过滤原语。
- `moving_average.close_above_ma30`、`risk.max_drawdown_120d_controlled`、`candlestick.red_k_ratio_20d_healthy`、`candlestick.long_shadow_ratio_20d_controlled` 已进入当前研究扫描和默认 registry，后续需要用更多样本继续校准阈值。
- 热门题材数据的来源和边界，先作为 `context_theme.hot_theme_active` 占位，不混入纯技术形态口径。
