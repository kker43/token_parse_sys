# 稳步上行 MVP 选股邮件推送设计

## 目标

为现有 `strategy.steady_uptrend_mvp/v1` 例行选股增加独立邮件推送任务。任务读取已经落盘并通过质量门的选股 artifact，生成 HTML 邮件并发送到已配置邮箱，不重新计算行情、指标或策略结果。

## 范围

本次只增加以下能力：

- 读取现有 `strategy_tracking` 运行结果。
- 将分层数量、最终候选和诊断信息渲染为 HTML。
- 通过 163 SMTP SSL 发送邮件。
- 记录发送结果并按 `trade_date + run_id` 防重复。
- 配置独立的远端例行调度。

本次不修改 S1-S5 策略口径，不发布正式 L5 信号，不引入新的事实数据生产，也不增加邮件管理后台。

## 架构

采用独立通知任务，而不是把 SMTP 调用放进选股计算任务：

```text
00:30 现有选股任务
-> 质量门检查
-> 生成 run artifact 和 report artifact

00:50 邮件通知任务
-> 读取 latest.json
-> 校验 job_result.json 和 result.json
-> 检查发送 ledger
-> 渲染 HTML
-> SMTP SSL 发送
-> 原子写入发送结果
```

通知任务只消费业务层 artifact。邮件发送失败不得修改选股报告，也不得把成功的选股运行标记为失败。

## 组件

### 邮件通知作业

新增独立入口 `workflows/jobs/daily_steady_uptrend_mvp_email.py`，职责如下：

1. 加载邮件调度配置。
2. 读取 `reports/latest.json` 指向的最新成功报告。
3. 校验策略标识为 `strategy.steady_uptrend_mvp/v1`。
4. 校验 `job_result.json.status == "success"`。
5. 读取对应运行目录的 `result.json`。
6. 检查同一 `trade_date + run_id` 是否已经成功发送。
7. 渲染 HTML 和纯文本降级内容。
8. 使用 SMTP SSL 发送邮件。
9. 原子写入发送结果 ledger。

### HTML 渲染

邮件正文包含：

- 交易日、策略 ID、版本和 `test_tracking` 状态。
- S1-S5 的输入、通过、淘汰数量。
- 按行业分组的最终候选。
- 每只股票的代码、名称、概念和 MA20 偏离度等级。
- 数据依赖版本和 `run_id`，用于审计。

当最终候选为零时，正文仍须发送，并展示：

- 完整分层数量。
- S3 和 S4 的存量数量。
- S5 阻断条件及命中数量。
- 明确说明“无最终入选”，避免被误判为邮件内容缺失。

所有来自 artifact 的文本在进入 HTML 前必须转义。

### SMTP 配置

业务调度配置只保存非敏感字段：

- SMTP 主机：`smtp.163.com`
- SMTP SSL 端口：`465`
- 发件人和收件人地址。
- 远端私有凭据文件路径。
- artifact、ledger 和锁文件路径。

SMTP 授权码只保存在远端私有文件中：

```text
/home/ubuntu/token_parse_sys/ops/env/steady_uptrend_email.json
```

该文件权限必须为 `0600`，不得纳入 Git，不得出现在命令输出、日志、异常文本、报告或测试夹具中。

## 防重复与日期规则

成功发送的唯一键为：

```text
strategy_id + strategy_version + trade_date + run_id
```

发送成功后写入：

```text
/home/ubuntu/token_parse_sys/runtime/strategy_tracking/email_delivery/YYYYMMDD.json
```

如果同一唯一键已经存在成功记录，任务返回成功但不再次发送。选股任务在非交易日重复指向旧交易日时，因此不会重复推送旧邮件。

## 失败处理

- 报告尚未生成：通知任务失败并记录 `report_not_ready`，不发送旧报告。
- 选股任务失败：通知任务记录 `selection_job_failed`，不发送伪造结果。
- artifact 契约不一致：通知任务失败，不猜测字段含义。
- SMTP 连接或认证失败：最多进行有限次数重试，最终失败时记录经过脱敏的错误类型。
- 发送成功但 ledger 落盘失败：任务以失败结束并保留明确错误；运维处理前不得自动假定可安全重发。

日志和失败 artifact 不得包含 SMTP 授权码。

## 调度

远端新增独立 cron：

```text
50 0 * * 2-6
```

时区沿用服务器的 `Asia/Shanghai`。现有 `00:30` 选股任务保持不变，通知任务在其后运行。

## 测试与验收

自动测试覆盖：

- 正常候选的 HTML 转义和行业分组。
- 零候选邮件包含 S3/S4 数量和 S5 阻断统计。
- 错误策略 ID、失败报告和缺失 artifact 被拒绝。
- 已发送唯一键不会重复调用 SMTP。
- SMTP 成功后写入 ledger。
- SMTP 失败不会修改选股 artifact，错误信息不泄露授权码。
- 私有配置缺字段或权限过宽时拒绝运行。

部署验收：

1. 相关单元测试和完整测试通过。
2. 远端代码与提交版本一致。
3. 私有凭据文件权限为 `0600`。
4. cron 中只存在一条启用的邮件通知任务。
5. 使用最近一期真实选股 artifact 发送一封 HTML 验证邮件。
6. 服务端 ledger 记录发送成功，但不记录授权码。

