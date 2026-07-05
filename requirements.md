# Stock Lobster 需求文档 v0.1

## 1. 项目定位

Stock Lobster 是一个面向 A 股的多源数据策略研究、分析编排与信号构建系统。

Stock Lobster 不负责生产权威事实数据。原始行情、基本面、宏观、行业、统计指标等事实数据由外部数据生产系统负责生产、质检和对外暴露取数规范。Stock Lobster 只负责理解这些取数规范，并基于可信数据做分析、语义构建、策略生成、回测和跟踪。

系统目标不是单纯做因子计算或回测，而是形成一条完整闭环：

```text
外部数据契约接入
-> 个股多维画像
-> 分析快照
-> 原语判断
-> 标签快照
-> 白盒策略 DSL
-> 选股结果
-> 自动回测
-> 用户确认
-> 观察池
-> 未来跟踪
-> 定期复盘和策略优化
```

核心使用方式是：用户可以围绕一个个股或一种个股形态，让系统从技术形态、基本面、行业、宏观、热度等多个维度沉淀出可解释的召回策略，再基于策略选股、验证回测效果、跟踪未来效果，并定期分析优化。

## 2. 初期范围

### 2.1 资产范围

初期只覆盖 A 股。

ETF、可转债、港股、美股、Crypto 等资产可以作为未来扩展方向，但不进入第一阶段实现范围。

### 2.2 数据源范围

初期可以复用远程服务器上的 `<external_producer_root>` 项目作为外部数据生产系统。

未来预计接入的数据类型包括：

- 技术形态数据
- 价格和成交量统计数据
- 均线、波动率等技术指标
- 基本面数据
- 行业、概念、板块数据
- 市场热度和人气数据
- 宏观分析数据
- 资金流数据
- 人工沉淀的研究记录或结构化观察

新增数据源必须先由外部数据生产系统完成生产、质量检查和取数规范暴露，然后 Stock Lobster 才能注册为可访问 DataAsset。

## 3. 核心使用场景

### 3.1 从个股形态生成策略

用户给出一只个股，或描述一种个股形态。

系统需要完成：

1. 从多维数据分析该个股当前状态。
2. 抽取可复用的白盒条件。
3. 生成一个或多个候选召回策略。
4. 将候选策略转换成可版本化的 StrategyDSL。
5. 自动运行多口径回测。
6. 输出选股结果、排序依据和回测证据。
7. 等待用户确认后，才能进入观察池。

### 3.2 多过滤逻辑选股

选股结果不能只是一个股票列表。

策略需要支持：

- 多个召回条件
- 多层过滤条件
- 排除条件
- 风险过滤
- 最终排序逻辑
- 策略专属评分规则

每只入选股票都需要说明为什么被召回、通过了哪些过滤、排名为什么靠前。

### 3.3 自动生成策略和自动回测

系统允许自动生成候选策略，并自动执行回测。

但是候选策略默认处于 `pending` 状态，不能自动进入观察池，也不能自动成为生产策略。

用户确认后，候选策略才能变为 `approved`，并进入观察池做未来跟踪。

### 3.4 观察池和未来跟踪

用户确认后的策略进入观察池。

系统需要持续跟踪策略未来表现，并对比回测预期。

跟踪结果需要支持：

- 策略级别表现
- 信号级别表现
- 个股级别表现
- 多周期收益表现
- 相对基准表现
- 失败案例收集
- 定期复盘和优化建议

### 3.5 定期策略优化

系统需要定期分析观察池策略的表现。

优化建议必须是白盒化的，不能悄悄修改已经批准的策略版本。

如果需要调整策略，必须生成新的策略版本或候选策略。

### 3.6 两类业务链路

系统需要同时支持两类业务链路。

第一类是全市场策略筛选链路：

```text
全 A 股票池
-> 质量层
-> 趋势层
-> 精筛层
-> 介入层
-> 排序
-> 选股结果
```

该链路适合主动扫描全市场机会，目标是发现尚未明显异动但已经满足策略条件的股票。

第二类是异动观察池分析链路：

