# 稳健趋势 MVP 例行测试跟踪

## 定位

`strategy.steady_uptrend_mvp/v1` 是当前唯一例行选股策略，生命周期为 `test_tracking`。任务输出观察候选和分层审计，不发布正式 L5 `StrategySignal`。

旧 breakout、pre-breakout、v3、v3.1、v4 和五子池策略只允许由样本回放任务读取，不得配置日常选股 cron。

## 前置条件

例行扫描必须在外部事实生产完成后运行，并取得以下只读 artifact：

```text
kline.tsv
weekly_kline.tsv
stock_context.tsv
kline_manifest.json
stock_context_manifest.json
quality_status.json
```

K线使用 `qfq_asof`；成交额单位为 `thousand_cny`；成交量单位为 `lot`。质量状态必须覆盖扫描器要求的全部 `pub_*` 产品并达到 `ready/pass`。

## 标准命令

调度器将 `trade_date` 展开到 `configs/schedules/daily_steady_uptrend_mvp_tracking.json` 的输入和输出目录，然后执行：

```bash
python3 workflows/jobs/steady_uptrend_s1_s5_mvp_scan.py \
  --kline-tsv-path "$INPUT_ROOT/kline.tsv" \
  --weekly-kline-tsv-path "$INPUT_ROOT/weekly_kline.tsv" \
  --stock-context-tsv-path "$INPUT_ROOT/stock_context.tsv" \
  --kline-manifest-path "$INPUT_ROOT/kline_manifest.json" \
  --stock-context-manifest-path "$INPUT_ROOT/stock_context_manifest.json" \
  --quality-status-path "$INPUT_ROOT/quality_status.json" \
  --strategy-config-path configs/strategies/steady_uptrend_mvp.json \
  --signal-date "$TRADE_DATE" \
  --run-id "steady-uptrend-mvp-v1-$TRADE_DATE" \
  --output-path "$OUTPUT_ROOT/current.json" \
  --markdown-output-path "$OUTPUT_ROOT/current.md"
```

## 输出检查

每次运行至少检查：

```text
status = test_tracking
output_kind = test_tracking_observation_candidates
strategy_id = strategy.steady_uptrend_mvp
version = v1
stage_counts 存在 S1-S5
data_dependency_versions 完整
```

失败时保留输入 manifest 和错误结果，不允许回退调用旧策略补位。进入 `active_production` 前必须完成 L2-L5 迁移、生命周期 gate 和用户审批。
