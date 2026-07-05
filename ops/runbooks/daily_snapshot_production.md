# 每日分析快照生产

## 目的

使用 `workflows/jobs/daily_snapshot_production.py` 作为面向调度器的第一阶段 L1 `AnalysisSnapshot` 生产入口。

这个作业不直接拉取市场数据。它消费：

- 已导出的 L0 `DataAsset` 目录。
- 每个目标股票/日期已经取得的源数据行。

它会写出确定性的快照 JSON，供后续 L2 原语和 L3 标签消费。

## 文件

- 调度配置示例：
  `configs/schedules/daily_snapshot_production.example.json`
- cron 模板：
  `ops/crontab/daily_snapshot_production.crontab.example`
- systemd 模板：
  `ops/systemd/token-parse-daily-snapshot-production.service.example`
  `ops/systemd/token-parse-daily-snapshot-production.timer.example`

## 示例命令

```bash
cd /home/ubuntu/token_parse_sys
/usr/bin/python3 workflows/jobs/daily_snapshot_production.py \
  --schedule-config-path configs/schedules/daily_snapshot_production.json
```

## 当前阶段

第一版由文件驱动。后续即使把 `snapshot_input_path` 的生成替换为基于 MySQL 的 L0 repository，也不应该改变 L1 快照 schema 或下游原语/标签接口。