```text
异动观察池
-> 质量分析
-> 趋势分析
-> 精筛标准
-> 是否介入
-> 排序或观察结论
```

该链路适合事件驱动和盘后复盘，目标是判断已经发生异动的股票是否值得继续跟踪或介入。

### 3.7 统一技术抽象

两类业务链路必须使用同一套技术方案，不应实现成两套割裂系统。

统一抽象如下：

```text
CandidatePoolPolicy
-> AnalysisSnapshot
-> StagePipeline
-> StrategyDSL
-> Signal Engine
-> Backtest Engine
-> Observation Tracking
```

其中：

- `CandidatePoolPolicy` 定义候选股票池如何产生。
- `AnalysisSnapshot` 定义候选股票在某个日期上的分析视图。
- `StagePipeline` 定义质量层、趋势层、精筛层、介入层等阶段。
- `StrategyDSL` 定义每个阶段的召回、过滤、排除和排序规则。
- `Signal Engine` 统一生成结果，不区分入口来自全市场还是观察池。
- `Backtest Engine` 必须能复现候选池生成逻辑，避免回测偏差。

两类链路的差异只应体现在配置上：

- 候选池来源不同。
- 阶段名称和阈值不同。
- 排序目标不同。
- 回测口径和跟踪周期不同。

底层执行框架、日志、版本、审计、回测、观察跟踪应保持一致。

## 4. 分层架构要求

系统必须遵循当前 `sys_command.md` 中定义的分层契约。

Stock Lobster 内部不设置事实数据生产层。L0 的职责是理解外部数据契约和安全取数，不负责采集、清洗、修复或改写外部数据。

```text
L0 Data Access Contract Layer
L1 Analysis Snapshot Layer
L2 Primitive Function Layer
L3 Label Snapshot Layer
L4 Strategy DSL Layer
L5 Signal Engine Layer
L6 Backtest Engine Layer
```

分层规则：

- 下层不能依赖上层。
- 上层只能消费下层产物。
- 不允许跨层绕行。
- 策略层不能直接访问原始价格数据。
- Agent 不能生产事实数据。
- 信号只能由 L5 生成。
- 回测结果只能由 L6 生成。

## 5. 核心对象定义

### 5.1 数据资产（DataAsset）

DataAsset 描述外部数据生产系统暴露出来的源表、文件、API 产物或派生数据集。

DataAsset 是取数契约，不是 Stock Lobster 生产的数据事实。

字段建议包括：

- asset_id
- source_type
- source_name
- table_name 或 storage_path
- field_schema
- update_frequency
- owner_layer
- quality_status
- first_available_date
- latest_available_date

### 5.2 分析快照（AnalysisSnapshot）

AnalysisSnapshot 是某只股票在某个日期上的稳定分析快照，也可以理解为策略分析视角下的 FeatureSnapshot。

AnalysisSnapshot 由 Stock Lobster 根据外部数据契约读取结果后构建，用于后续 Primitive 和 Label 计算。它不是权威事实数据源，必须能追溯到外部 DataAsset、查询条件和版本。

可包含：

- 价格和成交量特征
- 均线特征
- 波动率特征
- 基本面特征
- 行业和概念特征
- 宏观上下文特征
- 热度和人气特征

要求：

- 只能由 L1 生成。
- 必须可复现。
- 必须包含 `analysis_version` 和 `run_id`。
- 必须记录来源数据依赖。

### 5.3 原语（Primitive）

Primitive 是作用于 AnalysisSnapshot 的纯函数。

要求：

- 输入只能是 AnalysisSnapshot。
- 输出只能是 boolean 或 score。
- 不能绕过 L0 直接读取外部原始数据表。
- 不能保存状态。
- 必须版本化。
- 必须注册后才能被使用。

示例：

```text
is_ma_converging
is_volume_expanding
is_breakout_near_high
is_fundamental_improving
is_industry_heat_rising
```

### 5.4 标签快照（LabelSnapshot）

LabelSnapshot 是由 Primitive 派生出的确定性标签快照。

要求：

