# 稳健趋势 MVP 例行链路设计

## 目标

将外部事实数据就绪检查、只读输入导出、业务策略解析、MVP 扫描、审计归档和中文报告发布串成一个可由 cron 直接调用的确定性任务。

当前唯一例行业务策略为 `strategy.steady_uptrend_mvp/v1`，生命周期保持 `test_tracking`。本设计不发布正式 L5 `StrategySignal`，也不改变已确认的 S1-S5 业务口径。

## 分层边界

- 外部生产系统继续拥有事实数据和 `pub_data_quality_status`。
- Stock Lobster 只读消费外部 MySQL，不采集、修复或改写事实数据。
- 现有 K 线、上下文导出器负责生成确定性 TSV 和 manifest。
- 策略注册表与策略配置属于业务层。
- 新例行任务只负责技术编排，不持有 S1-S5 阈值或过滤逻辑。
- MVP 扫描器继续负责输入契约校验、分层计算和报告内容生成。

## 新增组件

新增 `workflows/jobs/daily_steady_uptrend_mvp_tracking.py`，作为唯一 cron 入口。

该任务接收一个 schedule JSON，并依次执行：

```text
解析 schedule
-> 解析并校验业务策略注册表
-> 解析目标交易日
-> 读取外部日频质量状态和周线发布产品证据
-> 校验必要产品 ready/pass
-> 导出日线和周线 TSV + manifest
-> 导出个股上下文 TSV + manifest
-> 执行注册表 selection_job
-> 写入版本化运行产物
-> 原子发布当日报告目录
-> 写入 latest 成功指针和任务结果
```

编排任务调用既有 Python API，不通过 shell 拼接子命令。业务策略执行入口必须来自注册表中唯一 `routine_selection_enabled=true` 的记录，并限制为仓库内已批准的 `workflows/jobs/` 模块。

## 交易日解析

- 显式传入 `--date YYYYMMDD` 时使用指定日期。
- 未传日期时，从外部 `pub_data_quality_status` 中选择最新交易日。
- 该日期的日线、日基础、日指标和资产基础产品必须在外部 `pub_data_quality_status` 中为 `CN_A/stock + ready/pass`，并使用精确日期查询，禁止范围扫描质量视图。
- 外部 `pub_data_quality_status` 正式发布 `pub_stock_weekly_kline` 质量项。若目标日期本身是周线周期结束日，精确日期查询直接取得五个产品；否则从同一质量视图读取不晚于目标日期的最近周线质量行。
- 周线质量行必须保持真实 `period_end_date`，不得把日频信号日期伪装成周线周期结束日；下游不再自行统计周线记录或构造质量状态。
- 任一必要产品缺失、重复、版本不一致或状态失败时，任务停止，不沿用上一日结果冒充当日结果。

## 输入窗口

窗口由 schedule 配置：

- 日线开始日期：目标交易日前 `daily_lookback_calendar_days`，MVP 默认 `440` 个自然日。
- 周线开始日期：目标交易日前 `weekly_lookback_calendar_days`，默认 `950` 个自然日。
- 结束日期均为目标交易日。
- 价格口径固定为 `qfq_asof`。

自然日窗口只用于生成足够的交易日历史，不改变策略内部交易日窗口定义。

## 目录与发布

每次运行的完整证据目录：

```text
/home/ubuntu/token_parse_sys/runtime/strategy_tracking/runs/YYYYMMDD/
  strategy.steady_uptrend_mvp/v1/
    input/
      kline.tsv
      weekly_kline.tsv
      stock_context.tsv
      kline_manifest.json
      stock_context_manifest.json
      quality_status.json
    result.json
    report.md
    job_result.json
```

面向人工查看的稳定报告目录：

```text
/home/ubuntu/token_parse_sys/runtime/strategy_tracking/reports/YYYYMMDD/
  report.md
  candidates.json
  job_result.json
```

成功后再通过同目录临时文件原子替换这三个发布文件，并更新：

```text
/home/ubuntu/token_parse_sys/runtime/strategy_tracking/reports/latest.json
```

`latest.json` 只指向最后一次成功运行。失败运行不得覆盖已有成功报告。

## 幂等与并发

- 同一日期、策略 ID、版本和输入数据版本生成固定 `run_id`。
- 相同输入重复执行可覆盖同一版本化运行目录，结果 JSON 和 Markdown 必须保持确定性。
- 任务使用独占锁文件，防止 cron 与人工执行并发写同一目录。
- 检测到锁已被有效进程持有时返回失败，不启动第二次扫描。

## 失败语义

每一步失败都写入全局任务状态目录：

```text
/home/ubuntu/token_parse_sys/runtime/strategy_tracking/job_results/YYYYMMDD.json
```

失败结果至少包含：

- `status=failed`
- `trade_date`（若已解析）
- `failed_stage`
- `error_type`
- `error_message`
- 已完成的 artifact 路径

任务返回非零退出码。不得回退到旧策略、不得发布半成品报告、不得修改 `latest.json`。

## Schedule 契约

`configs/schedules/daily_steady_uptrend_mvp_tracking.example.json` 扩展为完整例行配置，至少包含：

- MySQL 配置路径。
- 业务策略注册表路径。
- 运行根目录和报告根目录。
- 日线、周线自然日回看窗口。
- 价格口径。
- 质量状态产品集合。
- 锁文件和最新成功指针路径。

部署时从 example 生成服务器实际配置，不在仓库提交凭据。

## Cron

事实数据任务继续按原计划运行。MVP 任务在周二至周六凌晨执行：

```cron
30 0 * * 2-6 cd /home/ubuntu/token_parse_sys_mvp && /usr/bin/python3 workflows/jobs/daily_steady_uptrend_mvp_tracking.py --schedule-config-path configs/schedules/daily_steady_uptrend_mvp_tracking.json >> /home/ubuntu/token_parse_sys/runtime/strategy_tracking/cron.log 2>&1
```

自动日期解析保证周末和非交易日不伪造新交易日。重复跑到同一已就绪交易日属于幂等重跑。

## 测试与验收

单元测试覆盖：

- 注册表零个、多个或错误生命周期的例行策略均被拒绝。
- 自动日期解析只选择必要产品全部就绪的最新日期。
- 周线质量日期正确解析。
- 导出、扫描和发布按顺序执行。
- 中间失败不会发布报告或覆盖 `latest.json`。
- 同一输入重复运行结果一致。
- 报告目录包含 `report.md`、`candidates.json`、`job_result.json`。

部署验收：

- 本地全量测试通过。
- 服务器使用 2026-07-10 数据得到 `5521 -> 1482 -> 166 -> 106 -> 90 -> 25`。
- 手动不指定日期执行一次，自动选择最新全部就绪交易日。
- 安装 cron 后确认仅保留一个活动选股任务。
- 检查报告目录、latest 指针、失败状态和 cron 日志。

## 非目标

- 不将 `test_tracking` 晋升为 `active_production`。
- 不修改 S1-S5 阈值。
- 不重新启用任何历史业务策略。
- 不在本次工作中完成旧研究导出器向完整 L0-L5 正式链路的重构；新任务仅复用现有只读能力并保持边界清晰。
