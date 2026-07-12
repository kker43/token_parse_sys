# 稳健上升趋势策略 v3 优化建议

评估窗口：`20260513` 到 `20260609`，共 20 个已完成 20 日持有期的信号日。

数据来源：

- `runtime/strategy_backtests/sl_eval_steady_uptrend_20_completed/results/evaluation_summary.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_20_completed/results/optimization_diagnostics.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_20_completed/results/topn_diagnostic_summary.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_20_completed/results/v3_research/scan_result.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_20_completed/results/v3_research/event_backtest.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_20_completed/results/v3_research/threshold_validation.json`

## 结论

当前 v1/v2 不适合直接上线。主要问题不是信号数量不足，而是信号池太宽，H10 胜率不足，且相对候选池等权没有优势。

| 版本 | 信号数 | H10 胜率 | H10 均值 | H10 中位数 | H10 相对候选池 | H20 均值 | H20 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| v1 pre_breakout | 745 | 48.32% | 3.77% | -0.82% | -3.17% | 11.87% | 58.88% |
| v2 weak_shape | 679 | 46.69% | 3.41% | -1.85% | -3.33% | 11.76% | 58.72% |

v2 剔除 66 个 v1 信号，但主要回撤来源仍被保留，说明当前弱形态过滤不够准。

v3 research-only 已按数据验证结果建设完成。v3 不替换 v1/v2，当前结论是可进入 `test_tracking` 观察，不适合直接进入 `active_production`。

由于该策略定位是突破短线逻辑，v3.1 之后的评估主轴调整为：H5 是主指标，H10 是延续性辅助指标，H20 只作为风险延续和尾部回撤参考。H20 均值不应作为否定短线策略的主依据。

60 个完整 H20 信号日扩窗后，市场温度硬过滤不再稳定，默认口径已调整为：市场温度只做评分/诊断，不做硬过滤；题材退潮仍保留硬过滤。

| 版本/分组 | 信号数 | H10 胜率 | H10 均值 | H10 中位数 | H20 均值 | H20 胜率 | 说明 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| v3 base breakout before filters | 454 | 49.78% | 1.71% | -0.02% | 7.61% | 56.73% | v3 基础突破召回 |
| v3 signal after filters | 102 | 56.86% | 4.28% | 4.48% | 13.68% | 61.86% | 市场温度、题材降权、TopN、冷却后信号 |
| v3 rejected breakout | 277 | 44.77% | -0.32% | -2.56% | 2.53% | 50.18% | 被 v3 硬过滤剔除的突破样本 |
| v3 observation diagnostic | 98 | 48.98% | 2.93% | -0.36% | 13.96% | 61.22% | 观察池 T+1 买入诊断，不作为买入信号 |

60 个完整 H20 信号日回测：

| 版本/分组 | 信号数 | 信号日数 | H5 均值 | H5 胜率 | H10 均值 | H10 胜率 | H20 均值 | H20 胜率 | 说明 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| v3 strict market hard filter | 97 | 13 | 1.07% | 52.58% | 3.57% | 54.64% | 13.68% | 61.86% | 市场温度硬过滤，样本偏少，H20 较强 |
| v3 recommended no market hard filter | 276 | 28 | 3.95% | 61.23% | 4.55% | 57.97% | 9.21% | 56.16% | 市场温度只评分/诊断，H5/H10 更稳 |
| candidate_pool equal weight | 1865 | 28 | 3.19% | NA | 6.42% | NA | 11.32% | NA | 候选池按信号日等权基准 |

继续测试观察池后，`observation_top5` 是当前更有研究价值的候选：

| 版本/分组 | 信号数 | H5 均值 | H5 胜率 | H10 均值 | H10 胜率 | H20 均值 | H20 胜率 | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| v3 signal | 276 | 3.95% | 61.23% | 4.55% | 57.97% | 9.21% | 56.16% | -55.38% |
| observation all | 198 | 3.50% | 55.56% | 6.13% | 58.08% | 10.99% | 60.61% | -51.78% |
| observation top5 | 123 | 5.08% | 60.98% | 10.41% | 69.92% | 18.29% | 70.73% | -51.78% |
| v3.1 observation top5 no-refill | 100 | 6.79% | 62.00% | 11.89% | 70.00% | 16.69% | 71.00% | -51.78% |

`observation_top5` 的口径是：使用 v3 research scan 的 `observation_candidates`，每日按 `v3_score` 取前 5 个，使用 T+1 开盘入场。该结果来自：

