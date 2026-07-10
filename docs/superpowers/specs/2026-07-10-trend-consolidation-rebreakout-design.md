# 趋势盘整后再突破策略设计

## 1. 文档状态

- 设计日期：2026-07-10
- 设计状态：`pending_written_review`
- 目标策略族：`strategy.trend_consolidation_rebreakout`
- 初始生命周期：`research_only`
- 目标市场：A 股
- 价格口径：`qfq_asof`
- 主评估周期：H5
- 辅助评估周期：H10
- 风险参考周期：H20

本文固化已经确认的业务口径：盘整末期进入观察池，只有收盘确认突破阶段新高后才生成正式策略信号；异动用于优先召回和提前建档，但不是正式信号的硬前置条件。

## 2. 目标与非目标

### 2.1 目标

识别已经形成有效上涨趋势、随后经历有质量的盘整、最终收盘确认突破阶段新高的个股。

系统需要：

1. 用白盒规则识别原趋势、盘整、观察和确认突破四个阶段。
2. 用“异动优先 + 全市场兜底”的双候选池缩小每日分析范围，同时控制漏召回。
3. 让候选池来源、状态迁移、通过原因、拒绝原因和评分全部可复现。
4. 先以 `research_only` 方式完成样本召回、事件回测、分池比较和滚动稳定性验证。
5. 只有经过用户确认，策略才允许进入 `test_tracking`；本设计不授权进入 `active_production`。

### 2.2 非目标

本设计不负责：

- 生产、清洗、修复或改写权威行情事实数据。
- 把异动直接解释为买入信号。
- 使用机器学习替代白盒因子和状态迁移。
- 直接替换当前 `steady_uptrend_pre_breakout_watch` 例行任务。
- 在第一版引入基本面、新闻或 Agent 主观判断作为硬过滤。
- 为全市场链路和异动观察池建设两套独立引擎。

## 3. 核心业务语义

### 3.1 状态机

```text
E0-A 异动种子池 ─┐
                  ├→ S1 原上涨趋势成立
E0-B 全市场兜底池 ┘
                         ↓
                      S2 有效盘整形成
                         ↓
                      S3 盘整末期观察
                         ↓
                      S4 收盘确认新高突破
```

另设失败状态 `SX`，用于记录趋势破坏、平台失效、观察超时和假突破。

### 3.2 状态定义

#### E0：候选种子

E0 只回答“哪些股票值得开始或继续分析”，不表达趋势成立、盘整完成或可以买入。

候选来源：

- `anomaly_seed_pool`：价格强度、量价启动、低波动唤醒或行业共振异动。
- `full_market_trend_pool`：没有显著异动，但已满足基础趋势或盘整准备条件的全市场兜底候选。

两池取并集并按 `asset_id + signal_date` 去重，必须保留全部 `source_tags`、规则版本和首次进入日期。

#### S1：原上涨趋势成立

S1 必须证明盘整前已经存在有效上涨段，而不是长期弱势后的单日反弹。

第一版要求日线趋势成立，并把周线趋势作为质量过滤。原上涨段的强度、持续性和相对强度进入诊断与评分，不在未经样本验证前全部设为硬阈值。

#### S2：有效盘整形成

S2 必须同时表达：

- 盘整持续时间达到最低要求。
- 价格区间、ATR 或均线间距相对原上涨段收缩。
- 成交额相对原上涨段下降或保持温和。
- 平台低点没有破坏 MA20/MA30 或原突破位支撑。
- 没有出现足以判定趋势破坏的放量长阴、连续破位或异常换手。

默认研究窗口为 5 至 20 个交易日；同时回测 5-10、10-20、20-40 三档，窗口本身是业务含义，必须保留版本。

#### S3：盘整末期观察

S3 表示平台有效且价格重新接近触发位，但尚未收盘确认突破阶段新高。

默认观察条件：

- 距离触发位不超过 5%。
- 平台结构仍有效。
- 量能未出现明显过热或衰竭。
- 观察有效期默认 10 个交易日。

S3 只产生 `ObservationCandidate`，不产生 `StrategySignal`。

#### S4：收盘确认新高突破

正式触发位定义为：

```text
trigger_level = max(base_high_excluding_today, prior_60d_close_high_excluding_today)
```

只有当收盘价高于 `trigger_level`，并且突破幅度、量能和收盘质量通过时，L5 才能生成正式信号。

局部平台突破但尚未刷新阶段高点，只提升观察等级，不进入 S4。

#### SX：失效或失败

出现以下任一情况时进入 SX：

