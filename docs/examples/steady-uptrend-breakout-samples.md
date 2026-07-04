# 样本组：稳健上升趋势突破

## 1. 样本来源

用户提供了两个 A 股截图样本：

- `603256.SH` 宏和科技
- `301217.SZ` 铜冠铜箔

红色箭头表示用户认为“这个级别可以介入或需要及时关注”的位置。

## 2. 形态理解

这两个样本共同表达的不是简单追高，而是一个更窄的形态族：

```text
稳健趋势股
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
```

扫描结果：

| 股票 | 稳健趋势日期数 | 突破关注候选数 | 第一次候选日期 | 最近候选日期 |
| --- | ---: | ---: | --- | --- |
| `301217.SZ` 铜冠铜箔 | 65 | 11 | `20260428` | `20260618` |
| `603256.SH` 宏和科技 | 96 | 12 | `20260122` | `20260617` |

这些日期不是最终买卖点，而是第一版 L4 策略召回候选。后续要用精确箭头日期、更多正负样本和回测来校准阈值。

说明：`max_abs_drawdown_60d = 0.40` 是针对高弹性趋势股的候选阈值，不是最终风控口径。更稳健的低回撤版本可以另建策略变体，例如 `strategy.steady_uptrend_breakout_watch_low_drawdown`，使用 `0.25` 或更低阈值。

## 6. L4 策略候选

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

## 7. 下一步

建议下一步执行：

1. 用户补充红色箭头对应的精确交易日期。
2. 基础数据层补齐本形态族需要的技术指标。
3. 用两个样本的箭头日期跑 `IndividualStockStrategyResearchWorkflow`。
4. 扩展正样本和反例样本。
5. 完成样本组回测，若满足准入，再把 L4 策略升级为 `test_tracking`。