- `runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/results/v3_observation_top5/scan_result.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/results/v3_observation_top5/observation_event_backtest.json`

`observation_top5` 的回撤和过滤诊断来自：

- `runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/results/v3_observation_top5/drawdown_diagnostics.md`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/results/v3_observation_top5/risk_filter_diagnostics.md`

`v3.1 observation top5 no-refill` 的口径是：先按 v3 分数取每日 Top5，再对 `amount_ratio_20d < 1`、命中 `液冷服务器` / `第三代半导体` 的样本做后置剔除，且不补位。该结果来自：

- `configs/strategies/steady_uptrend_pre_breakout_watch_candidate_v3_1.example.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/results/v3_1_observation_top5/scan_result.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/results/v3_1_observation_top5/observation_event_backtest.json`

### observation_top5 风险过滤复核

`observation_top5` 当前优势主要体现在 H10/H20，但左尾风险仍然偏大：

- H10：123 笔，均值 10.41%，中位数 9.84%，胜率 69.92%，最大回撤 -46.46%，最差收益 -41.73%。
- H20：123 笔，均值 18.29%，中位数 12.43%，胜率 70.73%，最大回撤 -51.78%，最差收益 -49.60%。
- H10 最差信号日集中在 `20260528`、`20260521`、`20260527`。
- H10 最差个股里，`液冷服务器`、`第三代半导体`、`共封装光学(CPO)`、`机器人概念` 出现频率较高。

过滤变体复核结果：

| 过滤变体 | 信号数 | 信号日数 | H10 均值 | H10 胜率 | H10 最大回撤 | H10 最差收益 | H20 均值 | H20 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| observation_top5 | 123 | 27 | 10.41% | 69.92% | -46.46% | -41.73% | 18.29% | 70.73% |
| 剔除液冷服务器、第三代半导体 | 106 | 27 | 11.90% | 69.81% | -44.54% | -37.65% | 18.37% | 69.81% |
| 要求 amount_ratio_20d >= 1 | 109 | 26 | 11.08% | 71.56% | -44.54% | -37.65% | 18.82% | 71.56% |
| amount_ratio_20d >= 1，且剔除液冷服务器、第三代半导体 | 95 | 26 | 12.19% | 71.58% | -44.54% | -37.65% | 18.92% | 70.53% |
| 要求距离 60 日高点 -4% 到 -2%，且剔除液冷服务器、第三代半导体 | 63 | 26 | 13.85% | 71.43% | -44.54% | -37.65% | 20.22% | 69.84% |
| 剔除液冷服务器、第三代半导体、共封装光学(CPO) | 69 | 25 | 15.82% | 73.91% | -44.54% | -23.51% | 24.47% | 75.36% |

当前判断：

- `液冷服务器` 和 `第三代半导体` 可以进入下一版候选风险过滤。它们样本数不大，但确实命中了最差左尾，剔除后 H10/H20 稳定性略有改善。
- `amount_ratio_20d < 1` 可以作为降权或观察池排序惩罚。它不是灾难性条件，但整体质量弱于放量确认样本。
- 距离 60 日高点 `-4%` 到 `-2%` 比 `-6%` 到 `-4%` 略好，可以作为排序加分，不建议立刻硬过滤，否则样本从 123 降到 71 或 63。
- 剔除 `共封装光学(CPO)` 后结果最好，但这类题材在样本里也有大量正收益个股，直接剔除可能是窗口过拟合。当前只保留为风险诊断，不写入默认策略硬过滤。
- v3.1 正式扫描验证了一个重要细节：风险剔除不宜在 Top5 前补位执行。若剔除后继续用后排样本补满 Top5，H10 会被削弱；更稳的口径是 Top5 后剔除且不补位。

v3.1 正式回测结果：

| 版本 | 信号数 | H5 均值 | H5 胜率 | H10 均值 | H10 胜率 | H10 最差收益 | H20 均值 | H20 胜率 | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| observation_top5 | 123 | 5.08% | 60.98% | 10.41% | 69.92% | -41.73% | 18.29% | 70.73% | 基准观察池 |
| v3.1 no-refill | 100 | 6.79% | 62.00% | 11.89% | 70.00% | -37.65% | 16.69% | 71.00% | 短线主指标改善，H20 仅作风险参考 |

因此 v3.1 可以作为下一阶段短线观察池候选优先进入 `test_tracking`：它改善了 H5、H10 和 H10 左尾，符合突破短线策略的主目标。它仍不应直接进入 `active_production`，原因不是 H20 均值低于 v3，而是最大回撤仍偏大，且 `v3_score` 仍是研究评分，不是已批准的最终排序模型。

### v3.1 短线交易管理诊断

固定 v3.1 observation top5 no-refill 选股不变后，进一步测试短线交易管理。该诊断只改变入场/退出规则，不改变选股口径。

产物：

- `runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/results/v3_1_trade_management/diagnostics.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/results/v3_1_trade_management/diagnostics.md`

结果摘要：

| 交易管理规则 | 样本 | 跳过 | H5 均值 | H5 中位数 | H5 胜率 | 最差收益 | 最佳收益 | 止损数 | 止盈数 | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| baseline_h5 | 100 | 0 | 6.79% | 6.34% | 62.00% | -35.76% | 46.69% | 0 | 0 | 固定 H5 基准 |
| stop_loss_8 | 100 | 0 | 5.56% | 5.05% | 54.00% | -8.00% | 46.69% | 34 | 0 | 止损太紧，误杀较多 |
| stop_loss_10 | 100 | 0 | 6.68% | 5.99% | 61.00% | -10.00% | 46.69% | 21 | 0 | 当前最均衡 |
| stop_loss_12 | 100 | 0 | 6.78% | 6.34% | 62.00% | -12.00% | 46.69% | 12 | 0 | 收益接近基准，左尾收敛较弱 |
| stop10_take15 | 100 | 0 | 5.69% | 9.27% | 64.00% | -10.00% | 15.00% | 19 | 46 | 胜率/中位数高，但压制大赢家 |
| stop10_take20 | 100 | 0 | 6.11% | 6.34% | 62.00% | -10.00% | 20.00% | 20 | 30 | 仍压低均值 |
| gap5_stop10 | 97 | 3 | 6.55% | 5.85% | 60.82% | -10.00% | 46.69% | 21 | 0 | 高开过滤贡献有限 |
| gap8_stop10 | 99 | 1 | 6.80% | 6.13% | 61.62% | -10.00% | 46.69% | 21 | 0 | 与 stop_loss_10 接近 |

当前判断：

- `stop_loss_10` 是最值得继续验证的交易管理候选。它基本保留 baseline_h5 的 H5 均值，同时把最差收益从 -35.76% 收敛到 -10.00%。
- `stop_loss_8` 太紧，胜率和均值明显下降，容易把突破短线里的正常波动当成失败。
- 固定止盈不适合第一版规则。`take_profit_pct=15%/20%` 都会压制少数大赢家，而这类策略的收益结构正依赖大赢家抵消小亏损。
- 高开过滤在当前窗口贡献很小，只跳过 1 到 3 个样本，不建议先做硬过滤。
- 日线 OHLC 无法判断日内高低先后，因此交易管理诊断里的 `max_dd` 仍是偏保守的日线区间风险指标；评估止损效果时优先看 `worst_return`、均值、胜率和止损触发次数。

下一步建议把 `max_holding_days=5`、`stop_loss_pct=-0.10`、不设固定止盈作为 v3.1 的第一版短线交易管理候选，进入滚动窗口复核。

滚动稳定性复核已经补充到同一诊断产物中，按信号月份和市场 MA20 宽度分组：

| 分组 | 规则 | 样本 | H5 均值 | H5 中位数 | H5 胜率 | 最差收益 | 止损数 | 判断 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 202604 | baseline_h5 | 16 | 10.83% | 7.50% | 87.50% | -9.16% | 0 | 月度最强，止损贡献有限 |
| 202604 | stop_loss_10 | 16 | 10.62% | 7.50% | 87.50% | -10.00% | 2 | 基本不影响强月收益 |
| 202605 | baseline_h5 | 63 | 5.83% | 6.56% | 57.14% | -35.76% | 0 | 样本最多，左尾主要来源 |
| 202605 | stop_loss_10 | 63 | 6.08% | 6.56% | 57.14% | -10.00% | 15 | 止损价值最明确 |
| 202606 | baseline_h5 | 21 | 6.61% | 2.55% | 57.14% | -10.27% | 0 | 中位数偏弱 |
| 202606 | stop_loss_10 | 21 | 5.48% | 1.28% | 52.38% | -10.00% | 4 | 收敛左尾但牺牲部分收益 |
| breadth_ma20 < 35% | baseline_h5 | 40 | 3.86% | -0.65% | 47.50% | -13.17% | 0 | 弱市场环境明显拖累 |
| breadth_ma20 < 35% | stop_loss_10 | 40 | 3.13% | -1.53% | 45.00% | -10.00% | 12 | 止损不能修复弱环境胜率 |
| breadth_ma20 35%-55% | baseline_h5 | 22 | 6.81% | 6.91% | 68.18% | -35.76% | 0 | 收益可以，但存在极端左尾 |
| breadth_ma20 35%-55% | stop_loss_10 | 22 | 7.56% | 6.91% | 68.18% | -10.00% | 4 | 止损改善最优 |
| breadth_ma20 >= 55% | baseline_h5 | 38 | 9.87% | 8.52% | 73.68% | -17.96% | 0 | 当前最适配环境 |
| breadth_ma20 >= 55% | stop_loss_10 | 38 | 9.91% | 8.52% | 73.68% | -10.00% | 5 | 保持收益并收敛左尾 |

滚动结论：

- `stop_loss_10` 的主要价值是控制左尾，尤其是 202605；不是所有月份都提高收益。
- 市场宽度 `breadth_ma20 < 35%` 是当前最明确的短线弱环境：baseline H5 中位数 -0.65%、胜率 47.50%；加止损后中位数仍为 -1.53%、胜率 45.00%。
- 因此下一版不应简单靠止损解决弱环境，而应增加弱市场仓位控制：例如 breadth_ma20 < 35% 时每日 Top5 降到 Top2/Top3，或要求更强的放量/突破确认。
- 市场宽度 >= 55% 并不差，当前窗口里反而是最强环境，说明“大盘高温”不能简单硬过滤；短线突破更需要区分“强宽度承接”和“拥挤题材退潮”。

进一步按弱市场限额做候选池变体：

产物：

- `runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/results/v3_1_trade_management/weak_breadth_top2_param_diagnostics.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/results/v3_1_trade_management/weak_breadth_top2_param_diagnostics.md`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/results/v3_1_trade_management/scan_weak_breadth_top3.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/results/v3_1_trade_management/weak_breadth_top3_diagnostics.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/results/v3_1_trade_management/scan_weak_breadth_top2.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/results/v3_1_trade_management/weak_breadth_top2_diagnostics.json`

