"""Reusable L2 technical primitive functions."""

from __future__ import annotations

from stock_lobster.l1_analysis_snapshot.feature_access import (
    get_float_feature,
    get_indicator_value,
)
from stock_lobster.l1_analysis_snapshot.schema import AnalysisSnapshot


def basic_snapshot_ready(snapshot: AnalysisSnapshot) -> bool:
    """Return whether the core daily kline fields are present."""

    try:
        get_float_feature(snapshot, "pub_stock_daily_kline.close")
        get_float_feature(snapshot, "pub_stock_daily_kline.amount")
    except KeyError:
        return False
    return True


def close_above_ma20(snapshot: AnalysisSnapshot) -> bool:
    """Return whether close is above MA20."""

    if _indicator_exists(snapshot, "close_above_ma20_flag"):
        return get_indicator_value(snapshot, "close_above_ma20_flag") >= 1.0
    return get_float_feature(snapshot, "pub_stock_daily_kline.close") > get_indicator_value(snapshot, "ma20")


def close_above_ma30(snapshot: AnalysisSnapshot) -> bool:
    """Return whether close is above MA30."""

    return get_float_feature(snapshot, "pub_stock_daily_kline.close") > get_indicator_value(snapshot, "ma30")


def close_above_ma60(snapshot: AnalysisSnapshot) -> bool:
    """Return whether close is above MA60."""

    return get_float_feature(snapshot, "pub_stock_daily_kline.close") > get_indicator_value(snapshot, "ma60")


def ma20_above_ma60(snapshot: AnalysisSnapshot) -> bool:
    """Return whether MA20 is above MA60."""

    return get_indicator_value(snapshot, "ma20") > get_indicator_value(snapshot, "ma60")


def ma60_above_ma120(snapshot: AnalysisSnapshot) -> bool:
    """Return whether MA60 is above MA120."""

    return get_indicator_value(snapshot, "ma60") > get_indicator_value(snapshot, "ma120")


def ma20_rising_20d(snapshot: AnalysisSnapshot) -> bool:
    """Return whether the 20-day MA slope is positive."""

    return get_indicator_value(snapshot, "ma20_slope_20d") > 0


def amount_ratio_20d_high(snapshot: AnalysisSnapshot) -> bool:
    """Return whether amount is meaningfully above the 20-day average."""

    return get_indicator_value(snapshot, "amount_ratio_20d") >= 1.5


def volatility_60d_low(snapshot: AnalysisSnapshot) -> bool:
    """Return whether 60-day realized volatility is below the candidate threshold."""

    return get_indicator_value(snapshot, "volatility_60d") <= 0.35


def max_drawdown_60d_controlled(snapshot: AnalysisSnapshot) -> bool:
    """Return whether 60-day max drawdown stays within the candidate threshold."""

    return abs(get_indicator_value(snapshot, "max_drawdown_60d")) <= 0.40


def max_drawdown_120d_controlled(snapshot: AnalysisSnapshot) -> bool:
    """Return whether 120-day max drawdown stays within the candidate threshold."""

    return abs(get_indicator_value(snapshot, "max_drawdown_120d")) <= 0.55


def close_new_high_60d(snapshot: AnalysisSnapshot) -> bool:
    """Return whether close reaches a 60-day high."""

    return get_indicator_value(snapshot, "close_new_high_60d_flag") >= 1.0


def ma_5_10_20_converged(snapshot: AnalysisSnapshot) -> bool:
    """Return whether short moving averages are tightly converged."""

    return get_indicator_value(snapshot, "convergence_5_10_20_pct") <= 0.03


def close_near_high_60d(snapshot: AnalysisSnapshot) -> bool:
    """Return whether close is near the 60-day high but not a confirmed new high."""

    close_to_high = get_indicator_value(snapshot, "close_to_high_60d_pct")
    return -0.08 <= close_to_high <= -0.002