- 收盘跌破平台低点。
- 收盘有效跌破 MA30，且不是单日可修复噪声。
- 盘整持续超过当前策略版本的最大期限。
- 突破后在规定确认期内重新收回平台。
- 出现放量长阴、异常换手或连续分布日，导致趋势质量失效。

SX 必须记录 `failure_reason`，不得静默删除历史状态。

## 4. 双候选池设计

### 4.1 方案选择

采用“双入口、单状态机”：

- 异动池负责聚焦、提前建档和提高报告优先级。
- 全市场池负责发现没有明显异动但已经满足趋势或盘整条件的股票。
- 两个入口共用同一 `AnalysisSnapshot -> StagePipeline -> StrategyDSL -> Signal Engine -> Backtest Engine -> Observation Tracking` 主干。

不采用“异动硬前置”，因为缩量盘整本身可能非常安静，强制先异动会制造系统性漏召回。

### 4.2 CandidatePoolPolicy

第一版定义三个可回放候选池策略：

1. `candidate_pool.anomaly_seed_v1`
   - 来源：L2/L3 异动标签。
   - 默认保留期：40 个交易日。
   - 保留首次异动日期、最近异动日期、异动类型、触发值和规则版本。
2. `candidate_pool.full_market_trend_fallback_v1`
   - 来源：全 A 正常上市股票。
   - 先做最低数据质量和流动性检查，再召回基础趋势或盘整准备候选。
3. `candidate_pool.trend_consolidation_union_v1`
   - 来源：前两池并集。
   - 去重后保留所有来源标签，不允许后来源覆盖先来源。

所有候选池快照必须包含：

- `policy_id`、`policy_version`、`asof_date`。
- `asset_id`、`source_tags`、`first_seen_date`、`latest_seen_date`。
- 候选进入原因和候选失效原因。
- 输入 `AnalysisSnapshot`、标签和策略版本。

### 4.3 异动类型

第一版只建设四类可解释异动：

- `anomaly.price_relative_strength_acceleration`
  - 1/3/5 日收益相对全 A 或所属行业显著增强。
- `anomaly.price_volume_expansion`
  - 价格突破短期区间或接近阶段高点，同时成交额扩张。
- `anomaly.low_volatility_wakeup`
  - 前期 ATR 和成交额收缩，随后价格与成交额同步扩张。
- `anomaly.industry_context_acceleration`
  - 个股增强同时伴随行业或概念相对强度加速。

这些异动是 Stock Lobster 基于外部事实数据构建的确定性分析标签，不得写回或伪装成上游事实产品。

## 5. 分层因子设计

### 5.1 优先复用的 L2 原语

第一版复用现有口径族：

- `moving_average.close_above_ma20`
- `moving_average.close_above_ma30`
- `moving_average.close_above_ma60`
- `moving_average.ma20_above_ma60`
- `moving_average.ma60_above_ma120`
- `trend.ma20_rising_20d`
- `risk.max_drawdown_60d_controlled`
- `risk.max_drawdown_120d_controlled`
- `structure.ma_5_10_20_converged`
- `volume_liquidity.amount_ratio_20d_high`
- `candlestick.red_k_ratio_20d_healthy`
- `candlestick.long_shadow_ratio_20d_controlled`
- `weekly_context.weekly_trend_context_pass`
- `context.industry_or_concept_strength_hit`

复用不等于沿用当前所有阈值。阈值变化应生成新原语版本或参数化口径，不得静默修改旧版本。

### 5.2 必须新增的 L2 原语

#### 原上涨段

- `trend.prior_impulse_return`
- `trend.prior_impulse_duration`
- `trend.relative_strength_vs_market`
- `trend.relative_strength_vs_industry`

#### 盘整段

- `structure.consolidation_duration`
- `structure.base_high_excluding_today`
- `structure.base_low_excluding_today`
- `structure.base_range_pct`
- `volatility.base_atr_contraction_ratio`
- `volume.base_amount_contraction_ratio`
- `support.base_low_above_ma20_or_ma30`
- `support.base_low_above_prior_breakout_level`

#### 突破触发

- `level_breakout.prior_60d_close_high_excluding_today`
- `level_breakout.trigger_level`
- `level_breakout.breakout_margin_pct`
- `candlestick.close_location_value`
- `volume.breakout_amount_ratio`

#### 失败风险

- `risk.rest_duration_too_short`
- `risk.noisy_ma_convergence_breakdown`
- `risk.single_bull_then_bearish_pullback`
- `risk.failed_breakout_back_into_base`
- `risk.distribution_day_count`

### 5.3 初始参数搜索空间

以下是研究网格，不是生产硬阈值：

