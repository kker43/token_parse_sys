# L0 MySQL 读取接口和快照输入

## 目的

这一层把已注册的 L0 `DataAsset` 契约转换成只读 MySQL 查询，并为 `daily_snapshot_production.py` 构建文件驱动输入。

## 入口

- L0 MySQL 适配器：
  `stock_lobster/l0_data_access/adapters/external_mysql.py`
- 快照输入工作流：
  `workflows/jobs/daily_snapshot_input_build.py`
- 快照输入调度示例：
  `configs/schedules/daily_snapshot_input_build.example.json`
- 请求示例：
  `configs/schedules/daily_snapshot_input_request.example.json`
- cron 模板：
  `ops/crontab/daily_snapshot_input_build.crontab.example`
- systemd 模板：
  `ops/systemd/token-parse-daily-snapshot-input-build.service.example`
  `ops/systemd/token-parse-daily-snapshot-input-build.timer.example`

## 生产顺序

1. 运行事实生产包装器。
2. 导出或刷新 `configs/data_assets/published_products.json`。
3. 针对目标日期运行质量监控器。
4. 运行 `daily_snapshot_input_build.py`。
5. 运行 `daily_snapshot_production.py`。

## 安全规则

- 本项目中的 MySQL 访问必须是只读的。
- 构造查询前必须校验 SQL 标识符。
- 过滤值通过查询参数传入。
- 下游 L1 快照保留来源 `asset_id`、查询版本和查询参数，以支持可复现。
