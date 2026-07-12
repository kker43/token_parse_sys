# 分层召回与信号确认策略样本评估

## 口径

- `amount` 和 `avg_amount_20d` 单位：`thousand_cny`。
- 2 亿元门槛：`200000 thousand_cny`。
- `volume_ratio_5d_20d`：近 5 日平均成交量 / 近 20 日平均成交量；v1-v3 保留 `>= 1.2` 的旧硬门槛。
- candidate_v4 不把量比作为召回硬门槛；除权窗口改用 `turnover_ratio_5d_20d`，两者都缺失时只阻止最终信号。
- `amount_ratio_20d`：包含当日的 20 日成交额均值，仅用于诊断和评分。
- `amount_ratio_prev_20d`：不含当日的前 20 日成交额均值，仅用于诊断和评分。
- v3/v3.1 为静态门槛结果，不包含跨日 cooldown 和全市场 TopN 位置。
- candidate_v4 的 `final_signal` 为样本事件集合内的动态 TopN、cooldown 和 no-refill 结果，不替代全市场回测。

## 策略结果

| 策略 | 正样本静态召回 | 硬负样本静态误召回 |
| --- | ---: | ---: |
| `breakout_v1` | 0/23 | 1/4 |
| `breakout_v2_weak_shape` | 0/23 | 1/4 |
| `pre_breakout_v1` | 0/23 | 1/4 |
| `pre_breakout_v3` | 0/23 | 1/4 |
| `pre_breakout_v3_1` | 0/23 | 1/4 |
| `trend_recall_subpools_candidate_v1` | 20/23 | 2/4 |
| `candidate_v4_recall_union` | 20/23 | 2/4 |
| `candidate_v4_final_signal` | 10/23 | 0/4 |

## pre_breakout_v1 正样本首阻断

- `already_new_high_60d`: 10
- `trend_stability_failed`: 6
- `steady_uptrend_failed`: 2
- `turnover_quality_failed`: 2
- `pre_breakout_ma30_sustained_failed`: 2
- `industry_concept_strength_failed`: 1

## candidate_v4 验收

- 正样本召回：`20/23`，目标 `>=17/23`。
- 硬负样本最终信号：`0/4`，目标 `0/4`。
- 结论：样本门槛通过，策略状态保持 `research_only`。

### 未召回正样本

- 铜冠铜箔 `20260427`
- 东山精密 `20260226`
- 江丰电子 `20260105`

### 硬负样本处置

- 章源钨业 `20260612`: recall=false, waiting=`-`, hard_risk=`-`, final=false
- 强瑞技术 `20260608`: recall=true, waiting=`-`, hard_risk=`noisy_ma30_breakdown_rebound`, final=false
- 麦格米特 `20260429`: recall=false, waiting=`-`, hard_risk=`-`, final=false
- 领先股份 `20260707`: recall=true, waiting=`acceleration_needs_consolidation;post_impulse_no_followthrough`, hard_risk=`-`, final=false

## candidate_v4 阈值敏感性

| 变体 | 正样本召回 | 硬负样本最终信号 | 全样本最终信号 |
| --- | ---: | ---: | ---: |
| `early_reversal_floor_0.03` | 20 | 0 | 12 |
| `early_reversal_floor_0.05` | 20 | 0 | 12 |
| `early_reversal_floor_0.08` | 19 | 0 | 12 |
| `pullback_ma30_0.75_0.55` | 20 | 0 | 12 |
| `pullback_ma30_0.55_0.55` | 21 | 0 | 12 |
| `long_base_volume_bonus_1.0` | 20 | 0 | 12 |
| `long_base_volume_bonus_1.1` | 20 | 0 | 12 |
| `long_base_volume_bonus_1.2` | 20 | 0 | 12 |
| `overextended_0.50_0.16` | 20 | 0 | 12 |
| `overextended_0.60_0.18` | 20 | 0 | 12 |
| `overextended_0.70_0.20` | 20 | 0 | 12 |

明细见 `20260712-layered-recall-signal-sample-evaluation.csv`。