| 因子 | 初始搜索空间 |
| --- | --- |
| 盘整持续时间 | 5-10、10-20、20-40 个交易日 |
| 平台最大回撤 | 8%、12%、15% |
| 盘整 ATR / 原上涨段 ATR | 0.6-0.9 |
| 盘整成交额 / 原上涨段成交额 | 0.5-0.8 |
| 观察位距触发位 | 0% 至 -3%、-3% 至 -5% |
| 突破成交额比 | 1.0-1.5、1.5-2.5、超过 2.5 |
| 突破幅度 | 0-1%、1-3%、超过 3% |
| 观察有效期 | 5、10、15 个交易日 |

参数选择必须依据正负样本召回、分桶收益和滚动稳定性，禁止只选单窗口收益最高值。

## 6. L3 标签设计

新增候选标签：

- `anomaly.trend_seed_detected`
- `technical_context.prior_uptrend_confirmed`
- `technical_pattern.uptrend_consolidation_formed`
- `technical_pattern.uptrend_consolidation_ready`
- `technical_pattern.uptrend_consolidation_new_high_breakout`
- `risk_state.consolidation_invalidated`
- `risk_state.failed_rebreakout`

标签必须由已注册 L2 原语确定性派生，并保存原语输入、版本和匹配结果。

## 7. L4 StagePipeline 设计

策略版本 `candidate_v1` 的阶段顺序：

1. `quality_gate`
2. `candidate_source_merge`
3. `listing_and_liquidity_gate`
4. `prior_trend_gate`
5. `weekly_context_gate`
6. `consolidation_quality_gate`
7. `risk_exclusion_gate`
8. `observation_state_assignment`
9. `confirmed_breakout_trigger`
10. `ranking_and_daily_limit`

关键规则：

- 行业、概念和市场宽度第一版主要用于排序、每日数量控制和诊断，不作为所有样本统一硬门槛。
- 弱市场 `breadth_ma20 < 35%` 时，默认研究每日 Top2；其他环境研究每日 Top5。
- 同一股票正式信号默认设置 10 个交易日冷却期。
- S3 可以每天更新观察状态，但不得重复生成正式信号。
- 每一阶段必须输出 pass/reject/score 原因。

## 8. L5 输出设计

### 8.1 ObservationCandidate

S3 输出至少包含：

- `asset_id`、`observation_date`、`state_version`。
- `candidate_source_tags`。
- 原趋势、盘整和观察位证据。
- `trigger_level`、距触发位比例、平台低点。
- 状态有效期和失效条件。
- 排名分与分项解释。

### 8.2 StrategySignal

S4 输出至少包含：

- `strategy_id`、`strategy_version`、`signal_date`。
- `asset_id`、`trigger_level`、`breakout_margin_pct`。
- `source_observation_id`。
- 通过的趋势、盘整、突破和风险标签。
- 排名、警告和完整解释。

没有 S3 历史记录时，允许当日同时建立观察记录并触发 S4，但必须证明过去窗口内 S2 已成立；不得因为缺少例行跟踪文件而阻断可复现回放。

## 9. L6 回测与验收设计

### 9.1 样本语义门

实现前先对现有样本重新标记：

- `target_family=trend_consolidation_rebreakout`
- `adjacent_family`
- `negative_or_wait`

早期反转、单次急拉、鱼尾加速和无充分盘整的 follow-through 不计入本策略核心正样本。相邻形态保留，但不能稀释核心策略召回率。

### 9.2 候选池对照

同一窗口至少比较：

1. `full_market_trend_pool`
2. `anomaly_seed_pool`
3. `trend_consolidation_union_pool`

重点指标：

- 日均候选数和候选压缩比例。
- 核心正样本召回率。
- 异动池相对全市场池的召回损失。
- E0→S1、S1→S2、S2→S3、S3→S4 转化率。
- 各状态失效原因分布。

异动层第一阶段目标：相对全市场池减少 50% 至 80% 的优先分析数量，同时核心正样本召回损失不超过 10 个百分点。该目标用于判断异动层是否有聚焦价值，不等同于生产准入。

### 9.3 事件回测

统一使用：

- 入场：T+1 开盘。
- H5：入场质量主指标。
- H10：趋势延续辅助指标。
- H20：尾部和中期延续风险参考。
- 主比较组：同一 `CandidatePoolPolicy` 候选池按信号日等权。
- 其他市场基准：沿用评估配置，不在策略代码中硬编码。

第一版交易管理仅做诊断：

- 5 个交易日最大持有期。
- `stop_loss_pct=-0.10` 候选。
- 不设置固定止盈。

交易管理不得掩盖选股本身的召回和排序问题，必须同时报告无止损基准。

### 9.4 进入 test_tracking 的最低设计门槛

