# 稳健上升趋势 S1-S5 MVP

## 1. 定位

`steady_uptrend_s1_s5_mvp_candidate_v1` 是候选研究策略，状态为 `research_only`。它只消费外部事实数据，用确定性规则完成质量过滤、成熟趋势过滤、结构召回、股性稳健性精筛和介入层筛选。

业务阶段不替代技术架构：

| 业务阶段 | 技术层职责 |
| --- | --- |
| S1-S4 数值与布尔计算 | L2 原语 |
| 趋势、结构、稳健性、上下文标签 | L3 标签快照 |
| S1-S5 组合顺序 | L4 StrategyDSL |
| 最终介入候选和解释 | L5 Signal Engine |
| 同口径历史回放 | L6 Backtest Engine |

当前实现位于 `stock_lobster.research` 和研究工作流，不修改旧 candidate v2/v3/v3_1/v4 的含义，也不代表生产晋升。输出中的 `candidates` 是研究候选，不是 L5 `StrategySignal`，不得被正式 L5/L6 或例行生产消费。进入 `test_tracking` 前必须另行迁移到 L2 原语、L3 标签、L4 StrategyDSL 和 L5 信号链路并通过生命周期审批。

## 2. 输入契约

扫描器需要三个只读 TSV：

### 日线和周线 K 线

无表头，列顺序固定：

```text
asset_id trade_date open high low close amount volume
```

- `trade_date` 使用 `YYYYMMDD`。
- OHLC 使用同一个 `qfq_asof` 价格基准。
- `amount` 使用 `thousand_cny`，`volume` 使用 `lot`。
- 周线只使用 `period_end_date <= signal_date` 的已完成周线。
- 每只股票至少需要 120 根日线和 64 根周线；120 根日线用于保证最近 60 日中的每一天都有可计算的当日 MA60，而不是额外增加上市年限偏好。

### 股票上下文

使用 `read_stock_signal_context_tsv` 支持的表头，MVP 必需字段为：

```text
asset_id trade_date name industry market list_status
total_mv avg_amount_20d
strong_industry_hit strong_concept_hit
strong_industry_names strong_concept_names
```

- `total_mv` 单位为万元；`1_000_000` 对应 100 亿元。
- `avg_amount_20d` 单位为千元；`200_000` 对应 2 亿元。
- `industry` 是最终唯一行业分组字段。
- 强势行业和概念布尔值由外部上下文查询提供，策略不自行生产行业事实。

强势上下文沿用 `workflows/jobs/daily_strategy_signal_production.py::_stock_context_sql()`：行业指数和概念指数分别取近 20 日收益率前 30% 且站上 MA20/MA60 的趋势强势集合，并与最近 20 日至少 3 次、最近 5 日至少 1 次进入热度 Top5 的集合合并。股票按信号日成分关系映射到 `strong_industry_hit` 和 `strong_concept_hit`。

## 3. 运行

先通过外部数据适配和研究导出任务生成输入及版本清单，再运行：

```bash
/opt/homebrew/bin/python3.12 workflows/jobs/steady_uptrend_s1_s5_mvp_scan.py \
  --kline-tsv-path /path/to/daily_kline.tsv \
  --weekly-kline-tsv-path /path/to/weekly_kline.tsv \
  --stock-context-tsv-path /path/to/stock_context.tsv \
  --kline-manifest-path /path/to/kline_manifest.json \
  --stock-context-manifest-path /path/to/stock_context_manifest.json \
  --quality-status-path /path/to/pub_data_quality_status.json \
  --strategy-config-path configs/strategies/steady_uptrend_s1_s5_mvp_candidate_v1.example.json \
  --signal-date 20260710 \
  --run-id steady-uptrend-s1-s5-20260710-r1 \
  --output-path /path/to/result.json \
  --markdown-output-path /path/to/result.md
```

扫描器会在读取大文件前校验：K 线为 `qfq_asof`，`amount=thousand_cny`，`vol=lot`，上下文 `avg_amount_20d=thousand_cny`、`total_mv=ten_thousand_cny`，manifest 路径、行数、SHA-256 和截止日与实际输入一致；同时要求日线、周线、daily basic、指标和股票基础资料的 `CN_A/stock` 质量状态在信号日均为 `ready/pass`。`data_dependency_versions` 由 manifest 版本和文件摘要自动生成，非 `research_only` 状态会直接拒绝。

## 4. 输出契约

JSON 是事实来源，包含：

