"""Default L2 primitive registry for early research workflows."""

from __future__ import annotations

from stock_lobster.l2_primitives.registry import PrimitiveDefinition, PrimitiveRegistry
from stock_lobster.l2_primitives import technical


def build_default_primitive_registry() -> PrimitiveRegistry:
    """Build the default in-memory L2 primitive registry."""

    registry = PrimitiveRegistry()
    for primitive in (
        PrimitiveDefinition(
            primitive_id="data_quality.basic_snapshot_ready",
            version="v1",
            function=technical.basic_snapshot_ready,
            output_type="bool",
            description="Core L1 daily kline fields are available.",
        ),
        PrimitiveDefinition(
            primitive_id="moving_average.close_above_ma20",
            version="v1",
            function=technical.close_above_ma20,
            output_type="bool",
            description="Close is above MA20.",
        ),
        PrimitiveDefinition(
            primitive_id="moving_average.close_above_ma30",
            version="candidate_v1",
            function=technical.close_above_ma30,
            output_type="bool",
            description="Close is above MA30.",
        ),
        PrimitiveDefinition(
            primitive_id="moving_average.close_above_ma60",
            version="candidate_v1",
            function=technical.close_above_ma60,
            output_type="bool",
            description="Close is above MA60.",
        ),
        PrimitiveDefinition(
            primitive_id="moving_average.ma20_above_ma60",
            version="candidate_v1",
            function=technical.ma20_above_ma60,
            output_type="bool",
            description="MA20 is above MA60.",
        ),
        PrimitiveDefinition(
            primitive_id="moving_average.ma60_above_ma120",
            version="candidate_v1",
            function=technical.ma60_above_ma120,
            output_type="bool",
            description="MA60 is above MA120.",
        ),
        PrimitiveDefinition(
            primitive_id="trend.ma20_rising_20d",
            version="candidate_v1",
            function=technical.ma20_rising_20d,
            output_type="bool",
            description="MA20 slope is positive over the recent window.",
        ),
        PrimitiveDefinition(
            primitive_id="volume_liquidity.volume_ratio_5d_20d_high",
            version="v1",
            function=technical.volume_ratio_5d_20d_high,
            output_type="bool",
            description="Recent 5-day average volume is at least 1.2 times the 20-day average.",
        ),
        PrimitiveDefinition(
            primitive_id="volatility.volatility_60d_low",
            version="v1",
            function=technical.volatility_60d_low,
            output_type="bool",
            description="60-day realized volatility is below the candidate threshold.",
        ),
        PrimitiveDefinition(
            primitive_id="risk.max_drawdown_60d_controlled",
            version="candidate_v1",
            function=technical.max_drawdown_60d_controlled,
            output_type="bool",
            description="60-day max drawdown is controlled.",
        ),
        PrimitiveDefinition(
            primitive_id="risk.max_drawdown_120d_controlled",
            version="candidate_v1",
            function=technical.max_drawdown_120d_controlled,
            output_type="bool",
            description="120-day max drawdown is controlled.",
        ),
        PrimitiveDefinition(
            primitive_id="level_breakout.close_new_high_60d",
            version="v1",
            function=technical.close_new_high_60d,
            output_type="bool",
            description="Close reaches a 60-day high.",
        ),
        PrimitiveDefinition(
            primitive_id="structure.ma_5_10_20_converged",
            version="v1",
            function=technical.ma_5_10_20_converged,
            output_type="bool",
            description="MA5/MA10/MA20 are tightly converged.",
        ),
        PrimitiveDefinition(
            primitive_id="level_breakout.close_near_high_60d",
            version="candidate_v1",
            function=technical.close_near_high_60d,
            output_type="bool",
            description="Close is near the 60-day high but not a confirmed new high.",
        ),
        PrimitiveDefinition(
            primitive_id="risk.ma20_deviation_not_extreme",
            version="candidate_v1",
            function=technical.ma20_deviation_not_extreme,
            output_type="bool",
            description="Close is not overextended versus MA20.",
        ),
        PrimitiveDefinition(
            primitive_id="risk.ma30_deviation_not_extreme",
            version="candidate_v1",
            function=technical.ma30_deviation_not_extreme,
            output_type="bool",
            description="Close is not overextended versus MA30.",
        ),
        PrimitiveDefinition(
            primitive_id="moving_average.ma30_hold_ratio_90d_sustained",
            version="candidate_v1",
            function=technical.ma30_hold_ratio_90d_sustained,
            output_type="bool",
            description="90-day close-above-MA30 ratio is sustained.",
        ),
        PrimitiveDefinition(
            primitive_id="liquidity.avg_amount_20d_ge_2e",
            version="candidate_v1",
            function=technical.avg_amount_20d_ge_2e,
            output_type="bool",
            description="20-day average amount is at least 200 million yuan.",
        ),
        PrimitiveDefinition(
            primitive_id="liquidity.total_mv_ge_100e",
            version="candidate_v1",
            function=technical.total_mv_ge_100e,
            output_type="bool",
            description="Total market value is at least 10 billion yuan.",
        ),
        PrimitiveDefinition(
            primitive_id="risk.turnover_rate_20d_controlled",
            version="candidate_v1",
            function=technical.turnover_rate_20d_controlled,
            output_type="bool",
            description="Latest 20 days have no extreme turnover-rate spike.",
        ),
        PrimitiveDefinition(
            primitive_id="context.industry_or_concept_strength_hit",
            version="candidate_v1",
            function=technical.industry_or_concept_strength_hit,
            output_type="bool",
            description="Stock belongs to a strong industry or strong concept.",
        ),
        PrimitiveDefinition(
            primitive_id="candlestick.red_k_ratio_20d_healthy",
            version="candidate_v1",
            function=technical.red_k_ratio_20d_healthy,
            output_type="bool",
            description="20-day red K ratio is healthy enough for steady trend setups.",
        ),
        PrimitiveDefinition(
            primitive_id="candlestick.long_shadow_ratio_20d_controlled",
            version="candidate_v1",
            function=technical.long_shadow_ratio_20d_controlled,
            output_type="bool",
            description="20-day shadow noise is controlled.",
        ),
        PrimitiveDefinition(
            primitive_id="risk.daily_trend_quality_pass",
            version="candidate_v1",
            function=technical.daily_trend_quality_pass,
            output_type="bool",
            description="Composite daily trend quality filters pass.",
        ),
        PrimitiveDefinition(
            primitive_id="weekly_context.close_above_weekly_ma20",
            version="candidate_v1",
            function=technical.weekly_close_above_ma20,
            output_type="bool",
            description="As-of weekly close is above weekly MA20.",
        ),
        PrimitiveDefinition(
            primitive_id="weekly_context.weekly_ma10_above_ma20",
            version="candidate_v1",
            function=technical.weekly_ma10_above_ma20,
            output_type="bool",
            description="As-of weekly MA10 is above weekly MA20.",
        ),
        PrimitiveDefinition(
            primitive_id="weekly_context.weekly_ma20_rising_4w",
            version="candidate_v1",
            function=technical.weekly_ma20_rising_4w,
            output_type="bool",
            description="As-of weekly MA20 is rising over the recent 4-week window.",
        ),
        PrimitiveDefinition(
            primitive_id="weekly_context.weekly_drawdown_26w_controlled",
            version="candidate_v1",
            function=technical.weekly_drawdown_26w_controlled,
            output_type="bool",
            description="As-of weekly 26-week max drawdown is controlled.",
        ),
        PrimitiveDefinition(
            primitive_id="weekly_context.weekly_trend_context_pass",
            version="candidate_v1",
            function=technical.weekly_trend_context_pass,
            output_type="bool",
            description="Composite weekly trend context filters pass.",
        ),
    ):
        registry.register(primitive)
    return registry