当前主口径已经收敛到参数化诊断任务：`workflows/jobs/steady_uptrend_trade_management_diagnostics.py --weak-breadth-ma20-threshold 0.35 --weak-breadth-top-n 2`。

规则：当 `market_temperature.breadth_ma20 < 0.35` 时，每个信号日只保留 v3.1 observation 排名前 N 个；其他市场宽度环境沿用 v3.1 observation top5 no-refill。旧的 `scan_weak_breadth_top2/top3` 文件是早期临时验证产物，后续应优先使用参数化诊断任务复现。

| 候选池变体 | 交易管理 | 样本 | H5 均值 | H5 中位数 | H5 胜率 | 最差收益 | 最佳收益 | 判断 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| v3.1 all | stop_loss_10 | 100 | 6.68% | 5.99% | 61.00% | -10.00% | 46.69% | 当前基准 |
| weak_breadth_top3 | stop_loss_10 | 92 | 7.19% | 6.91% | 63.04% | -10.00% | 46.69% | 有改善 |
| weak_breadth_top2 | stop_loss_10 | 84 | 7.53% | 7.35% | 65.48% | -10.00% | 46.69% | 当前最优候选 |

弱市场内部对比：

| 变体 | breadth_ma20 < 35% 样本 | H5 均值 | H5 中位数 | H5 胜率 | 止损数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| v3.1 all + stop_loss_10 | 40 | 3.13% | -1.53% | 45.00% | 12 |
| weak_breadth_top3 + stop_loss_10 | 32 | 3.70% | -0.65% | 46.88% | 9 |
| weak_breadth_top2 + stop_loss_10 | 24 | 3.73% | 0.33% | 50.00% | 7 |