- `strategy_id`、`version`、`status`、`run_id`、`signal_date`。
- `data_dependency_versions` 和完整 `policy`。
- 每层 `input`、`passed`、`rejected`。
- `blocker_counts`、每只股票的首个阻断层和全部阻断条件。
- 全部 `evaluations`、最终 `candidates`、`industry_groups`。
- 与 JSON 同源的 `markdown`。

主要阻断键：

| 阶段 | 阻断键 |
| --- | --- |
| S1 | `data_quality_unavailable`、`duplicate_daily_trade_date`、`duplicate_weekly_trade_date`、`weekly_asof_mismatch`、`not_normal_listing`、`st_stock`、`market_cap_below_minimum`、`avg_amount_20d_below_minimum` |
| S2 | `daily_mature_trend_failed`、`weekly_mature_trend_failed` |
| S3 | `no_structure_recalled` |
| S4 | `noisy_shadow_ma_flip_composite`、`low_red_k_ratio_60d`、`frequent_extreme_bearish_days_10d` |
| S5 | `context_strength_unavailable`、`ma20_deviation_unavailable` |

MA20 偏离等级为 `normal`、`20`、`30`、`40`、`50`。它只参与提醒和组内升序排序，不参与过滤。

## 5. 样本回放

使用同一批 `qfq_asof` 日线、周线和样本日期上下文回放：

| 样本 | 日期 | 结果 | 关键证据 |
| --- | --- | --- | --- |
| 铜冠铜箔 | `20260609` | 通过 S1-S5 | S3-A/B；上影线日 6，60 日总影线均值 52.62%，均线状态切换 3 次，未命中 S4 组合剔除；MA20 偏离 22.12% |
| 强瑞技术 | `20260608` | S4 剔除 | 上影线日 7，60 日总影线均值 57.33%，均线状态切换 6 次，命中 `noisy_shadow_ma_flip_composite` |
| 宏和科技 | `20260429` | 通过 S1-S5 | S3-A/B，S4 通过 |
| 宏和科技 | `20260522` | 通过 S1-S5 | S3-A，S4 通过 |
| 宏和科技 | `20260611` | 通过 S1-S5 | S3-A/B，S4 通过 |
| 宏和科技 | `20260409` | S3 未召回 | 距 60 日最高收盘价 `-10.94%`，低于当前 S3-A 的 `-10%` 边界，且未命中 S3-B/C |

`20260409` 的差异是已确认阈值下的真实结果，不在 MVP 实现阶段擅自放宽。后续若调整，应作为独立候选版本重新做正负样本评估。

## 6. 全市场回放

使用成交额修复后重新导出的 `20260710` 全市场数据：

| 阶段 | 输入 | 通过 | 剔除 |
| --- | ---: | ---: | ---: |
| S1 硬性质量过滤 | 5521 | 1482 | 4039 |
| S2 成熟趋势过滤 | 1482 | 166 | 1316 |
| S3 形态结构召回 | 166 | 106 | 60 |
| S4 股性稳健性精筛 | 106 | 90 | 16 |
| S5 介入层筛选 | 90 | 60 | 30 |

S4 的 16 只均命中 `noisy_shadow_ma_flip_composite`。S5 的 30 只均因 `context_strength_unavailable` 未进入最终介入候选。最终 60 只股票分布在 18 个规范行业中。

本次证据使用：

```text
run_id = steady-uptrend-s1-s5-20260710-r2
daily = v1:55628a08ff3a
weekly = v1:5c99c4f29502
context = v1:bd01edb31a4f
```

远端持久产物：

```text
/home/ubuntu/token_parse_sys/runtime/strategy_effect_eval/20260710/
  steady_uptrend_s1_s5_mvp_candidate_v1/result.json
  steady_uptrend_s1_s5_mvp_candidate_v1/result.md
  steady_uptrend_s1_s5_mvp_candidate_v1/kline_manifest.json
  steady_uptrend_s1_s5_mvp_candidate_v1/stock_context_manifest.json
  steady_uptrend_s1_s5_mvp_candidate_v1/quality_status.json
```

## 7. 验证注意事项

不得使用成交额修复前生成的旧 TSV。远端 `token_fetch` 的 `reports/amount_unit_repair_20260711.json` 显示 `20260427-20260710` 修复于 `2026-07-11 21:11` 完成；早于该时间的本地导出物需要重新生成。扫描前应检查导出清单时间和 `amount/(close*vol)` 单位一致性，避免把过期输入误判为策略问题。
