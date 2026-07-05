# 每日策略信号生产运行手册

## 目标

`token_parse_sys` 接管策略生产调度和报告归档，但基础事实数据生产逻辑保持与 `token_fetch` 一致。Phase A 的边界是：

- 基础数据生产：由 `token_parse_sys` 的 `daily_fact_data_production.py` 作为外层入口，实际调用 `/home/ubuntu/token_fetch/cron_script/daily_master_scheduler.py`。
- 策略信号生产：基础任务完成后，`daily_strategy_signal_production.py` 从 MySQL 读取日线、周线、基础信息、行业/概念上下文，执行已注册测试策略。
- 报告落点：`/home/ubuntu/token_parse_sys/runtime/strategy_signal_production/YYYYMMDD/`。

## 例行任务

建议服务器 crontab 使用：

```cron
0 18 * * * cd /home/ubuntu/token_parse_sys && /usr/bin/python3 /home/ubuntu/token_parse_sys/workflows/jobs/daily_fact_data_production.py --schedule-config-path /home/ubuntu/token_parse_sys/configs/schedules/daily_fact_data_production.json >> /home/ubuntu/token_parse_sys/runtime/daily_fact_data_production/cron.log 2>&1
30 0 * * 2-6 cd /home/ubuntu/token_parse_sys && /usr/bin/python3 /home/ubuntu/token_parse_sys/workflows/jobs/daily_strategy_signal_production.py --schedule-config-path /home/ubuntu/token_parse_sys/configs/schedules/daily_strategy_signal_production.json >> /home/ubuntu/token_parse_sys/runtime/strategy_signal_production/cron.log 2>&1
```

第一条任务保持 `token_fetch` 当前生产逻辑不变，只迁移调度归属。第二条任务在次日凌晨运行，默认读取最新交易日，避免基础数据生产多轮重试后尚未完成。

## 手动执行

```bash
cd /home/ubuntu/token_parse_sys
/usr/bin/python3 workflows/jobs/daily_strategy_signal_production.py \
  --schedule-config-path configs/schedules/daily_strategy_signal_production.json \
  --date 20260703
```

## 产出文件

- `input/kline.tsv`：本次扫描用日线窗口。
- `input/weekly_kline.tsv`：本次扫描用周线窗口，按日线日期自动取不晚于当日的最近周线。
- `input/stock_context.tsv`：上市状态、市值、换手率、20 日均成交额、强行业/强概念命中。
- `candidates.json`：完整结构化结果。
- `candidates.csv`：便于人工查看的候选表。
- `report.md`：每日中文报告。
- `latest_result.json`：最新任务状态指针。

## 质量检查

每次部署或口径调整后至少检查：

```bash
python -m unittest discover -s tests
python workflows/jobs/daily_strategy_signal_production.py --help
```

如果策略报告候选异常偏多或偏少，先看 `input/stock_context.tsv` 中 `strong_industry_hit`、`strong_concept_hit`、`max_turnover_rate_20d`、`avg_amount_20d` 是否符合预期，再判断是否需要修改策略阈值。
