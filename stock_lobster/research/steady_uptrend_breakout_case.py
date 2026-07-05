"""Reusable request builders for steady uptrend breakout research cases."""

from __future__ import annotations

from stock_lobster.core.ids import RunId
from stock_lobster.l1_analysis_snapshot.schema import AnalysisSnapshot
from stock_lobster.l2_primitives import build_default_primitive_registry
from stock_lobster.l3_labels import build_default_label_registry
from stock_lobster.l6_backtest_engine import BacktestResult
from stock_lobster.research.single_stock_strategy import (
    IndividualStockStrategyResearchRequest,
    IndividualStockStrategyResearchResult,
    IndividualStockStrategyResearchWorkflow,
    LabelHypothesis,
    PrimitiveHypothesis,
)
from stock_lobster.research.trend_breakout_scan import TrendBreakoutMetrics


STEADY_UPTREND_BREAKOUT_PRIMITIVES: tuple[PrimitiveHypothesis, ...] = (
    PrimitiveHypothesis(
        primitive_id="moving_average.close_above_ma20",
        category="moving_average",
        proposed_logic="close > ma20",
        reason="确认价格在 MA20 上方。",
        required_features=("pub_stock_daily_kline.close", "indicator:ma20"),
    ),
    PrimitiveHypothesis(
        primitive_id="moving_average.close_above_ma30",
        category="moving_average",
        proposed_logic="close > ma30",
        reason="确认日线没有跌破 MA30，避免均线黏合后破位的弱质量走势。",
        required_features=("pub_stock_daily_kline.close", "indicator:ma30"),
    ),
    PrimitiveHypothesis(
        primitive_id="moving_average.close_above_ma60",
        category="moving_average",
        proposed_logic="close > ma60",
        reason="确认价格在 MA60 上方。",
        required_features=("pub_stock_daily_kline.close", "indicator:ma60"),
    ),
    PrimitiveHypothesis(
        primitive_id="moving_average.ma20_above_ma60",
        category="moving_average",
        proposed_logic="ma20 > ma60",
        reason="确认短中期均线多头排列。",
        required_features=("indicator:ma20", "indicator:ma60"),
    ),
    PrimitiveHypothesis(
        primitive_id="moving_average.ma60_above_ma120",
        category="moving_average",
        proposed_logic="ma60 > ma120",
        reason="确认中长期均线多头排列。",
        required_features=("indicator:ma60", "indicator:ma120"),
    ),
    PrimitiveHypothesis(
        primitive_id="trend.ma20_rising_20d",
        category="trend",
        proposed_logic="ma20_slope_20d > 0",
        reason="确认趋势均线抬升。",
        required_features=("indicator:ma20_slope_20d",),
    ),
    PrimitiveHypothesis(
        primitive_id="risk.max_drawdown_60d_controlled",
        category="risk",
        proposed_logic="abs(max_drawdown_60d) <= 0.40",
        reason="确认趋势推进中的回撤可控。",
        required_features=("indicator:max_drawdown_60d",),
        threshold_refs=("max_abs_drawdown_60d",),
    ),
    PrimitiveHypothesis(
        primitive_id="risk.max_drawdown_120d_controlled",
        category="risk",
        proposed_logic="abs(max_drawdown_120d) <= 0.55",
        reason="确认历史回撤没有过大，过滤日线持有体验很差的趋势。",
        required_features=("indicator:max_drawdown_120d",),
        threshold_refs=("max_abs_drawdown_120d",),
    ),
    PrimitiveHypothesis(
        primitive_id="risk.ma30_deviation_not_extreme",
        category="risk",
        proposed_logic="ma30_deviation_pct <= 0.35",
        reason="过滤距离 MA30 过远、短期拉高后才召回的候选。",
        required_features=("indicator:ma30_deviation_pct",),
        threshold_refs=("max_ma30_deviation_pct",),
    ),
    PrimitiveHypothesis(
        primitive_id="moving_average.ma30_hold_ratio_90d_sustained",
        category="moving_average",
        proposed_logic="ma30_hold_ratio_90d >= 0.75",
        reason="确认日线趋势有持续承接，过滤频繁跌破 MA30/MA60 的不稳健走势。",
        required_features=("indicator:ma30_hold_ratio_90d",),
        threshold_refs=("min_sustained_ma30_hold_ratio_90d",),
    ),
    PrimitiveHypothesis(
        primitive_id="candlestick.red_k_ratio_20d_healthy",
        category="candlestick",
        proposed_logic="red_k_ratio_20d >= 0.45",
        reason="确认近期红 K 占比不弱，过滤绿 K 偏多、红绿比难看的走势。",
        required_features=("indicator:red_k_ratio_20d",),
        threshold_refs=("min_red_k_ratio_20d",),
    ),
    PrimitiveHypothesis(
        primitive_id="candlestick.long_shadow_ratio_20d_controlled",
        category="candlestick",
        proposed_logic="long_shadow_ratio_20d <= 0.65",
        reason="确认近期上下影线噪声不过高，过滤走势不干净的突破。",
        required_features=("indicator:long_shadow_ratio_20d",),
        threshold_refs=("max_long_shadow_ratio_20d",),
    ),
    PrimitiveHypothesis(
        primitive_id="level_breakout.close_new_high_60d",
        category="level_breakout",
        proposed_logic="close_new_high_60d_flag == true",
        reason="确认价格向上突破近期高点。",
        required_features=("indicator:close_new_high_60d_flag",),
    ),
    PrimitiveHypothesis(
        primitive_id="volume_liquidity.amount_ratio_20d_high",
        category="volume_liquidity",
        proposed_logic="amount_ratio_20d >= 1.5",
        reason="确认突破时存在量能配合。",
        required_features=("indicator:amount_ratio_20d",),
        threshold_refs=("amount_ratio_20d_high",),
    ),
    PrimitiveHypothesis(
        primitive_id="liquidity.total_mv_ge_100e",
        category="liquidity",
        proposed_logic="total_mv >= 1000000",
        reason="剔除总市值低于 100 亿的股票，减少流动性和承载风险。",
        required_features=("pub_stock_daily_basic.total_mv",),
        threshold_refs=("min_total_mv",),
    ),
    PrimitiveHypothesis(
        primitive_id="liquidity.avg_amount_20d_ge_2e",
        category="liquidity",
        proposed_logic="avg_amount_20d_raw >= 2000000000",
        reason="剔除近 20 日平均成交额低于 2 亿的股票；当前 amount 原始值约等于实际成交额(元) * 10。",
        required_features=("indicator:avg_amount_20d",),
        threshold_refs=("min_avg_amount_20d",),
    ),
    PrimitiveHypothesis(
        primitive_id="risk.turnover_rate_20d_controlled",
        category="risk",
        proposed_logic="max_turnover_rate_20d <= 20",
        reason="过滤近 20 日出现极端换手率的拉高爆量形态。",
        required_features=("indicator:max_turnover_rate_20d",),
        threshold_refs=("max_turnover_rate_20d",),
    ),
    PrimitiveHypothesis(
        primitive_id="context.industry_or_concept_strength_hit",
        category="context",
        proposed_logic="strong_industry_hit OR strong_concept_hit",
        reason="确认个股处于强行业或强概念环境中。",
        required_features=("indicator:context_strength_pass",),
    ),
    PrimitiveHypothesis(
        primitive_id="weekly_context.close_above_weekly_ma20",
        category="weekly_context",
        proposed_logic="weekly_close > weekly_ma20",
        reason="确认日线信号发生时，周级别价格仍在主要趋势均线之上。",
        required_features=("pub_stock_weekly_kline.close", "indicator:weekly_ma20"),
    ),
    PrimitiveHypothesis(
        primitive_id="weekly_context.weekly_ma10_above_ma20",
        category="weekly_context",
        proposed_logic="weekly_ma10 > weekly_ma20",
        reason="确认周级别中短期趋势方向向上。",
        required_features=("indicator:weekly_ma10", "indicator:weekly_ma20"),
    ),
    PrimitiveHypothesis(
        primitive_id="weekly_context.weekly_ma20_rising_4w",
        category="weekly_context",
        proposed_logic="weekly_ma20_slope_4w > 0",
        reason="确认周级别 MA20 正在抬升，而不是弱反弹。",
        required_features=("indicator:weekly_ma20_slope_4w",),
    ),
    PrimitiveHypothesis(
        primitive_id="weekly_context.weekly_drawdown_26w_controlled",
        category="weekly_context",
        proposed_logic="abs(weekly_max_drawdown_26w) <= 0.55",
        reason="确认周级别趋势背景没有经历过深回撤。",
        required_features=("indicator:weekly_max_drawdown_26w",),
        threshold_refs=("max_abs_weekly_drawdown_26w",),
    ),
    PrimitiveHypothesis(
        primitive_id="weekly_context.weekly_trend_context_pass",
        category="weekly_context",
        proposed_logic="weekly trend context composite flag == true",
        reason="确认周线趋势背景过滤通过；周线只做背景，不直接替代日线入场质量。",
        required_features=("indicator:weekly_trend_pass",),
    ),
)


