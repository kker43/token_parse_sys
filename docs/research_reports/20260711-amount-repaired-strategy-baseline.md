# 修复成交额后的样本策略基线

## 口径

- `amount` 和 `avg_amount_20d` 单位：`thousand_cny`。
- 2 亿元门槛：`200000 thousand_cny`。
- `amount_ratio_20d`：包含当日的20日均值。
- `amount_ratio_prev_20d`：不含当日的前20日均值。
- v3/v3.1 为静态门槛结果，不包含跨日 cooldown 和全市场 TopN 位置。

## 策略结果

| 策略 | 正样本静态召回 | 硬负样本静态误召回 |
| --- | ---: | ---: |
| `breakout_v1` | 0/23 | 1/4 |
| `breakout_v2_weak_shape` | 0/23 | 1/4 |
| `pre_breakout_v1` | 0/23 | 1/4 |
| `pre_breakout_v3` | 0/23 | 1/4 |
| `pre_breakout_v3_1` | 0/23 | 1/4 |
| `trend_recall_subpools_candidate_v1` | 15/23 | 0/4 |

## pre_breakout_v1 正样本首阻断

- `already_new_high_60d`: 10
- `trend_stability_failed`: 6
- `steady_uptrend_failed`: 2
- `turnover_quality_failed`: 2
- `pre_breakout_ma30_sustained_failed`: 2
- `industry_concept_strength_failed`: 1

明细见 `20260711-amount-repaired-strategy-baseline.csv`。
