"""Reusable request builders for steady uptrend breakout research cases."""

from __future__ import annotations

from stock_lobster.core.ids import RunId
from stock_lobster.l1_analysis_snapshot.schema import AnalysisSnapshot
from stock_lobster.l2_primitives import build_default_primitive_registry
from stock_lobster.l3_labels import build_default_label_registry
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
)


STEADY_UPTREND_BREAKOUT_LABELS: tuple[LabelHypothesis, ...] = (
    LabelHypothesis(
        label_id="technical_pattern.steady_uptrend_stock",
        category="technical_pattern",
        primitive_ids=(
            "moving_average.close_above_ma20",
            "moving_average.close_above_ma60",
            "moving_average.ma20_above_ma60",
            "moving_average.ma60_above_ma120",
            "trend.ma20_rising_20d",
            "risk.max_drawdown_60d_controlled",
        ),
        proposed_logic="steady trend primitives are true",
        reason="沉淀稳健趋势股标签。",
    ),
    LabelHypothesis(
        label_id="technical_pattern.steady_uptrend_new_high_breakout",
        category="technical_pattern",
        primitive_ids=(
            "moving_average.close_above_ma20",
            "moving_average.close_above_ma60",
            "moving_average.ma20_above_ma60",
            "moving_average.ma60_above_ma120",
            "trend.ma20_rising_20d",
            "risk.max_drawdown_60d_controlled",
            "level_breakout.close_new_high_60d",
        ),
        proposed_logic="steady trend primitives and new high are true",
        reason="沉淀稳健趋势股向上突破标签。",
    ),
    LabelHypothesis(
        label_id="composite_setup.steady_uptrend_breakout_watch",
        category="composite_setup",
        primitive_ids=(
            "moving_average.close_above_ma20",
            "moving_average.close_above_ma60",
            "moving_average.ma20_above_ma60",
            "moving_average.ma60_above_ma120",
            "trend.ma20_rising_20d",
            "risk.max_drawdown_60d_controlled",
            "level_breakout.close_new_high_60d",
            "volume_liquidity.amount_ratio_20d_high",
        ),
        proposed_logic="steady trend, new high breakout, and volume confirmation are true",
        reason="沉淀 L4 可召回的稳健上升趋势突破关注准备态。",
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
        ("ma60", metrics.ma60),
        ("ma120", metrics.ma120),
        ("ma20_slope_20d", metrics.ma20_slope_20d),
        ("amount_ratio_20d", metrics.amount_ratio_20d),
        ("max_drawdown_60d", metrics.max_drawdown_60d),
        ("convergence_5_10_20_pct", metrics.convergence_5_10_20_pct),
        ("close_new_high_60d_flag", 1 if metrics.close_new_high_60d_flag else 0),
    )
    features: dict[str, object] = {
        "pub_stock_daily_kline.close": metrics.close,
        "pub_stock_daily_kline.amount": 0,
    }
    for index, (indicator_name, indicator_value) in enumerate(indicators, start=1):
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
) -> IndividualStockStrategyResearchRequest:
    """Build a research workflow request from scanner metrics."""

    return IndividualStockStrategyResearchRequest(
        case_id=f"steady_uptrend_breakout.{metrics.asset_id}.{metrics.trade_date}",
        title="稳健上升趋势突破关注样本",
        thesis="样本处于均线多头趋势，回撤可控，并出现新高突破和量能确认。",
        snapshot=snapshot_from_trend_breakout_metrics(metrics),
        primitive_hypotheses=STEADY_UPTREND_BREAKOUT_PRIMITIVES,
        label_hypotheses=STEADY_UPTREND_BREAKOUT_LABELS,
        strategy_id="strategy.steady_uptrend_breakout_watch",
        strategy_name="稳健上升趋势突破关注策略",
        notes=("由 steady_uptrend_breakout_research_scan 扫描候选生成。",),
    )


def run_steady_uptrend_breakout_case(
    metrics: TrendBreakoutMetrics,
) -> IndividualStockStrategyResearchResult:
    """Run the standard research workflow for one scanner candidate."""

    return IndividualStockStrategyResearchWorkflow(
        primitive_registry=build_default_primitive_registry(),
        label_registry=build_default_label_registry(),
    ).run(build_steady_uptrend_breakout_request(metrics))