除通用生命周期标准外，本策略还应满足：

- 核心正样本召回率不低于 70%。
- 核心硬负样本不得被 S4 大量误召回，误召回必须逐条归因。
- H5 完成样本数不低于 50。
- H5 平均收益和中位收益均大于 0。
- H5 胜率不低于 55%。
- H5 相对候选池等权超额收益大于 0。
- 至少三个滚动时间窗口方向一致，不允许只依赖单月结果。
- 连续三个交易日 dry-run 成功。
- 用户明确批准进入 `test_tracking`。

这些门槛不授权 `active_production`；正式生产仍受 `docs/standards/011-strategy-lifecycle-gates.md` 约束。

## 10. 数据与错误处理

- 所有日线、周线和上下文数据必须按 `signal_date` as-of 对齐。
- 前高、平台高点和平台低点计算必须排除当前交易日，避免把触发结果泄漏进触发条件。
- 历史不足时输出 `insufficient_history`，不得自动缩短窗口。
- 核心价格和成交额字段缺失时阻断状态判断。
- 行业、概念或市场宽度缺失时保留缺失警告；第一版不因辅助上下文缺失伪造通过结果。
- qfq 调整锚点、输入数据版本、策略版本和代码版本必须进入产物 provenance。
- 任一显式候选池 key 缺失时任务失败，不允许静默回退到其他池。

## 11. 确定性产物

每次扫描至少生成：

- `candidate_pool_snapshot.json`
- `state_snapshot.json`
- `observation_candidates.json`
- `strategy_signals.json`
- `rejected_candidates.json`
- `scan_summary.json`
- `report.md`

每次回测至少生成：

- `event_backtest.json`
- `candidate_pool_benchmark.json`
- `stage_conversion_report.json`
- `threshold_diagnostics.json`
- `closed_loop_review.json`

JSON 是事实来源，CSV 和 Markdown 仅用于人工审阅。

## 12. 测试要求

### 12.1 L2

- 当前日排除测试。
- 盘整窗口边界测试。
- ATR、成交额收缩和平台支撑的纯函数测试。
- 缺失值和历史不足测试。

### 12.2 L3

- 正样本状态标签测试。
- 硬负样本失效标签测试。
- 同样输入重复计算结果一致性测试。

### 12.3 L4/L5

- 双候选池合并与来源保留测试。
- StagePipeline pass/reject/score 原因测试。
- S3 不产生正式信号测试。
- S4 只在确认新高后产生信号测试。
- 冷却期和弱市场每日限额测试。

### 12.4 L6

- T+1 入场和 H5/H10/H20 口径测试。
- 候选池显式 key 回放测试。
- 异动池、全市场池和并集池对照测试。
- 滚动窗口稳定性测试。

### 12.5 架构边界

- L0-L6 不得导入 `stock_lobster.research` 或 `stock_lobster.app`。
- L2 只消费 `AnalysisSnapshot`。
- L3 只引用已注册 L2 原语。
- L4 只引用已批准字段和标签。
- 只有 L5 生成 `StrategySignal`。
- 只有 L6 生成回测结果。

## 13. 分阶段落地

### 阶段 A：样本和口径

- 给现有样本补充核心策略族标记。
- 固化盘整、观察、新高突破和失效定义。
- 建立核心正样本、相邻样本和硬负样本验收集。

### 阶段 B：L2/L3

- 复用现有趋势与质量原语。
- 新增盘整、异动、突破触发和失败风险原语。
- 注册状态标签并完成样本测试。

### 阶段 C：L4/L5

- 新增三个 `CandidatePoolPolicy`。
- 新增状态化 StagePipeline 和候选策略配置。
- 生成观察候选和确认突破信号。

### 阶段 D：L6 闭环

- 完成三候选池同窗对照。
- 完成事件回测、候选池等权 benchmark 和滚动稳定性。
- 输出是否进入 `test_tracking` 的证据包。

### 阶段 E：例行测试跟踪

- 用户批准后才新增或调整例行作业。
- 新策略以独立 `test_tracking` 任务运行。
- 不替换现有例行策略，不写入正式生产信号入口。

## 14. 已确认决策

- 采用固定窗口白盒状态机作为第一版，不使用机器学习。
- 盘整末期进入观察池，确认新高才生成正式信号。
- 采用异动优先、全市场兜底的双候选池。
- 异动不是正式信号的硬前置条件。
- 两类候选入口共用一套 L1-L6 主干。
- H5 为主指标，H10 为延续性辅助，H20 为风险参考。
- 第一版基本面与新闻只作为未来扩展，不进入硬过滤。
- 第一阶段仅允许 `research_only`，不得直接进入正式生产。
