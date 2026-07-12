# 20260709 刷新数据后的样本策略复盘

## 口径

- 样本库：`configs/research_samples/steady_uptrend_breakout_samples.json`
- 样本范围：18 个样本标的，34 个日线事件；其中 23 个正向召回目标、4 个硬负样本、2 个低价值/排除样本、4 个等待型边界样本、1 个历史非标准负向标签。
- 行情输入：远端 `runtime/strategy_signal_production/20260708/input/` 的 `qfq_asof` 日线和周线输入。
- 上下文输入：按样本覆盖的 24 个交易日重新导出的全市场 `stock_context`，共 131,815 行。
- 明细文件：`docs/research_reports/20260709-refreshed-sample-strategy-analysis.csv`

说明：v3/v3.1 本次按样本日期做同日静态排名和拒绝原因分析；完整历史 cooldown 精确回放需要导出 20260105-20260708 全交易日上下文，本次没有强行等待完整区间导出。

## 总体结论

当前几个策略和样本库的主矛盾不是复权问题，而是策略语义过窄。

现有 `breakout_v1` / `pre_breakout_v1` / `v3` / `v3.1` 都没有召回 23 个正向样本中的任何一个；但它们会召回部分硬负、低价值或等待型样本。也就是说，刷新 qfq 数据解决了除权导致的价格/均线失真，但没有解决“样本形态族”和“当前策略候选定义”不一致的问题。

## 策略表现

| 策略 | 正样本召回 | 硬负样本误召回 | 低价值/排除误召回 | 等待型召回 | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| `breakout_v1` | 0/23 | 1/4 | 0/2 | 0/4 | 漏掉全部正样本，同时误召回强瑞技术。 |
| `breakout_v2_weak_shape` | 0/23 | 1/4 | 0/2 | 0/4 | 弱形态过滤没有挡住强瑞技术，也没有改善正样本召回。 |
| `pre_breakout_v1` | 0/23 | 1/4 | 1/2 | 2/4 | 能解释周三误召回：领先股份、杰华特 20260707、冰轮环境、天创时尚都被纳入。 |
| `pre_breakout_v3` | 0/23 | 1/4 | 1/2 | 0/4 | 挡住领先股份、冰轮环境、天创时尚，但仍放过杰华特 20260707 和强瑞技术。 |
| `pre_breakout_v3_1` | 0/23 | 1/4 | 0/2 | 0/4 | 比 v3 更好地挡住杰华特 20260707，但仍放过强瑞技术。 |

## 正样本为什么漏掉

23 个正向事件中，只有 8 个通过 `daily_quality_pass` 和 `steady_uptrend`。主要阻断原因：

- `pre_breakout_ma30_sustained_failed`：13 次。很多高价值样本是启动、回调再加速、同段 follow-through，不满足当前“持续站稳 MA30 后的 pre-breakout”定义。
- `avg_amount_20d_below_threshold`：10 次。当前 `min_avg_amount_20d=2000000000` 对样本中的中小市值强趋势标的太硬。
- `trend_stability_failed`：6 次。早期反转、长期盘整后刚突破的样本常被这个规则挡住。
- `amount_ratio_20d` 不足：多只后续证明很强的样本是温和放量或沿 MA10/MA20 稳步上行，不满足突破侧的 `min_amount_ratio_20d=1.5`。

因此，不能简单把这些正样本塞进现有 `pre_breakout` 或 `breakout`。更合理的是把策略拆成子类：长期盘整早期突破、回调再加速、稳健 MA10/MA20 walk-up 新高、强趋势 follow-through、早期反转启动。

## 周三候选复盘

- 领先股份 `603991.SH`：`pre_breakout_v1` 会召回；v3/v3.1 因 `pre_breakout_too_close_to_high` 挡住。用户判断“不应该召回”与 v3/v3.1 一致。
- 杰华特 `688141.SH`：20260609 是中价值正样本，但 20260707 是低价值/排除；`pre_breakout_v1` 和 v3 都会召回 20260707，v3.1 用 `amount_ratio_below_v3_threshold` 挡住。v3.1 更贴近用户修正。
- 冰轮环境 `000811.SZ`：`pre_breakout_v1` 会召回；v3/v3.1 因 `pre_breakout_too_far_from_high` 挡住，更符合“高位盘整但还要等”。
- 天创时尚 `603608.SH`：`pre_breakout_v1` 会召回；v3/v3.1 因 `pre_breakout_too_close_to_high` 挡住，更符合“V 形偏陡，等 W 形/平台”。
- 强瑞技术 `301128.SZ`：所有 breakout/v3 信号侧仍会误召回，这是当前最需要补的硬负样本过滤。它的问题不是 qfq，而是影线噪声、MA 黏合后破位、趋势质量不稳没有被现有弱形态过滤识别出来。

## 标注体系问题

样本里还有一个历史事件 `stbu_600105_20260624_overextended_negative` 使用 `event_class=negative_after_close_recall`，没有落到当前统计用的固定目标类。建议后续修正到现有分类之一，例如 `borderline_negative_recall` 或 `weak_or_excluded_attention`，不要继续扩散新的顶层事件类。

## 下一步

1. 不建议直接把 v3.1 升成正式策略。它对周三误召回更好，但正样本召回仍为 0/23。
2. 先新增一个 `wide_recall_pool` 或样本评估专用候选池，用更宽的日线技术条件覆盖正样本，再由子类标签做排序/降权。
3. 单独补 `risk_state.noisy_ma_convergence_breakdown` / `single_bull_then_bearish_pullback` / `rest_duration_too_short` 这类负向原语，优先处理强瑞技术和领先股份。
4. v3.1 的 `amount_ratio_below_v3_threshold` 对杰华特 20260707 有效，但它也会挡住部分温和放量高价值样本，不能作为通用硬过滤，只适合放在“加速后缺少盘整”的风险分支里。