- 只能由 L3 生成。
- 必须包含 `label_version` 和 `run_id`。
- 必须可复现。
- 必须基于快照生成。
- 暴露给 StrategyDSL 的只能是 LabelSnapshot 字段。

示例：

```text
ma_convergence_breakout
volume_confirmed_breakout
fundamental_repair
industry_rotation_candidate
low_volatility_accumulation
```

### 5.5 策略 DSL（StrategyDSL）

StrategyDSL 是白盒策略定义。

它需要描述：

- 策略元信息
- 候选池策略
- 阶段流水线
- 召回条件
- 过滤条件
- 排除条件
- 排序逻辑
- 回测口径
- 跟踪周期
- 版本信息

要求：

- 只能引用 LabelSnapshot 字段和被批准的元数据字段。
- 不能直接引用原始价格数据。
- 必须确定性执行。
- 必须版本化。
- 必须人类可读。

### 5.6 候选池策略（CandidatePoolPolicy）

CandidatePoolPolicy 定义一次策略运行的候选股票池来源。

它需要支持：

- 全 A 股票池。
- 指数成分股票池。
- 行业或概念股票池。
- 外部异动观察池。
- 已批准策略的历史观察池。
- 用户手动输入股票池。

CandidatePoolPolicy 必须版本化，并且必须能在回测时复现。

对于异动观察池链路，进入观察池的规则本身也是 CandidatePoolPolicy 的一部分，不能只记录“来自观察池”。

### 5.7 阶段流水线（StagePipeline）

StagePipeline 定义策略执行过程中的分层过滤和分析阶段。

典型阶段包括：

- 质量层
- 趋势层
- 精筛层
- 介入层
- 排序层

每个阶段需要定义：

- stage_id
- stage_name
- stage_type
- input_scope
- pass_conditions
- reject_conditions
- score_fields
- output_fields
- explain_template

StagePipeline 应同时支持全市场筛选和异动观察池分析。

### 5.8 策略候选（StrategyCandidate）

StrategyCandidate 是系统自动生成、但尚未被用户批准的候选策略。

候选策略可以自动回测，但不能进入观察池，也不能生成正式生产信号。

### 5.9 策略信号（StrategySignal）

StrategySignal 是由 L5 生成的选股信号。

字段建议包括：

- strategy_id
- strategy_version
- signal_date
- stock_code
- stock_name
- triggered_labels
- recall_reasons
- passed_filters
- warning_checks
- ranking_score
- rank
- suggested_tracking_horizons

### 5.10 回测结果（BacktestResult）

BacktestResult 是由 L6 生成的回测结果。

字段建议包括：

- strategy_id
- strategy_version
- backtest_period
- benchmark
- selection_frequency
- holding_horizon
- return_metrics
- drawdown_metrics
- win_rate
- hit_rate_by_horizon
- turnover
- sample_size
- failure_cases
- parameter_set

### 5.11 观察记录（ObservationRecord）

ObservationRecord 记录已确认策略信号的未来跟踪结果。

字段建议包括：

- strategy_id
- strategy_version
- signal_id
- stock_code
- observation_date
- tracking_horizons
- future_returns
- benchmark_returns
- expectation_met
- review_status

## 6. 白盒策略生成要求

### 6.1 白盒优先

召回策略必须白盒化。

用户需要能看懂：

- 股票为什么被召回。
- 触发了哪些标签。
- 通过了哪些过滤条件。
- 为什么排序靠前。
- 历史回测证据是什么。
- 后续观察周期是什么。

黑盒模型后续可以作为辅助评分，但初期不能替代白盒 StrategyDSL。

### 6.2 候选策略来源

系统可以从以下来源生成候选策略：

- 用户给出的一只股票。
- 用户描述的一类股票形态。
- 历史上重复出现的成功形态。
- 已有 AnalysisSnapshot 和 Label 的组合。
- 观察池中的成功案例。
- 观察池中的失败案例。

生成出来的策略默认是候选策略，状态为 `pending`。

候选策略可以由 Agent 起草，但 Agent 只能使用外部事实数据、已注册分析快照、已注册 Primitive 和已注册 Label，不允许自己补充、改写或生成事实数据。

