# 研究用日线和周线批量导出

## 目标

`research_kline_batch_export.py` 用于从外部事实数据库只读导出策略研究需要的 `kline.tsv` 和 `weekly_kline.tsv`。

它只读取 `token_daily_details` 和 `token_weekly_details`，不生产、修复或修改权威事实数据。

## 手动执行

```bash
python workflows/jobs/research_kline_batch_export.py \
  --mysql-config-path ops/env/external_mysql.json \
  --daily-start-date 20250102 \
  --daily-end-date 20260707 \
  --weekly-start-date 20230101 \
  --weekly-end-date 20260703 \
  --daily-output-path runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/input/kline.tsv \
  --weekly-output-path runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/input/weekly_kline.tsv \
  --manifest-path runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/input/kline_manifest.json
```

## 输出

- `kline.tsv`：无表头日线 TSV，字段顺序为 `ts_code, trade_date, open, high, low, close, amount`。
- `weekly_kline.tsv`：无表头周线 TSV，字段顺序同日线。
- `kline_manifest.json`：记录源表、日期范围、行数和输出路径。

## 稳健上升趋势扩窗结果

当前已验证扩到 `20250102` 后：

- 日线行数：1977767
- 周线行数：972058
- v3.1 `candidate_pool_count` 从 1865 增加到 1866
- v3.1 `observation_candidate_count` 仍为 100
- 新增基础候选 `20260514 000628.SZ` 因 `pre_breakout_too_far_from_high` 被剔除

结论：仅扩到 2025 年不会增加 v3.1 最终观察池样本。若继续扩样本，需要补齐 2024 或更早的基础上下文，或者在现有数据内建立研究用宽召回池。
