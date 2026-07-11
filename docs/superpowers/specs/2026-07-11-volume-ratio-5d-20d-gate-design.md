# 5/20 日成交量比统一门槛设计

## 目标

将现有策略中用于硬阻断的成交额量比统一替换为上游已发布指标：

```text
volume_ratio_5d_20d = 最近 5 个交易日平均成交量 / 最近 20 个交易日平均成交量
通过条件：volume_ratio_5d_20d >= 1.2
```

`amount_ratio_20d` 和 `amount_ratio_prev_20d` 继续计算、持久化到研究报告并参与评分，但不再作为突破、预突破或 v3/v3.1 的硬门槛。

## 数据边界

- 权威事实数据由 `token_fetch` 生产。
- Stock Lobster 只消费 `pub_stock_daily_indicator` 中的 `volume_ratio_5d_20d`。
- 不在 Stock Lobster 内重新生产或修复该指标。
- 指标版本沿用上游发布契约中的 `legacy_v1/default`。

## 数据流

```text
token_fetch.token_daily_details.vol
  -> short_term_anomaly_daily.volume_ratio_5d_20d
  -> pub_stock_daily_indicator
  -> StockSignalContext.volume_ratio_5d_20d
  -> TrendBreakoutMetrics.volume_ratio_5d_20d
  -> breakout / pre_breakout / v3 / v3.1 gate
```

策略生产和研究批量导出必须使用相同字段与缺失值语义。

## 策略语义

统一替换以下现有硬门槛：

- `breakout_v1`、`breakout_v2` 的 `min_amount_ratio_20d = 1.5`。
- `pre_breakout_v1` 的 `min_pre_breakout_amount_ratio_20d = 0.8`。
- `pre_breakout_v3_1` 的 `min_amount_ratio_20d = 1.0`。
- 代码、配置、阻断原因、报告列和测试中所有承担硬门槛职责的同类口径。

统一替换为：

```text
min_volume_ratio_5d_20d = 1.2
```

阻断原因统一为 `volume_ratio_5d_20d_below_1.2`。字段缺失时记录 `volume_ratio_5d_20d_missing`，不得默认通过。

五类前置召回子池继续把量能作为评分信息，不增加第二套成交额量比硬门槛。

## 兼容与迁移

- 保留 `TrendBreakoutMetrics.amount_ratio_20d` 和 `amount_ratio_prev_20d`，避免破坏已有研究报告。
- 新增 `volume_ratio_5d_20d` 字段，旧 TSV 缺少该列时必须明确失败或由兼容读取器返回缺失状态，不能填充为 1。
- 配置加载只接受新门槛承担硬过滤；旧字段可以保留在历史 artifact 中，但活动配置不得继续引用。
- Markdown、CSV 和 JSON 报告同时输出三种量比，名称不得简写成含义不明的“量比”。

## 测试与验收

1. 单元测试先证明 `1.19` 被拒绝、`1.20` 通过、缺失值被拒绝。
2. 数据读取测试证明上游字段进入 `StockSignalContext` 和 `TrendBreakoutMetrics`。
3. 配置扫描确认活动策略不存在承担硬门槛的 `min_amount_ratio_20d` 或 `min_pre_breakout_amount_ratio_20d`。
4. 重新导出样本上下文并复盘 23 个正样本、4 个硬负样本。
5. 重新运行 2026-07-10 全市场扫描，输出每层数量及候选差异。
6. 远程完整测试、JSON 校验和正式策略任务全部通过后部署。

## 非目标

- 本次不调整 MA30、换手率、行业概念、盘整和硬负形态阈值。
- 本次不将五类研究子池直接晋升为正式生产策略。
- 本次不修改上游 `volume_ratio_5d_20d` 的事实计算公式。