### 6.3 用户确认边界

系统可以自动执行：

- 生成候选策略。
- 运行回测。
- 生成解释。
- 推荐跟踪周期。
- 提出优化建议。

系统必须等待用户确认后才能：

- 将候选策略提升为正式策略。
- 将策略加入观察池。
- 替换已批准策略版本。
- 发布新策略的正式信号。

## 7. 选股结果要求

一次选股运行需要输出排序后的股票列表。

每条结果至少包含：

- 股票代码
- 股票名称
- 信号日期
- 策略名称和版本
- 候选池来源
- 召回原因
- 触发标签
- 各阶段通过情况
- 过滤条件摘要
- 排名分数
- 排名
- 策略回测摘要
- 建议跟踪周期
- 风险提示

选股流程需要支持：

- 候选池策略
- 召回规则
- 硬过滤
- 软过滤
- 排除规则
- 阶段流水线
- 排序规则
- 排名并列处理
- 最大选股数量
- 行业或概念分散约束

不论入口是全 A 股票池还是异动观察池，输出结构都应保持一致。

每条结果都应能解释：

- 它如何进入候选池。
- 它通过了哪些阶段。
- 它在哪些阶段被加分或扣分。
- 它为什么最终入选或被排除。
- 它的排序分数由哪些部分构成。

## 8. 回测要求

由于不同策略目标不同，回测必须支持多种口径。

初期建议支持：

- 信号日后事件收益回测
- 固定持有周期回测
- 每日滚动选股回测
- 排名分桶表现对比
- 相对基准表现
- 回撤分析
- 失败案例分析

跟踪和回测周期需要可配置，例如：

```text
1 个交易日
3 个交易日
5 个交易日
10 个交易日
20 个交易日
60 个交易日
```

回测口径需要绑定到策略版本或 EvaluationProfile。

不同类型策略可以有不同默认周期：

- 短线异动策略：1/3/5 个交易日。
- 波段策略：10/20 个交易日。
- 中期趋势策略：20/60 个交易日。
- 基本面修复策略：20/60 个交易日或更长。

## 9. 未来跟踪要求

未来跟踪需要验证实盘观察表现是否符合回测预期。

系统需要支持：

- 多跟踪周期
- 策略级别跟踪
- 信号级别跟踪
- 个股级别跟踪
- 相对基准跟踪
- 定期汇总报告
- 失败案例归因
- 优化建议生成

跟踪结果不能修改历史策略定义。

如果策略需要优化，必须生成新的策略版本。

## 10. 自动发现、注册和 Agent 边界

系统需要支持自动发现，但自动化边界必须清楚。

允许自动化：

- 从已批准外部数据契约中发现新表或新字段。
- 在外部质量状态通过、字段含义明确后注册新的 AnalysisSnapshot 字段。
- 自动运行依赖满足的已注册 Primitive。
- 自动生成依赖满足的已注册 Label。
- 自动把已批准的 LabelSnapshot 字段暴露给 StrategyDSL。
- 自动为候选策略运行回测。

限制自动化：

- 不能静默发明正式 Primitive。
- 不能静默发明正式 Label。
- 不能静默发布正式策略。
- 不能静默修改已批准策略。
- 不能让策略层绕过 LabelSnapshot 读取原始数据。
- 不能让 Agent 生产任何事实数据。

系统可以生成候选 Primitive、候选 Label、候选策略，但这些都是策略语义候选，不是事实数据。它们需要经过确认后才能进入正式 registry。

Agent 的定位是工具和数据使用者，而不是事实来源。

Agent 可以：

- 理解外部数据契约。
- 选择合适的取数工具。
- 编排分析流程。
- 起草候选 Primitive、候选 Label 和候选 StrategyDSL。
- 触发信号引擎和回测引擎。
- 解释选股、回测和跟踪结果。
- 提出优化建议。

Agent 不可以：

- 采集、清洗、修复或改写事实数据。
- 直接写入外部数据生产系统。
- 凭经验补充缺失事实。
- 把推测写成事实字段。
- 绕过 L0 数据契约取数。
- 绕过 L5/L6 自己生成正式信号或回测结果。

