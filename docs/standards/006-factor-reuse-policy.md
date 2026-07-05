# Standard 006: 因子复用优先与新增准入标准

## 1. 目的

本文档定义研究 workflow skill 在选择 L1/L2 因子、提出新原语或新指标生产需求时的优先级。

核心原则：

```text
先复用已有同类因子。
再通过参数化扩展已有口径。
最后才新增因子或生产任务。
```

这条规则用于避免因为单个策略样本反复建设语义相近、窗口略有不同、命名不同但本质重复的因子。

## 2. 适用范围

适用于：

- 个股研究策略沉淀 workflow。
- L2 primitive 设计。
- L3 label 依赖选择。
- L4 策略召回字段选择。
- 研究态指标缺口登记。
- 生产候选指标准入评审。

不适用于：

- 上游事实类数据生产。
- 临时样本解释中的人工备注。
- 不进入 registry 的一次性分析草稿。

## 3. 因子选择顺序

研究 workflow 选择因子时必须按以下顺序执行。

### 3.1 查找完全匹配因子

优先查找以下字段完全一致的因子：

```text
业务含义
时间周期
时间窗口
输入字段
计算公式
复权/价格口径
as-of 规则
缺失值策略
```

如果完全匹配，必须复用，不允许新增。

### 3.2 查找同类可参数化因子

如果只有窗口不同，例如：

```text
max_drawdown_60d
max_drawdown_120d
weekly_max_drawdown_26w
```

应优先判断它们是否属于同一个口径族：

```text
rolling_max_drawdown(close, window)
```

如果属于同一口径族，应登记为同类口径的参数扩展，而不是创建独立算法或策略专属生产任务。

### 3.3 查找近似替代因子

如果目标因子暂时不存在，但存在近似替代因子，例如：

```text
weekly_volatility_20w
weekly_pct_change_10w
weekly_ma20_slope_4w
```

workflow 可以在 research_only 阶段临时使用近似替代，但必须记录：

- 替代因子是什么。
- 和目标因子的差异是什么。
- 是否可能影响策略判断。
- 后续是否需要补齐目标因子。

### 3.4 登记生产缺口

只有当已有因子和参数化扩展都不能满足需求时，才登记生产缺口。

生产缺口必须说明：

```text
目标因子名
所属口径族
为什么已有因子不能复用
上游事实输入
计算公式
窗口参数
as-of 规则
预期使用层级
样本证据
```

### 3.5 禁止直接新增策略专属因子

不允许因为某个策略需要就直接新增：

```text
strategy_xxx_score
strong_breakout_magic_factor
weekly_good_stock_flag
```

策略组合逻辑应放在 L3/L4，L2 和基础指标层只沉淀可复用口径。

## 4. 相似因子判定规则

两个因子如果满足以下条件之一，应视为相似因子，必须先尝试复用或参数化：

- 只有时间窗口不同。
- 只有日线/周线/月线周期不同，但公式相同。
- 只有阈值不同。
- 输入字段相同、计算公式相同、输出语义相同。
- 一个是另一个的布尔化版本。

例子：

| 目标需求 | 已有类似因子 | 处理方式 |
| --- | --- | --- |
| `weekly_max_drawdown_26w` | `max_drawdown_60d`, `max_drawdown_120d` | 复用滚动最大回撤口径族，新增窗口参数，不新建算法 |
| `weekly_ma20` | `ma_price_weekly_statistic.ma20` | 直接复用上游周线 MA 统计 |
| `weekly_amount_ratio` | `amount_weekly_statistic.amount_ratio` | 直接复用上游周线成交额比值 |
| `weekly_trend_pass` | 多个周线原子因子 | 放在 L3/L4 组合，不作为事实层硬生产优先项 |

## 5. 状态标记

因子或指标缺口必须标记状态：

| 状态 | 含义 |
| --- | --- |
| `reuse_existing` | 已有完全可复用因子 |
| `reuse_with_window_param` | 复用同类口径，只新增窗口参数 |
| `research_temporary` | 研究态临时计算，不进入生产 |
| `pending_upstream_reuse` | 上游已有同类口径，但目标窗口尚未发布 |
| `new_factor_required` | 确认无法复用，才允许新建 |

## 6. Agent 检查清单

研究 workflow skill 在提出新因子前必须检查：

- [ ] 是否已有完全同名或同义因子。
- [ ] 是否只有窗口不同。
- [ ] 是否只有周期不同。
- [ ] 是否可以通过已有口径族参数化得到。
- [ ] 是否可以用已有近似因子支持 research_only 阶段。
- [ ] 是否明确记录不能复用的原因。
- [ ] 是否避免策略专属命名进入 L2 或基础指标层。

## 7. 周线回撤口径示例

`weekly_max_drawdown_26w` 的处理规则：

```text
目标语义：最近 26 根周 K 收盘价滚动最大回撤。
口径族：rolling_max_drawdown(close, window)。
窗口参数：26 weekly bars。
as-of：period_end_date <= signal_date 的最新周线。
当前状态：pending_upstream_reuse。
处理方式：研究扫描可临时计算；生产使用必须复用上游已有滚动统计口径族补齐，不在策略项目内另建生产任务。
```