STEADY_UPTREND_BREAKOUT_LABELS: tuple[LabelHypothesis, ...] = (
    LabelHypothesis(
        label_id="technical_pattern.steady_uptrend_stock",
        category="technical_pattern",
        primitive_ids=(
            "moving_average.close_above_ma20",
            "moving_average.close_above_ma30",
            "moving_average.close_above_ma60",
            "moving_average.ma20_above_ma60",
            "moving_average.ma60_above_ma120",
            "trend.ma20_rising_20d",
            "risk.max_drawdown_60d_controlled",
            "risk.max_drawdown_120d_controlled",
            "risk.ma30_deviation_not_extreme",
            "candlestick.red_k_ratio_20d_healthy",
            "candlestick.long_shadow_ratio_20d_controlled",
        ),
        proposed_logic="steady trend primitives are true",
        reason="沉淀稳健趋势股标签，并加入日线质量过滤。",
    ),
    LabelHypothesis(
        label_id="technical_pattern.steady_uptrend_new_high_breakout",
        category="technical_pattern",
        primitive_ids=(
            "moving_average.close_above_ma20",
            "moving_average.close_above_ma30",
            "moving_average.close_above_ma60",
            "moving_average.ma20_above_ma60",
            "moving_average.ma60_above_ma120",
            "trend.ma20_rising_20d",
            "risk.max_drawdown_60d_controlled",
            "risk.max_drawdown_120d_controlled",
            "risk.ma30_deviation_not_extreme",
            "candlestick.red_k_ratio_20d_healthy",
            "candlestick.long_shadow_ratio_20d_controlled",
            "level_breakout.close_new_high_60d",
        ),
        proposed_logic="steady trend primitives and new high are true",
        reason="沉淀稳健趋势股向上突破标签，并排除日线质量不足的突破。",
    ),
    LabelHypothesis(
        label_id="technical_context.weekly_uptrend_context",
        category="technical_context",
        primitive_ids=(
            "weekly_context.close_above_weekly_ma20",
            "weekly_context.weekly_ma10_above_ma20",
            "weekly_context.weekly_ma20_rising_4w",
            "weekly_context.weekly_drawdown_26w_controlled",
            "weekly_context.weekly_trend_context_pass",
        ),
        proposed_logic="weekly context primitives are true",
        reason="沉淀日线策略前置的周级别趋势背景标签。",
    ),
    LabelHypothesis(
        label_id="composite_setup.steady_uptrend_breakout_watch",
        category="composite_setup",
        primitive_ids=(
            "moving_average.close_above_ma20",
            "moving_average.close_above_ma30",
            "moving_average.close_above_ma60",
            "moving_average.ma20_above_ma60",
            "moving_average.ma60_above_ma120",
            "trend.ma20_rising_20d",
            "risk.max_drawdown_60d_controlled",
            "risk.max_drawdown_120d_controlled",
            "risk.ma30_deviation_not_extreme",
            "candlestick.red_k_ratio_20d_healthy",
            "candlestick.long_shadow_ratio_20d_controlled",
            "weekly_context.weekly_trend_context_pass",
            "context.industry_or_concept_strength_hit",
            "level_breakout.close_new_high_60d",
            "volume_liquidity.amount_ratio_20d_high",
        ),
        proposed_logic="weekly context, steady trend, daily quality, new high breakout, and volume confirmation are true",
        reason="沉淀 L4 可召回的稳健上升趋势突破关注准备态，同时要求周级别趋势背景和日线质量通过。",
    ),
)


