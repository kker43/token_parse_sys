# 每日事实数据生产

## 目的

使用 `workflows/jobs/daily_fact_data_production.py` 作为外部事实数据生产例行任务唯一面向调度器的入口。

调度器应该指向一个纳入版本管理的调度配置文件，而不是在 cron 或 systemd 中直接嵌入完整的上游命令。

## 文件

- 调度配置示例：
  `configs/schedules/daily_fact_data_production.example.json`
- cron 模板：
  `ops/crontab/daily_fact_data_production.crontab.example`
- systemd 模板：
  `ops/systemd/token-parse-daily-fact-production.service.example`
  `ops/systemd/token-parse-daily-fact-production.timer.example`

## 推荐服务器路径

- 项目根目录：`/home/ubuntu/token_parse_sys`
- 线上调度配置：
  `/home/ubuntu/token_parse_sys/configs/schedules/daily_fact_data_production.json`
- 运行结果路径：
  `/home/ubuntu/token_parse_sys/runtime/daily_fact_data_production/result.json`

## 示例命令

```bash
cd /home/ubuntu/token_parse_sys
/usr/bin/python3 workflows/jobs/daily_fact_data_production.py \
  --schedule-config-path configs/schedules/daily_fact_data_production.json
```

## 结果契约

包装器会写入结构化 JSON 结果，并把同一份 payload 打印到 stdout。payload 包含：

- `run_id`
- `status`
- `schedule_config_path`
- 生产者 `branch`
- 生产者 `commit`
- 生产者 `command`
- 生产者 `returncode`
- 生产者 `stdout_tail`
- 生产者 `stderr_tail`

调度器应该把非零退出码视为失败。
