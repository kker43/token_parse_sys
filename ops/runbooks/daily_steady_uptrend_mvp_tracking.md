# 稳健趋势 MVP 例行测试跟踪

## 定位

`strategy.steady_uptrend_mvp/v1` 是当前唯一例行选股策略，生命周期为 `test_tracking`。任务输出观察候选和分层审计，不发布正式 L5 `StrategySignal`。

旧 breakout、pre-breakout、v3、v3.1、v4 和五子池策略只允许由样本回放任务读取，不得配置日常选股 cron。

## 前置条件

例行任务必须在外部事实生产完成后运行。它通过精确日期查询从外部 `pub_data_quality_status` 只读解析最近一个日频产品完整的交易日。周线质量也由该上游视图正式发布：周期结束日可随同精确日期查询取得，非周期结束日读取不晚于信号日的最近周线质量行。下游不直接统计周线事实表，也不构造替代质量状态。随后自动生成并校验以下 artifact：

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

## HTML 邮件推送

邮件任务独立于选股计算，只消费 `reports/latest.json`、对应的 `job_result.json` 和运行目录中的 `result.json`。SMTP 失败不会修改选股 artifact，也不会把已成功的选股运行改成失败。

手动发送最新一份尚未投递的报告：

```bash
cd /home/ubuntu/token_parse_sys_mvp
/usr/bin/python3 workflows/jobs/daily_steady_uptrend_mvp_email.py \
  --schedule-config-path configs/schedules/daily_steady_uptrend_mvp_email.json
```

邮件包含 S1-S5 分层数量、按行业分组的最终候选、股票代码、强势概念和 MA20 偏离度。MA20 偏离度仅作诊断与排序，不单独过滤。最终候选为零时仍会发送，正文展示完整分层数量和以下 S5 介入阻断统计：

```text
context_strength_unavailable
close_not_above_ma5
close_too_far_below_prior_high_20d
```

成功发送的唯一键为 `strategy_id + strategy_version + trade_date + run_id`。发送状态写入：

```text
/home/ubuntu/token_parse_sys/runtime/strategy_tracking/email_delivery/YYYYMMDD.json
```

状态含义：

- `sending`：已开始发送但尚未确认成功；为避免重复邮件，人工核查前不自动重发该不确定状态。
- `sent`：SMTP 已确认发送，后续相同唯一键返回 `already_sent`。
- `failed`：有限次数重试后失败，可在查明 SMTP 或网络原因后再次运行。

每次任务结果另存于 `email_job_results/YYYYMMDD.json`。日志和结果只记录错误类型与固定失败文案，不记录 SMTP 底层异常内容。

SMTP 凭据只允许保存在远端私有文件：

```text
/home/ubuntu/token_parse_sys/ops/env/steady_uptrend_email.json
```

文件格式：

```json
{
  "username": "sender@163.com",
  "authorization_code": "由运维人员在服务器上填写"
}
```

必须执行 `chmod 600`。该文件不得加入 Git、复制到报告目录或输出到终端。授权码轮换后只修改该私有文件，不修改版本化配置。

邮件任务在选股任务之后运行：

```cron
50 0 * * 2-6 cd /home/ubuntu/token_parse_sys_mvp && /usr/bin/python3 workflows/jobs/daily_steady_uptrend_mvp_email.py --schedule-config-path configs/schedules/daily_steady_uptrend_mvp_email.json >> /home/ubuntu/token_parse_sys/runtime/strategy_tracking/email_cron.log 2>&1
```

如果非交易日的最新报告仍指向已成功发送的 `run_id`，任务正常跳过，不重复发送旧结果。

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