def snapshot_from_trend_breakout_metrics(
    metrics: TrendBreakoutMetrics,
    run_id: RunId | None = None,
) -> AnalysisSnapshot:
    """Build an L1 snapshot-like object from computed research metrics."""

    indicators: tuple[tuple[str, object], ...] = (
        ("ma5", metrics.ma5),
        ("ma10", metrics.ma10),
        ("ma20", metrics.ma20),
        ("ma30", metrics.ma30),
        ("ma60", metrics.ma60),
        ("ma120", metrics.ma120),
        ("ma20_slope_20d", metrics.ma20_slope_20d),
        ("amount_ratio_20d", metrics.amount_ratio_20d),
        ("max_drawdown_60d", metrics.max_drawdown_60d),
        ("max_drawdown_120d", metrics.max_drawdown_120d),
        ("convergence_5_10_20_pct", metrics.convergence_5_10_20_pct),
        ("close_to_high_60d_pct", metrics.close_to_high_60d_pct),
        ("ma20_deviation_pct", metrics.ma20_deviation_pct),
        ("ma30_deviation_pct", metrics.ma30_deviation_pct),
        ("ma30_hold_ratio_30d", metrics.ma30_hold_ratio_30d),
        ("ma30_hold_ratio_60d", metrics.ma30_hold_ratio_60d),
        ("ma30_hold_ratio_90d", metrics.ma30_hold_ratio_90d),
        ("ma30_hold_ratio_120d", metrics.ma30_hold_ratio_120d),
        ("ma60_hold_ratio_120d", metrics.ma60_hold_ratio_120d),
        ("return_20d", metrics.return_20d),
        ("red_k_ratio_20d", metrics.red_k_ratio_20d),
        ("green_k_ratio_20d", metrics.green_k_ratio_20d),
        ("long_shadow_ratio_20d", metrics.long_shadow_ratio_20d),
        ("avg_amount_20d", metrics.avg_amount_20d),
        ("max_turnover_rate_20d", metrics.max_turnover_rate_20d),
        ("avg_turnover_rate_20d", metrics.avg_turnover_rate_20d),
        ("turnover_spike_ratio_20d", metrics.turnover_spike_ratio_20d),
        ("close_new_high_60d_flag", 1 if metrics.close_new_high_60d_flag else 0),
        ("daily_quality_pass", 1 if metrics.daily_quality_pass else 0),
        ("trend_stability_pass", 1 if metrics.trend_stability_pass else 0),
        ("market_cap_liquidity_pass", 1 if metrics.market_cap_liquidity_pass else 0),
        ("turnover_quality_pass", 1 if metrics.turnover_quality_pass else 0),
        ("context_strength_pass", 1 if metrics.context_strength_pass else 0),
        ("strong_industry_hit", 1 if metrics.strong_industry_hit else 0),
        ("strong_concept_hit", 1 if metrics.strong_concept_hit else 0),
        ("pre_breakout_watch", 1 if metrics.pre_breakout_watch else 0),
        ("setup_score", metrics.setup_score),
        ("weekly_ma5", metrics.weekly_ma5),
        ("weekly_ma10", metrics.weekly_ma10),
        ("weekly_ma20", metrics.weekly_ma20),
        ("weekly_ma20_slope_4w", metrics.weekly_ma20_slope_4w),
        ("weekly_max_drawdown_26w", metrics.weekly_max_drawdown_26w),
        ("weekly_trend_pass", 1 if metrics.weekly_trend_pass else 0),
    )
    features: dict[str, object] = {
        "pub_stock_daily_kline.close": metrics.close,
        "pub_stock_daily_kline.amount": 0,
    }
    if metrics.total_mv is not None:
        features["pub_stock_daily_basic.total_mv"] = metrics.total_mv
    if metrics.turnover_rate is not None:
        features["pub_stock_daily_basic.turnover_rate"] = metrics.turnover_rate
    if metrics.weekly_close is not None:
        features["pub_stock_weekly_kline.close"] = metrics.weekly_close
    if metrics.weekly_asof_trade_date is not None:
        features["pub_stock_weekly_kline.period_end_date"] = metrics.weekly_asof_trade_date
    for index, (indicator_name, indicator_value) in enumerate(indicators, start=1):
        if indicator_value is None:
            continue
        features[f"pub_stock_daily_indicator.{index}.indicator_name"] = indicator_name
        features[f"pub_stock_daily_indicator.{index}.indicator_value"] = indicator_value

    return AnalysisSnapshot(
        stock_code=metrics.asset_id,
        snapshot_date=metrics.trade_date,
        analysis_version="analysis_v1",
        run_id=run_id or RunId("steady_uptrend_breakout_research"),
        features=features,
    )