当前判断：

- `weak_breadth_top2 + stop_loss_10` 是当前最有价值的 v3.2 候选方向。
- 它不是靠提高最强环境收益，而是减少弱市场低质量样本，使整体 H5 均值、胜率和中位数都改善。
- 这个规则仍不能直接上线，因为样本从 100 降到 84，需要更长历史和滚动窗口确认；但它比继续做固定止盈更符合当前数据证据。

参数敏感性复核：

产物目录：

- `runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/results/v3_1_trade_management/sensitivity/`

| 弱市场阈值/限额 | 样本 | H5 均值 | H5 中位数 | H5 胜率 | 最差收益 | 止损数 | breadth_ma20 < 35% 中位数 | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 不限额 | 100 | 6.68% | 5.99% | 61.00% | -10.00% | 21 | -1.53% | v3.1 基准 |
| breadth < 30%, top2 | 87 | 7.29% | 7.26% | 65.52% | -10.00% | 17 | 0.69% | 有效但弱市场定义偏窄 |
| breadth < 35%, top2 | 84 | 7.53% | 7.35% | 65.48% | -10.00% | 16 | 0.33% | 当前保守主候选 |
| breadth < 45%, top2 | 83 | 7.74% | 7.44% | 66.27% | -10.00% | 15 | 0.33% | 当前窗口略优，但样本证据更薄 |
| breadth < 35%, top1 | 73 | 8.18% | 7.95% | 67.12% | -10.00% | 13 | -1.28% | 过度收缩，弱市场内部中位数仍偏负 |
| breadth < 35%, top3 | 92 | 7.19% | 6.91% | 63.04% | -10.00% | 18 | -0.65% | 改善弱于 top2 |

