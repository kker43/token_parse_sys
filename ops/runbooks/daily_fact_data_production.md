# Daily Fact Data Production

## Purpose

Use `workflows/jobs/daily_fact_data_production.py` as the only scheduler-facing
entrypoint for the external factual-producer routine.

The scheduler should point to a checked-in schedule config file instead of
embedding the full upstream command directly in cron or systemd.

## Files

- schedule config example:
  `configs/schedules/daily_fact_data_production.example.json`
- cron template:
  `ops/crontab/daily_fact_data_production.crontab.example`
- systemd templates:
  `ops/systemd/token-parse-daily-fact-production.service.example`
  `ops/systemd/token-parse-daily-fact-production.timer.example`

## Recommended server paths

- project root: `/home/ubuntu/token_parse_sys`
- live schedule config:
  `/home/ubuntu/token_parse_sys/configs/schedules/daily_fact_data_production.json`
- runtime result path:
  `/home/ubuntu/token_parse_sys/runtime/daily_fact_data_production/result.json`

## Example command

```bash
cd /home/ubuntu/token_parse_sys
/usr/bin/python3 workflows/jobs/daily_fact_data_production.py \
  --schedule-config-path configs/schedules/daily_fact_data_production.json
```

## Result contract

The wrapper writes a structured JSON result and prints the same payload to
stdout. The payload includes:

- `run_id`
- `status`
- `schedule_config_path`
- producer `branch`
- producer `commit`
- producer `command`
- producer `returncode`
- producer `stdout_tail`
- producer `stderr_tail`

Schedulers should treat non-zero exit codes as failures.
