# 研究用股票上下文批量导出

## 目标

`research_stock_context_batch_export.py` 用于为策略研究和历史回测批量生成 `stock_context.tsv`。

它只复用 `daily_strategy_signal_production.py` 中现有的只读 `stock_context` 查询口径，不生产权威事实数据，不修改外部数据库。

## 使用场景

当已有 `kline.tsv` 和 `weekly_kline.tsv` 覆盖更长历史，但 `stock_context.tsv` 只覆盖较短日期范围时，先用本工作流补齐上下文，再重新运行研究扫描和回测。

注意：当前实现复用每日策略生产的单日上下文 SQL，并按交易日循环执行。该口径适合补小段缺口或验证日期覆盖，不适合一次性导出数百个交易日。远程实测约 7 个交易日生成 38315 行耗时接近 3 分钟；大范围扩窗应优先建设区间批处理 SQL，或先导出更早的 `kline.tsv` 后确认真实瓶颈。

## 手动执行

按日期区间导出：

```bash
python workflows/jobs/research_stock_context_batch_export.py \
  --mysql-config-path ops/env/external_mysql.json \
  --start-date 20260101 \
  --end-date 20260608 \
  --output-path runtime/strategy_backtests/sl_eval_steady_uptrend_extended/input/stock_context.tsv \
  --manifest-path runtime/strategy_backtests/sl_eval_steady_uptrend_extended/input/stock_context_manifest.json
```

按指定交易日导出：

```bash
python workflows/jobs/research_stock_context_batch_export.py \
  --mysql-config-path ops/env/external_mysql.json \
  --trade-date 20260427 \
  --trade-date 20260428 \
  --output-path runtime/strategy_backtests/sl_eval_steady_uptrend_extended/input/stock_context.tsv \
  --manifest-path runtime/strategy_backtests/sl_eval_steady_uptrend_extended/input/stock_context_manifest.json
```

## 输出

- `stock_context.tsv`：合并后的多日上下文文件，字段与每日策略生产的 `input/stock_context.tsv` 一致。
- `stock_context_manifest.json`：记录日期列表、总行数、每个交易日行数和源查询口径。

## 后续回测链路

生成更长 `stock_context.tsv` 后，再运行：

```bash
python workflows/jobs/steady_uptrend_v3_research_scan.py \
  --kline-tsv-path runtime/strategy_backtests/sl_eval_steady_uptrend_extended/input/kline.tsv \
  --weekly-kline-tsv-path runtime/strategy_backtests/sl_eval_steady_uptrend_extended/input/weekly_kline.tsv \
  --stock-context-tsv-path runtime/strategy_backtests/sl_eval_steady_uptrend_extended/input/stock_context.tsv \
  --strategy-config-path configs/strategies/archive/steady_uptrend/steady_uptrend_pre_breakout_watch_candidate_v3_1.example.json \
  --output-path runtime/strategy_backtests/sl_eval_steady_uptrend_extended/results/v3_1_observation_top5/scan_result.json \
  --start-date 20260101
```

然后使用 `steady_uptrend_trade_management_diagnostics.py` 对 `observation_candidates` 做交易管理和弱市场限额复核。

## 已验证边界

稳健上升趋势 v3.1 扩窗验证中，已将 `stock_context.tsv` 从 `20260311-20260608` 补齐到 `20250214-20260608`。

结果显示 scan 结果完全一致：

- `candidate_pool_count`: 1865
- `observation_candidate_count`: 100
- 最早候选日期仍为 `20260427`
- `observation_candidates` 的股票和日期与原结果完全一致

因此当前 v3.1 样本数量不是短上下文文件造成的。下一步要扩充历史样本，应补更早的 `kline.tsv` 和匹配上下文，而不是继续单独补 `stock_context.tsv`。