def build_steady_uptrend_breakout_request(
    metrics: TrendBreakoutMetrics,
    backtest_result: BacktestResult | None = None,
) -> IndividualStockStrategyResearchRequest:
    """Build a research workflow request from scanner metrics."""

    return IndividualStockStrategyResearchRequest(
        case_id=f"steady_uptrend_breakout.{metrics.asset_id}.{metrics.trade_date}",
        title="稳健上升趋势突破关注样本",
        thesis="样本处于周级别上升趋势背景，日线均线多头、回撤和日线质量可控，并出现新高突破和量能确认。",
        snapshot=snapshot_from_trend_breakout_metrics(metrics),
        primitive_hypotheses=STEADY_UPTREND_BREAKOUT_PRIMITIVES,
        label_hypotheses=STEADY_UPTREND_BREAKOUT_LABELS,
        strategy_id="strategy.steady_uptrend_breakout_watch",
        strategy_name="稳健上升趋势突破关注策略",
        backtest_result=backtest_result,
        notes=("由 steady_uptrend_breakout_research_scan 扫描候选生成。",),
    )


def run_steady_uptrend_breakout_case(
    metrics: TrendBreakoutMetrics,
    backtest_result: BacktestResult | None = None,
) -> IndividualStockStrategyResearchResult:
    """Run the standard research workflow for one scanner candidate."""

    return IndividualStockStrategyResearchWorkflow(
        primitive_registry=build_default_primitive_registry(),
        label_registry=build_default_label_registry(),
    ).run(build_steady_uptrend_breakout_request(metrics, backtest_result=backtest_result))
