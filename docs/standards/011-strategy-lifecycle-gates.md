# Standard 011：策略生命周期上线门槛

## 目的

本文档定义候选策略从测试跑数进入 `test_tracking`，再进入 `active_production` 的最低门槛。

核心原则：

```text
回测通过不等于自动上线。
test_tracking 不等于正式生产。
任何生命周期升级都需要用户确认。
```

## 状态分级

通用 artifact 状态以 `000-standards-map.md` 为准。本文只定义策略从候选验证进入测试跟踪和正式生产时的生命周期门槛。

`pending_approval`、`paused` 和 `retired` 是观察记录或策略流转中的局部状态：

- `pending_approval` 表示等待用户确认，不代表已经进入 `test_tracking`。
- `paused` 表示暂缓执行或观察，不代表淘汰。
- `retired` 表示策略或观察记录生命周期结束，可在 artifact 层映射为 `deprecated`。

### test_tracking

含义：

- 允许每天用实盘数据跑闭环。
- 允许记录候选、观察未来表现和生成复盘材料。
- 不发布正式信号。
- 不代表策略已被批准生产。

建议最低门槛：

```text
target_status: test_tracking
主周期: 10D
样本数: >= 20
胜率: >= 52%
平均收益: > 0
相对候选池等权: excess_avg_return > 0
最大回撤: <= 30%
dry-run 连续成功: >= 3 个交易日
用户确认: required
```

### active_production

含义：

- 策略成为正式生产策略。
- 信号进入正式报告、看板或例行复盘。
- 策略版本必须锁定。
- 调整必须生成新候选版本，不能静默修改原版本。

建议最低门槛：

```text
target_status: active_production
主周期: 10D
样本数: >= 50
test_tracking 观察: >= 20 个交易日
胜率: >= 55%
平均收益: > 0
中位收益: > 0
相对候选池等权: excess_avg_return > 0
相对全 A 等权: excess_avg_return > 0
最大回撤: <= 25%
失败案例: 已归因并形成 ReviewFinding
用户确认: required
```

## 测试阶段和正式阶段差异

| 项目 | test_tracking | active_production |
| --- | --- | --- |
| 输出类型 | evidence / proposal / observation draft | StrategySignal / production report |
| 是否正式信号源 | 否 | 是 |
| 是否允许调口径 | 允许生成新候选版本 | 只能生成新版本，不能静默修改 |
| 是否需要人工确认 | 是 | 是 |
| 失败处理 | 记录失败样本和复盘线索 | 必须进入 ReviewFinding |
| 目录建议 | `runs/test_tracking_candidates/` | `runs/production/` |

## 配置落点

生命周期门槛写在 evaluation profile 的 `lifecycle_gates` 中：

```text
configs/evaluation_profiles/*.json
```

`strategy_closed_loop_review` 根据 `--target-status` 选择对应 gate：

```text
--target-status test_tracking
--target-status active_production
```

如果没有匹配的 lifecycle gate，则回退到 `acceptance_policy`。

## 禁止事项

- 不允许因为单次回测好看直接进入 `active_production`。
- 不允许脚本自动替代用户审批。
- 不允许在不生成新版本的情况下修改已批准策略口径。
- 不允许把测试阶段输出当作正式信号发布。
