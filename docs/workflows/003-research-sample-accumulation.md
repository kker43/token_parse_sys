# Workflow 003：研究样本积累

## 目的

本 workflow 用于把人工样本、扫描候选、失败案例和漏召回案例沉淀为可复核的经验数据，帮助优化 L2/L3/L4 策略口径。

它只生产研究经验 artifact，不生产权威事实数据。

## 输入来源

样本来源分四类：

| 来源 | 用途 | 注意事项 |
| --- | --- | --- |
| `manual_gold_sample` | 用户人工确认的典型正反样本 | 保留截图、精确 `trade_date` 和人工解释 |
| `scan_candidate_review` | 扫描候选后的人工标注样本 | 必须记录扫描策略和候选池版本 |
| `backtest_failure_case` | 回测或观察中表现差的失败样本 | 区分入口错误、趋势质量不足和退出不足 |
| `missed_opportunity_case` | 事后强走势但未召回样本 | 只能用于研究校准，不能直接污染正式回测证据 |

## 样本事件分类

样本事件不要只分正负，应使用更细粒度分类：

| 分类 | 含义 |
| --- | --- |
| `positive_attention_high_value` | 高价值正样本，用于核心口径校准 |
| `positive_attention_mid_value` | 中价值正样本，可参与召回但需要降权或更强风控 |
| `weak_or_excluded_attention` | 弱样本或排除候选，用于降权和过滤 |
| `borderline_negative_recall` | 边界负样本，用于确认、风控和退出规则 |
| `negative_after_close_recall` | 召回后失败样本，优先进入失败归因 |
| `hard_negative_recall` | 硬负样本，用于入口排除和趋势质量过滤 |

## 最小结构

每个样本事件至少应包含：

```text
asset_id
asset_name
trade_date
timeframe
event_class
value_tier
human_interpretation
derived_l2_candidates
derived_l3_candidates
l4_implication
```

图片或外部证据放在：

```text
docs/assets/research_samples/<family_id>/
```

结构化样本放在：

```text
configs/research_samples/
```

## 覆盖门槛

第一版稳健上升趋势突破样本门槛记录在：

```text
configs/research_workflows/research_sample_accumulation_gate.example.json
```

默认目标：

| 指标 | 目标 |
| --- | ---: |
| 总事件数 | 40 |
| 有精确交易日事件数 | 30 |
| 正样本事件数 | 30 |
| 高价值正样本事件数 | 15 |
| 负样本事件数 | 15 |
| 硬负样本事件数 | 8 |
| 边界负样本事件数 | 10 |

该门槛只表示样本覆盖可以进入下一轮策略调参和验证，不表示策略可以进入生产。

## 检查命令

运行样本库覆盖检查：

```bash
python -m workflows.jobs.research_sample_library_review \
  --sample-library-path configs/research_samples/steady_uptrend_breakout_samples.json \
  --policy-path configs/research_workflows/research_sample_accumulation_gate.example.json \
  --output-path runtime/research_sample_reviews/steady_uptrend_breakout_sample_gate.json
```

输出中的 `gaps` 表示当前缺口，`next_actions` 表示下一批样本应该优先补什么。

## 待审样本队列

自动标注只能生成待审队列，不能直接写入正式样本库。

配置文件：

```text
configs/research_workflows/research_annotation_queue.example.json
```

生成待审队列：

```bash
python -m workflows.jobs.research_annotation_queue_build \
  --scan-result-path runtime/steady_uptrend_breakout/scan_result.json \
  --event-backtest-path runtime/steady_uptrend_breakout/event_backtest.json \
  --policy-path configs/research_workflows/research_annotation_queue.example.json \
  --holding-horizon 20 \
  --output-path runtime/research_annotation_queues/steady_uptrend_breakout_queue.json
```

队列中的每条记录必须保持：

```text
label_status = proposed
requires_human_confirmation = true
confirmed_event_class = null
confirmed_value_tier = null
```

用户确认后，才能把样本事件写入 `configs/research_samples/`。确认时只填写数字，不需要输入标签文字：

| 数字 | 类别 | 用途 |
| ---: | --- | --- |
| 1 | `positive_attention_high_value` | 高价值正样本 |
| 2 | `positive_attention_mid_value` | 中价值正样本 |
| 3 | `weak_or_excluded_attention` | 弱样本或排除候选 |
| 4 | `borderline_negative_recall` | 边界负样本 |
| 5 | `negative_after_close_recall` | 召回后失败样本 |
| 6 | `hard_negative_recall` | 硬负样本 |
| 7 | `out_of_family` | 不属于本形态族 |
| 8 | `skip_uncertain` | 证据不足，暂不入库 |

推荐的批量确认格式：

```text
queue_item_id<TAB>review_code
```

示例：

```text
603256.SH.20260409.scan_candidate_review	1
600188.SH.20260601.scan_candidate_review	4
002378.SZ.20260612.scan_candidate_review	6
```

## 与主链路关系

样本补充后，只能按以下顺序推进：

```text
PatternCase
-> FactorObservation
-> PrimitiveCandidate
-> LabelCandidate
-> StrategyCandidate
-> BacktestEvidence
-> ApprovalDecision
```

不能因为新增样本而直接修改正式策略、正式标签或事实数据生产逻辑。