更细市场宽度分桶显示，`breadth_ma20 < 35%` 的弱市场判断有数据支撑；`35%-45%` 这一段也偏弱，但当前只有 5 个基准样本：

| breadth_ma20 分桶 | 样本 | H5 均值 | H5 中位数 | H5 胜率 | 止损数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| < 30% | 33 | 4.28% | -1.79% | 45.45% | 10 |
| 30%-35% | 7 | -2.31% | -1.28% | 42.86% | 2 |
| 35%-45% | 5 | 0.16% | -10.00% | 40.00% | 3 |
| 45%-55% | 17 | 9.74% | 7.26% | 76.47% | 1 |
| >= 55% | 38 | 9.91% | 8.52% | 73.68% | 5 |

参数敏感性结论：

- `top2` 比 `top1` 更适合作为第一版规则。`top1` 虽然整体收益更高，但样本从 100 降到 70-78，且弱市场内部中位数没有稳定转正。
- `breadth_ma20 < 0.35 + top2` 是更稳健的 v3.2 保守候选。
- `breadth_ma20 < 0.45 + top2` 当前指标略优，适合作为 `test_tracking` 激进候选；但 `35%-45%` 分桶样本太少，不能直接作为唯一生产口径。

### 扩窗输入验证

为确认样本数量是否受 `stock_context.tsv` 日期范围限制，补齐了本地日线输入起点以来的上下文：

- 原上下文：`runtime/strategy_backtests/sl_eval_steady_uptrend_60_completed/input/stock_context.tsv`，覆盖 `20260311` 到 `20260608`。
- 补齐后上下文：`runtime/strategy_backtests/sl_eval_steady_uptrend_context_20250214_20260608/input/stock_context.tsv`，覆盖 `20250214` 到 `20260608`，共 78 个交易日、426647 行。
- 重跑 scan：`runtime/strategy_backtests/sl_eval_steady_uptrend_context_20250214_20260608/results/v3_1_observation_top5/scan_result.json`。
- 重跑交易管理：`runtime/strategy_backtests/sl_eval_steady_uptrend_context_20250214_20260608/results/v3_1_trade_management/weak_breadth_top2_diagnostics.json`。

验证结果：

| 对比项 | 原 60 日上下文 | 补齐上下文 | 是否一致 |
| --- | ---: | ---: | --- |
| candidate_pool | 1865 | 1865 | 是，ID 完全一致 |
| observation_candidates | 100 | 100 | 是，ID 完全一致 |
| signal_candidates | 119 | 119 | 是，ID 完全一致 |
| v3_rejected_candidates | 908 | 908 | 是，ID 完全一致 |
| 最早候选日期 | 20260427 | 20260427 | 是 |
| 最晚候选日期 | 20260608 | 20260608 | 是 |

弱市场 top2 + `stop_loss_10` 也完全复现：样本 84，H5 均值 7.53%，中位数 7.35%，胜率 65.48%，最差收益 -10.00%。

结论：当前样本数量不是 `stock_context.tsv` 从 20260311 才开始导致的。要继续扩充历史样本，下一步应导出更早的 `kline.tsv` 和匹配的上下文，而不是只继续补 `stock_context.tsv`。

进一步导出更早日线/周线后，已覆盖：

