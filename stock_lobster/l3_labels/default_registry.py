"""Default L3 label registry for early research workflows."""

from __future__ import annotations

from stock_lobster.l3_labels.registry import LabelDefinition, LabelRegistry


def build_default_label_registry() -> LabelRegistry:
    """Build the default in-memory L3 label registry."""

    registry = LabelRegistry()
    for label in (
        LabelDefinition(
            label_id="quality_gate.snapshot_consumable",
            version="v1",
            primitive_ids=("data_quality.basic_snapshot_ready",),
            description="The L1 snapshot can be consumed by research workflows.",
        ),
        LabelDefinition(
            label_id="technical_pattern.steady_uptrend_stock",
            version="candidate_v1",
            primitive_ids=(
                "moving_average.close_above_ma20",
                "moving_average.close_above_ma60",
                "moving_average.ma20_above_ma60",
                "moving_average.ma60_above_ma120",
                "trend.ma20_rising_20d",
                "risk.max_drawdown_60d_controlled",
            ),
            description="The stock is in a steady upward trend with controlled drawdown.",
        ),
        LabelDefinition(
            label_id="technical_pattern.uptrend_consolidation_breakout",
            version="candidate_v1",
            primitive_ids=(
                "moving_average.close_above_ma20",
                "moving_average.close_above_ma60",
                "moving_average.ma20_above_ma60",
                "moving_average.ma60_above_ma120",
                "trend.ma20_rising_20d",
                "risk.max_drawdown_60d_controlled",
                "structure.ma_5_10_20_converged",
                "level_breakout.close_new_high_60d",
            ),
            description="Steady uptrend followed by convergence and an upward breakout.",
        ),
        LabelDefinition(
            label_id="technical_pattern.steady_uptrend_new_high_breakout",
            version="candidate_v1",
            primitive_ids=(
                "moving_average.close_above_ma20",
                "moving_average.close_above_ma60",
                "moving_average.ma20_above_ma60",
                "moving_average.ma60_above_ma120",
                "trend.ma20_rising_20d",
                "risk.max_drawdown_60d_controlled",
                "level_breakout.close_new_high_60d",
            ),
            description="Steady uptrend stock reaches a new high breakout.",
        ),
        LabelDefinition(
            label_id="technical_pattern.volume_breakout",
            version="v1",
            primitive_ids=(
                "moving_average.close_above_ma20",
                "volume_liquidity.amount_ratio_20d_high",
                "level_breakout.close_new_high_60d",
            ),
            description="Price is above MA20 with volume expansion and a new high.",
        ),
        LabelDefinition(
            label_id="composite_setup.steady_uptrend_breakout_watch",
            version="candidate_v1",
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
            description="Composite watch setup for steady trend stocks breaking upward.",
        ),
    ):
        registry.register(label)
    return registry