def ma20_deviation_not_extreme(snapshot: AnalysisSnapshot) -> bool:
    """Return whether close is not overextended versus MA20."""

    return get_indicator_value(snapshot, "ma20_deviation_pct") <= 0.35


def ma30_deviation_not_extreme(snapshot: AnalysisSnapshot) -> bool:
    """Return whether close is not overextended versus MA30."""

    return get_indicator_value(snapshot, "ma30_deviation_pct") <= 0.35


def ma30_hold_ratio_90d_sustained(snapshot: AnalysisSnapshot) -> bool:
    """Return whether close stayed above MA30 often enough over 90 days."""

    return get_indicator_value(snapshot, "ma30_hold_ratio_90d") >= 0.75


def avg_amount_20d_ge_2e(snapshot: AnalysisSnapshot) -> bool:
    """Return whether 20-day average amount is at least 200 million yuan."""

    return get_indicator_value(snapshot, "avg_amount_20d") >= 200_000


def total_mv_ge_100e(snapshot: AnalysisSnapshot) -> bool:
    """Return whether total market value is at least 100e CNY."""

    return get_float_feature(snapshot, "pub_stock_daily_basic.total_mv") >= 1_000_000


def turnover_rate_20d_controlled(snapshot: AnalysisSnapshot) -> bool:
    """Return whether the latest 20 days avoid extreme turnover."""

    return get_indicator_value(snapshot, "max_turnover_rate_20d") <= 20


def industry_or_concept_strength_hit(snapshot: AnalysisSnapshot) -> bool:
    """Return whether industry or concept context is strong."""

    return get_indicator_value(snapshot, "context_strength_pass") >= 1.0


def red_k_ratio_20d_healthy(snapshot: AnalysisSnapshot) -> bool:
    """Return whether recent red K ratio is healthy enough for steady trend setups."""

    return get_indicator_value(snapshot, "red_k_ratio_20d") >= 0.45


def long_shadow_ratio_20d_controlled(snapshot: AnalysisSnapshot) -> bool:
    """Return whether recent shadow noise is controlled."""

    return get_indicator_value(snapshot, "long_shadow_ratio_20d") <= 0.65


def daily_trend_quality_pass(snapshot: AnalysisSnapshot) -> bool:
    """Return whether daily trend quality filters pass."""

    return get_indicator_value(snapshot, "daily_quality_pass") >= 1.0


def weekly_close_above_ma20(snapshot: AnalysisSnapshot) -> bool:
    """Return whether the as-of weekly close is above weekly MA20."""

    return get_float_feature(snapshot, "pub_stock_weekly_kline.close") > get_indicator_value(
        snapshot,
        "weekly_ma20",
    )


def weekly_ma10_above_ma20(snapshot: AnalysisSnapshot) -> bool:
    """Return whether weekly MA10 is above weekly MA20."""

    return get_indicator_value(snapshot, "weekly_ma10") > get_indicator_value(snapshot, "weekly_ma20")


def weekly_ma20_rising_4w(snapshot: AnalysisSnapshot) -> bool:
    """Return whether weekly MA20 is rising over the recent 4-week window."""

    return get_indicator_value(snapshot, "weekly_ma20_slope_4w") > 0


def weekly_drawdown_26w_controlled(snapshot: AnalysisSnapshot) -> bool:
    """Return whether 26-week max drawdown stays within the context threshold."""

    return abs(get_indicator_value(snapshot, "weekly_max_drawdown_26w")) <= 0.55


def weekly_trend_context_pass(snapshot: AnalysisSnapshot) -> bool:
    """Return whether the high-timeframe weekly trend context passes."""

    return get_indicator_value(snapshot, "weekly_trend_pass") >= 1.0


def _indicator_exists(snapshot: AnalysisSnapshot, indicator_name: str) -> bool:
    try:
        get_indicator_value(snapshot, indicator_name)
    except KeyError:
        return False
    return True