- 日线：`runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/input/kline.tsv`，覆盖 `20250102` 到 `20260707`，共 1977767 行。
- 周线：`runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/input/weekly_kline.tsv`，覆盖 `20230101` 到 `20260703`，共 972058 行。
- 上下文：`runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/input/stock_context.tsv`，覆盖 `20250102` 到 `20260608`，共 103 个交易日、560263 行。
- 重跑 scan：`runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/results/v3_1_observation_top5/scan_result.json`。
- 重跑交易管理：`runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/results/v3_1_trade_management/weak_breadth_top2_diagnostics.json`。

扩到 `20250102` 后，基础候选池只新增 1 个样本：

| 项目 | 原结果 | 扩到 20250102 后 | 变化 |
| --- | ---: | ---: | --- |
| candidate_pool | 1865 | 1866 | +1 |
| observation_candidates | 100 | 100 | 0 |
| signal_candidates | 119 | 119 | 0 |
| v3_rejected_candidates | 908 | 909 | +1 |

新增样本为 `20260514 000628.SZ 高新发展`，属于 `pre_breakout_watch`，但因 `pre_breakout_too_far_from_high` 被剔除，没有进入最终观察池。扩窗后的最终观察池和交易管理结果与原结果完全一致：弱市场 top2 + `stop_loss_10` 仍为样本 84，H5 均值 7.53%，中位数 7.35%，胜率 65.48%，最差收益 -10.00%。

因此当前最重要的结论变为：仅把历史输入扩到 2025 年不能增加 v3.1 最终观察池样本。继续扩样本需要二选一：

- 继续向 2024 或更早扩事实输入，但前提是补齐 `token_daily_basic`、同花顺行业/概念和上下文口径。
- 或者在现有 2025-2026 数据内建立“研究用宽召回池”，专门收集 borderline/rejected 样本，不能把它直接等同于可交易观察池。

### 研究用宽召回池验证

为继续积累人工样本，但不放宽正式观察池，新增 `steady_uptrend_wide_recall_pool` 研究任务。该任务只从 `v3_rejected_candidates` 中抽取有研究价值的边界样本，并写明 `pool_semantics=research_only_wide_recall_not_trade_signal`。

产物：

- `runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/results/v3_1_wide_recall_pool/wide_recall_candidates.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/results/v3_1_wide_recall_pool/wide_recall_event_backtest.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/results/v3_1_observation_top5/observation_event_backtest.json`
- `runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/results/v3_1_observation_top5/signal_event_backtest.json`

宽召回池当前共 138 条，覆盖 `20260427` 到 `20260608` 的 28 个交易日：

| 研究 bucket | 样本数 | 含义 |
| --- | ---: | --- |
| near_pre_breakout | 78 | 接近预突破，但被 `pre_breakout_too_far_from_high` 或 `pre_breakout_too_close_to_high` 剔除 |
| risk_context_rejected | 60 | 命中 `blocked_risk_context` 或 `fading_context_without_preferred_rotation` |

宽召回池不等于策略信号。它保留 `review_idx`、`suggested_review_code` 和完整 1-8 数字标签说明，用于后续人工确认正负样本。

同口径事件回测对比：

| 候选池 | 样本 | H5 均值 | H5 中位数 | H5 胜率 | H10 均值 | H10 中位数 | H10 胜率 | H20 均值 | H20 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| signal_candidates | 119 | 3.46% | 1.26% | 58.82% | 6.39% | 4.66% | 60.50% | 12.61% | 64.71% |
| observation_candidates | 100 | 6.79% | 6.34% | 62.00% | 11.89% | 11.22% | 70.00% | 16.69% | 71.00% |
| wide_recall_candidates | 138 | 3.21% | 1.81% | 60.14% | 5.63% | 3.23% | 55.07% | 17.88% | 68.12% |

宽召回池内部：

| bucket | 样本 | H5 均值 | H5 中位数 | H5 胜率 | H10 均值 | H10 中位数 | H20 均值 | H20 中位数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| near_pre_breakout | 78 | 2.89% | 1.47% | 58.97% | 7.38% | 8.92% | 15.44% | 10.02% |
| risk_context_rejected | 60 | 3.61% | 2.47% | 61.67% | 3.36% | 0.05% | 21.06% | 16.11% |

当前判断：

