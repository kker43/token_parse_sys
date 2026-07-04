# Daily Snapshot Production

## Purpose

Use `workflows/jobs/daily_snapshot_production.py` as the scheduler-facing
entrypoint for first-stage L1 `AnalysisSnapshot` production.

This job does not fetch market data directly. It consumes:

- an exported L0 `DataAsset` catalog
- already-fetched source rows for each target stock/date

It writes deterministic snapshot JSON that later L2 primitives and L3 labels can
consume.

## Files

- schedule config example:
  `configs/schedules/daily_snapshot_production.example.json`
- cron template:
  `ops/crontab/daily_snapshot_production.crontab.example`
- systemd templates:
  `ops/systemd/token-parse-daily-snapshot-production.service.example`
  `ops/systemd/token-parse-daily-snapshot-production.timer.example`

## Example command

```bash
cd /home/ubuntu/token_parse_sys
/usr/bin/python3 workflows/jobs/daily_snapshot_production.py \
  --schedule-config-path configs/schedules/daily_snapshot_production.json
```

## Current stage

The first version is file-driven. Replacing `snapshot_input_path` generation
with MySQL-backed L0 repositories should not change the L1 snapshot schema or
downstream primitive/label interfaces.
