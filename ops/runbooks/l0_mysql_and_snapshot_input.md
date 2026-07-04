# L0 MySQL Read Interface and Snapshot Input

## Purpose

This layer turns registered L0 `DataAsset` contracts into read-only MySQL
queries and builds file-driven input for `daily_snapshot_production.py`.

## Entry Points

- L0 MySQL adapter:
  `stock_lobster/l0_data_access/adapters/external_mysql.py`
- Snapshot input workflow:
  `workflows/jobs/daily_snapshot_input_build.py`
- Snapshot input schedule example:
  `configs/schedules/daily_snapshot_input_build.example.json`
- Request example:
  `configs/schedules/daily_snapshot_input_request.example.json`
- cron template:
  `ops/crontab/daily_snapshot_input_build.crontab.example`
- systemd templates:
  `ops/systemd/token-parse-daily-snapshot-input-build.service.example`
  `ops/systemd/token-parse-daily-snapshot-input-build.timer.example`

## Production Order

1. Run fact production wrapper.
2. Export or refresh `configs/data_assets/published_products.json`.
3. Run quality monitor for the target date.
4. Run `daily_snapshot_input_build.py`.
5. Run `daily_snapshot_production.py`.

## Safety Rules

- MySQL access is read-only from this project.
- SQL identifiers are validated before query construction.
- Filter values are passed as query parameters.
- Downstream L1 snapshots keep source `asset_id`, query version, and query
  params for reproducibility.