- 正式 `observation_candidates` 的 H5/H10 明显优于宽召回池，说明 v3.1 过滤对短线目标有效。
- 宽召回池 H20 不弱，说明被剔除样本里存在中期走强个股，但它不符合当前突破短线的首要目标。
- `near_pre_breakout` 更像“入场太早/太近，需要确认触发”的样本，应优先用于学习突破确认条件。
- `risk_context_rejected` 的 H20 较强，但 H10 中位数接近 0，适合拆分行业轮动错杀和退潮风险，而不是直接取消风险上下文过滤。
- 下一轮人工打标可以优先从 `wide_recall_candidates.json` 的 `review_idx` 低位开始，每次按日期顺序确认 20 到 30 条。


## 关键发现

### 1. 预突破更适合作为观察池，不适合作为直接买入信号

H10 中位数为负，H20 均值转强。这说明信号有一定中期延续性，但 T+1 直接进入的短期体验较差。

建议：

- `pre_breakout` 先进入观察池。
- 只有后续出现确认触发，才转为信号。
- 确认触发包括：突破 60 日高点、收盘重新站上高点附近、放量不过热、回撤不破 MA10/MA20。

### 2. 大盘高温阶段不是最优入场环境

按信号日大盘温度分桶后，市场 20 日平均涨幅和 MA20 宽度越高，后续 H10 不一定更好。

v1 诊断：

- 市场 20 日平均收益低位组：H10 均值 20.35%，胜率 82.49%。
- 市场 20 日平均收益中位组：H10 均值 -0.56%，胜率 41.02%。
- 市场 20 日平均收益高位组：H10 均值 1.10%，胜率 42.43%。

建议把大盘温度拆成三档：

- `cold_rebound`：市场刚降温或回撤后，筛选仍保持强势的个股，可正常准入。
- `neutral`：正常准入，但限制每日候选数量。
- `overheated`：市场宽度和成交热度过高时，不新增预突破信号，只保留已确认突破或高质量观察。

### 3. 行业轮动比单个股形态更关键

H10 表现较差的概念：

- `算力租赁`：均值 -12.54%，胜率 12.50%。
- `数据中心`：均值 -9.44%，胜率 17.90%。
- `储能`：均值 -6.44%，胜率 27.50%。
- `华为概念`：均值 -6.41%，胜率 27.30%。

H10 表现较好的概念：

- `PCB概念`：均值 13.14%，胜率 71.90%。
- `存储芯片`：均值 11.54%，胜率 55.50%。
- `先进封装`：均值 6.82%，胜率 59.50%。
- `光纤概念`：均值 6.80%，胜率 57.80%。

建议新增行业/概念轮动状态：

- `leader_accelerating`：继续准入。
- `leader_after_cooling`：优先准入，适合从观察池转信号。
- `crowded_hot`：降权或限制每日数量。
- `fading_hot`：不准入。

### 4. 弱形态过滤需要重做，多个直觉硬过滤不被当前数据支持

分桶结果显示，`large_bearish_body_ratio_20d >= 30%` 在该窗口并不差，v2 直接硬过滤会误杀一部分有效样本。

初始诊断中曾怀疑以下字段适合硬过滤，但 v3 建设后的全量验证不支持直接硬剔除：

- `red_k_ratio_20d < 0.50`：H10 均值 5.72%，胜率 56.52%；H20 均值 10.83%，胜率 65.22%。
- `amount_ratio_20d >= 2.5`：H10 均值 4.49%，胜率 58.82%；H20 均值 3.35%，胜率 54.90%。
- `single_bull_bar_return_share_20d` 在 0.25 到 0.40 的样本 H10/H20 不差。
- `ma30_deviation_pct >= 0.30` 的 H20 均值 9.36%，胜率 58.42%，不适合直接硬剔除。

20 日窗口支持的硬过滤是：

- `fading_context_without_preferred_rotation`：H10 均值 -6.51%，胜率 32.89%；H20 均值 -9.39%，胜率 28.95%。
- `market_avg_return_20d >= 0.03` 的市场温度过热样本：H10 均值 0.54%，胜率 46.56%；H20 均值 3.26%，胜率 51.15%。

60 日窗口复核后，市场温度硬过滤证据不稳定：

- `market_breadth_ma20_overheated` 剔除组 H10 均值 5.45%，胜率 57.95%，并不差。
- `market_avg_return_20d_overheated` 剔除组 H10 均值 3.84%，胜率 54.20%，与保留组差距不够稳定。
- 去掉市场温度硬过滤后，v3 H10 从 3.57% / 54.64% 提升到 4.55% / 57.97%，信号数从 97 增加到 276。

