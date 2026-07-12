# 稳健趋势 MVP 例行测试跟踪

## 定位

`strategy.steady_uptrend_mvp/v1` 是当前唯一例行选股策略，生命周期为 `test_tracking`。任务输出观察候选和分层审计，不发布正式 L5 `StrategySignal`。

旧 breakout、pre-breakout、v3、v3.1、v4 和五子池策略只允许由样本回放任务读取，不得配置日常选股 cron。

## 前置条件

例行任务必须在外部事实生产完成后运行。它从外部 `pub_data_quality_status` 只读解析最近一个完整交易日，随后自动生成并校验以下 artifact：

```text
kline.tsv
weekly_kline.tsv
stock_context.tsv
kline_manifest.json
stock_context_manifest.json
quality_status.json
```

K线使用 `qfq_asof`；成交额单位为 `thousand_cny`；成交量单位为 `lot`。质量状态必须覆盖扫描器要求的全部 `pub_*` 产品并达到 `ready/pass`。

## 手动执行

自动选择最近一个全部产品达到 `ready/pass` 的交易日：

```bash
cd /home/ubuntu/token_parse_sys_mvp
/usr/bin/python3 workflows/jobs/daily_steady_uptrend_mvp_tracking.py \
  --schedule-config-path configs/schedules/daily_steady_uptrend_mvp_tracking.json
```

复跑指定交易日：

```bash
/usr/bin/python3 workflows/jobs/daily_steady_uptrend_mvp_tracking.py \
  --schedule-config-path configs/schedules/daily_steady_uptrend_mvp_tracking.json \
  --date 20260710
```

## 输出目录

完整输入和分层审计：

```text
/home/ubuntu/token_parse_sys/runtime/strategy_tracking/runs/YYYYMMDD/
  strategy.steady_uptrend_mvp/v1/
```

面向人工查看的固定报告目录：

```text
/home/ubuntu/token_parse_sys/runtime/strategy_tracking/reports/YYYYMMDD/
  report.md
  candidates.json
  job_result.json
```

`reports/latest.json` 只指向最后一次成功运行。失败状态写入 `job_results/YYYYMMDD.json`，不会覆盖成功报告。

## 例行任务

```cron
30 0 * * 2-6 cd /home/ubuntu/token_parse_sys_mvp && /usr/bin/python3 workflows/jobs/daily_steady_uptrend_mvp_tracking.py --schedule-config-path configs/schedules/daily_steady_uptrend_mvp_tracking.json >> /home/ubuntu/token_parse_sys/runtime/strategy_tracking/cron.log 2>&1
```

任务使用非阻塞独占锁。同一交易日重复执行会重建相同版本目录并原子替换报告；第二个并发任务会失败退出。

## 输出检查

每次运行至少检查：

```text
status = test_tracking
output_kind = test_tracking_observation_candidates
strategy_id = strategy.steady_uptrend_mvp
version = v1
stage_counts 存在 S1-S5
data_dependency_versions 完整
reports/YYYYMMDD 下三个发布文件齐全
reports/latest.json 指向该交易日
```

失败时查看 `job_results/YYYYMMDD.json` 的 `failed_stage`、`error_type` 和 `error_message`。不允许删除锁文件绕过有效进程，不允许回退调用旧策略补位。进入 `active_production` 前必须完成 L2-L5 迁移、生命周期 gate 和用户审批。
