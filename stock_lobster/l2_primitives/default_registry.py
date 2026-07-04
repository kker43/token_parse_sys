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
            primitive_id="volume_liquidity.amount_ratio_20d_high",
            version="v1",
            function=technical.amount_ratio_20d_high,
            output_type="bool",
            description="Amount ratio versus 20-day average is high.",
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
    ):
        registry.register(primitive)
    return registry
