# 每日策略选股例行任务运行手册

## 技术边界

本手册描述长期保留的例行任务能力，不固化某一版业务选股口径。技术体系负责：

- 在外部事实数据就绪后读取只读输入 artifact。
- 校验 K 线、上下文、质量状态和版本 manifest。
- 调用业务策略注册表中唯一启用的策略执行入口。
- 生成可复现的候选、分层审计和任务状态产物。
- 保留样本回放、因子计算和历史结果复核能力。

策略配置、阈值、过滤顺序和排序规则属于业务层。旧策略退役只会禁用其调度绑定，不会删除例行任务、执行器、输入契约或回放能力。

## 当前业务绑定

当前唯一启用的业务策略为 `strategy.steady_uptrend_mvp/v1`，生命周期为 `test_tracking`。配置入口：

```text
configs/strategies/strategy_registry.json
configs/strategies/steady_uptrend_mvp.json
configs/schedules/daily_steady_uptrend_mvp_tracking.json
```

旧 `daily_strategy_signal_production.json` 是 pre-breakout 业务策略的历史绑定，必须保持 `enabled=false`。`workflows/jobs/daily_strategy_signal_production.py` 及其取数、报告辅助能力继续保留，不因旧绑定停用而废弃。

## 执行顺序

```text
外部事实数据完成
-> 解析业务策略注册表
-> 验证仅一个 routine_selection_enabled=true
-> 从 pub_data_quality_status 解析完整交易日
-> 生成并校验只读输入 artifact
-> 执行该策略的 selection_job
-> 原子发布 test_tracking 报告和审计明细
```

当前 MVP 的具体命令、输入文件和输出检查见 `ops/runbooks/daily_steady_uptrend_mvp_tracking.md`。

## 发布检查

每次替换业务策略绑定时至少检查：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 workflows/jobs/daily_steady_uptrend_mvp_tracking.py --help
```

同时确认：注册表仅有一个例行策略、旧业务绑定均未启用、结果中的策略 ID/版本/状态与注册表一致、输入依赖版本完整。