因此 v3 把个股量比、红柱比例、MA30 乖离、单根大阳柱贡献、市场温度全部降级为评分惩罚和诊断字段；硬过滤只保留题材退潮条件。

### 5. 重复信号需要冷却期

同一股票连续多日入选会放大回测样本，也会放大实盘风险。10 日冷却期可以减少重复暴露，并略微改善 H10 均值。

v1：

- 原始 H10：745 笔，均值 3.77%，胜率 48.32%。
- 10 日冷却：225 笔，均值 4.53%，胜率 49.33%。

建议：

- 同一股票 10 个交易日内只允许产生一次正式信号。
- 观察池可以连续记录状态，但不能重复生成买入信号。
- 如果前一信号尚未走完持有期，后续信号只更新观察理由，不新增仓位。

## v3 建议口径

### 质量层

- 正常上市、非 ST。
- 总市值和 20 日均成交额沿用当前阈值。
- `red_k_ratio_20d` 当前只做诊断和评分，不做 v3 硬过滤。
- `amount_ratio_20d` 当前只做诊断和评分，不做 v3 硬过滤。
- `max_turnover_rate_20d` 继续保留。

### 趋势层

- 周线趋势仍保留。
- MA30 稳健性保留。
- MA30 乖离进入评分惩罚，不做 v3 硬过滤。

### 预突破层

- 不建议离高点太近时直接买入。
- 优先区间：距离 60 日高点约 2% 到 6%。
- 距高点小于 2% 但未突破，应等待确认突破。

### 行业轮动层

- 剔除纯指数成分概念，例如 `中证500成份股`、`上证180成份股`，不能作为强题材依据。
- 概念强度加入最近 5 日变化，识别加速、降温和拥挤。
- 对 `fading_hot` 概念降权，尤其是已经高热后回落的算力、数据中心、储能类。

### 大盘温度层

- 市场过热时不扩大候选池。
- 当前不启用市场温度硬过滤。
- `breadth_ma20`、`avg_return_20d`、`avg_amount_ratio` 只进入评分惩罚和诊断。
- 市场冷却后，只筛选仍在 MA20/MA30 上方并且行业未退潮的个股。
- 市场弱势时，预突破只进入观察池，不转正式信号。

### 排序层

当前 `setup_score` 不可直接用于上线 Top-N，但可作为 v3 诊断起点。

需要新增多维排序：

```text
技术稳健分
+ 行业轮动分
+ 概念热度变化分
+ 大盘温度适配分
- 拥挤度惩罚
- 过热放量惩罚
- 重复信号惩罚
```

## 下一步验证

1. 已实现 v3 research-only 配置，不替换 v1/v2。
2. 已完成同样窗口 20 个已完成信号日复测。
3. 已对 H5/H10/H20 分别评估。
4. 已扩展到 60 个完整 H20 信号日，并验证市场温度硬过滤应降级为诊断。
5. 已验证 `observation_top5` 明显优于直接突破信号，下一步应围绕观察池做分日期稳定性、最大回撤来源、人工样本复核。
6. 当前仍不能进入 `active_production`：最大回撤过大，且 `v3_score` 仍是研究评分，不是已批准的最终排序模型。
7. 已实现并回测 v3.1 research-only 短线观察池：以 `observation_top5` 为主线，`amount_ratio_20d < 1`、命中 `液冷服务器` / `第三代半导体` 的样本在 Top5 后剔除且不补位。按突破短线口径，H5 是主指标，H10 是辅助确认，v3.1 的短线表现优于 v3 observation_top5。
8. 暂不把 `共封装光学(CPO)` 写入默认硬过滤；它在本窗口剔除后收益最好，但过拟合风险高，应先用更长历史和滚动窗口复核。
9. 已完成第一轮 v3.1 短线交易管理诊断：`stop_loss_pct=-0.10` 基本保留 H5 均值，并显著收敛最差收益；固定止盈和高开硬过滤暂不优先。
10. 下一步应做滚动窗口稳定性：分别比较 `observation_top5`、`v3.1 no-refill`、`v3.1 no-refill + -10% stop`、`CPO 仅诊断` 四组在不同月份、不同市场温度下的 H5、H10、最大回撤和最差收益；H20 仅保留为风险延续参考。
11. 已新增研究用宽召回池，专门积累 `near_pre_breakout` 和 `risk_context_rejected` 的人工样本；该池当前不准入正式交易观察池，只用于错杀分析、边界样本标注和下一轮规则优化。
