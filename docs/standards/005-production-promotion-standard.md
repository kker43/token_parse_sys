# Standard 005: 研究指标与经验数据生产准入标准

## 1. 目的

本文档定义研究过程中产生的新指标、新 L2 原语、新 L3 标签和新 L4 策略，什么时候可以继续保留在研究态，什么时候可以注册为候选口径，什么时候可以进入例行生产。

核心原则：

```text
不要因为单个策略临时需要，就立刻污染基础生产层。
先研究、再验证、再注册、再生产。
```

## 2. 分层状态机

所有研究派生 artifact 必须处于以下状态之一：

| 状态 | 中文含义 | 允许做什么 | 不允许做什么 |
| --- | --- | --- | --- |
| `research_only` | 研究临算 | 在研究 job 中临时计算、样本验证、回测探索 | 不进入例行生产，不作为正式依赖 |
| `candidate` | 候选注册 | 写入 registry 样例，记录口径、证据、阈值、适用范围 | 不进入生产调度，不对外承诺稳定 |
| `production_candidate` | 生产候选 | 已有足够证据，准备进入生产设计、成本评估、质量监控设计 | 仍不能直接用于正式策略生产 |
| `approved_production` | 已批准生产 | 进入例行任务、质量监控、版本化发布 | 不能静默修改口径 |
| `deprecated` | 废弃 | 保留历史兼容和审计 | 不再新增依赖 |

状态推进链路：

```text
research_only
-> candidate
-> production_candidate
-> approved_production
```

任何一级都可以因为证据不足、成本过高或口径不稳定而停留或退回。

## 3. 各层生产准入边界

### 3.1 基础技术指标

基础技术指标包括：

```text
ma60
ma120
ma20_slope_20d
max_drawdown_60d
close_new_high_60d_flag
convergence_5_10_20_pct
```

进入例行生产前，必须满足：

- 至少被 2 个以上研究 workflow 依赖，或被 1 个高优先级策略反复使用。
- 有明确、白盒、无未来函数的计算口径。
- 有窗口长度、字段来源、缺失处理、数据质量检查。
- 计算成本可接受。
- 有生产失败时的降级策略。

未满足时，保留在：

```text
research_only 或 candidate
```

### 3.2 L2 原语

L2 原语进入生产前，必须满足：

- 只消费 L1 snapshot 或已批准基础指标。
- 原语表达的是单一状态，不表达完整策略。
- 阈值经过样本组和反例验证。
- 有明确适用市场、周期、窗口。
- 有至少一个 L3 标签或 L4 策略持续依赖。

### 3.3 L3 标签

L3 标签进入生产前，必须满足：

- 只消费已批准或生产候选的 L2 原语。
- 标签语义稳定，能够被人工解释。
- 有正样本、反例样本、失败案例。
- 有回测或观察证据证明它不是单一股票偶然现象。
- 明确是否属于技术形态、基本面画像、环境标签、风险标签或复合准备态。

### 3.4 L4 策略

L4 策略进入 `test_tracking` 前，必须满足：

- L2/L3 依赖没有未解决生产缺口。
- L6 回测达到准入标准。
- 样本数满足最低要求。
- 最大回撤、胜率、收益指标达到阈值。
- 记录失败案例和适用边界。

L4 策略进入正式生产前，还需要经过更严格的人工审批。

## 4. 生产准入证据字段

每个 artifact 的生产准入评审需要一份 evidence 文件，字段如下：

```text
artifact_id
artifact_type
current_status
target_status
owner
description
dependency_count
dependent_workflows
positive_sample_count
negative_sample_count
backtest_sample_size
backtest_win_rate
backtest_annual_return
backtest_max_drawdown
threshold_stability
calculation_cost
quality_monitoring_ready
missing_data_policy_ready
no_future_data_check_ready
failure_case_count
notes
```

## 5. 默认准入阈值

第一版默认阈值：

| 目标状态 | 最低要求 |
| --- | --- |
| `candidate` | 有清晰口径，至少 2 个正样本或 1 个明确研究案例 |
| `production_candidate` | 正样本不少于 20，反例不少于 10，至少 1 次回测或观察验证 |
| `approved_production` | 回测样本不少于 30，胜率不低于 55%，最大回撤不超过 25%，质量监控和缺失策略已准备 |

说明：

这些阈值是默认标准。不同策略家族可以覆盖，但必须显式记录原因。

## 6. 稳健趋势突破策略当前结论

以 `strategy.steady_uptrend_breakout_watch` 为例：

当前结论：

```text
L4 策略保持 draft。
相关新指标保持 research_only 或 candidate。
暂不进入基础数据例行生产。
```

原因：

- 样本主要来自两个强样本股票。
- 20 日回测可评估样本只有 17，低于默认 30。
- 20 日最大交易回撤约 30.47%，超过默认 25%。
- 基本面、行业、题材上下文尚未纳入。

下一步应该是：

```text
扩样本
补反例
多阈值回测
记录失败案例
再决定是否进入 production_candidate
```

## 7. 操作流程

标准流程：

```text
1. 研究 job 临时计算指标。
2. 生成 evidence JSON。
3. 运行 production_promotion_review.py。
4. 如果结论是 keep_research_only，继续研究。
5. 如果结论是 promote_to_candidate，写入 registry 样例。
6. 如果结论是 promote_to_production_candidate，设计生产任务和质量监控。
7. 如果结论是 approve_production，进入例行调度。
```

任何自动脚本只能给出建议，不能替代人工审批。