## 11. 与外部事实数据生产系统的关系

远程服务器上的 `<external_producer_root>` 初期建议保持独立运行。

推荐映射关系：

```text
token_daily_details / token_weekly_details / token_monthly_details
-> 外部事实数据，由 L0 Data Access Contract Layer 读取

价格、成交量、波动率、均线统计表
-> 外部基础指标，由 L1 Analysis Snapshot Layer 读取并形成分析快照

convergence、anomaly、stock_recall 等表
-> 先作为 L1 分析快照输入或 L2/L3 候选语义输入
-> 最终归属取决于语义和版本化改造
```

当前项目不应该直接粗暴合并整个外部事实数据生产仓库。

不建议迁入：

- venv
- logs
- tracker 运行态文件
- reports 历史报告
- old_version
- tmp 临时文件

优先建设适配层、Catalog 和 Registry。

## 12. 非功能要求

### 12.1 可复现

每个 AnalysisSnapshot、Label、StrategySignal、BacktestResult、ObservationRecord 都需要通过版本和 run_id 复现。

### 12.2 可审计

系统需要能回答：

- 这个特征来自哪些数据？
- 这个标签由哪些 Primitive 生成？
- 这只股票触发了哪些标签？
- 这只股票为什么排名靠前？
- 这个信号由哪个策略版本生成？
- 这个回测结果使用了哪个回测口径？

### 12.3 可扩展

新增数据源不应该要求重写策略引擎、信号引擎或回测引擎。

### 12.4 层级安全

系统需要通过代码结构、registry 校验和测试来约束层级边界。

### 12.5 人工控制

系统可以自动化研究过程，但策略进入观察池、策略版本升级、正式信号发布必须有人确认。

## 13. 策略生命周期

建议策略状态包括：

```text
draft
pending_backtest
backtested
pending_approval
approved
observing
paused
retired
```

状态说明：

- `draft`：草稿，尚未形成完整 DSL。
- `pending_backtest`：等待自动回测。
- `backtested`：已经完成回测。
- `pending_approval`：等待用户确认。
- `approved`：用户已确认，可以进入观察池。
- `observing`：正在进行未来跟踪。
- `paused`：暂停观察或暂停使用。
- `retired`：策略退役，只保留历史记录。

## 14. 阶段路线

### 里程碑 1：需求和架构基线

- 固化需求文档。
- 固化分层契约。
- 定义核心对象 schema。
- 定义策略生命周期。

### 里程碑 2：数据适配和资产目录

- 接入外部事实数据生产系统产出的 MySQL 表。
- 建立 DataAsset Catalog。
- 定义 AnalysisSnapshot schema。
- 将现有统计表映射为分析快照输入。

### 里程碑 3：Primitive 和 Label Registry

- 定义 Primitive 注册格式。
- 实现第一批白盒 Primitive。
- 定义 Label 生成规则。
- 生成版本化 LabelSnapshot。

### 里程碑 4：StrategyDSL 和候选策略生成

- 定义 DSL schema。
- 支持从个股形态生成候选策略。
- 支持召回、过滤、排除和排序逻辑。

### 里程碑 5：回测引擎

- 实现多回测口径。
- 生成策略级和信号级回测报告。
- 存储 BacktestResult。

### 里程碑 6：观察池和跟踪系统

- 加入用户确认流程。
- 跟踪已批准策略信号。
- 生成定期跟踪和优化报告。

## 15. 待确认问题

- 新系统自己的 registry 和 snapshot 数据存在哪里？
- StrategyDSL 使用 YAML、JSON、数据库记录，还是 Python 对象？
- 第一个用于生成策略的个股形态是什么？
- 初期回测基准使用哪个：沪深 300、中证 500、中证 1000、全 A 等权，还是按策略类型选择？
- 用户确认流程第一版采用什么形式：命令行、数据库状态、Markdown 审阅文件，还是 Web UI？
- 初期观察池每天自动更新，还是由用户手动触发？
