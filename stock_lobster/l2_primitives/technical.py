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


def close_new_high_60d(snapshot: AnalysisSnapshot) -> bool:
    """Return whether close reaches a 60-day high."""

    return get_indicator_value(snapshot, "close_new_high_60d_flag") >= 1.0


def ma_5_10_20_converged(snapshot: AnalysisSnapshot) -> bool:
    """Return whether short moving averages are tightly converged."""

    return get_indicator_value(snapshot, "convergence_5_10_20_pct") <= 0.03


def _indicator_exists(snapshot: AnalysisSnapshot, indicator_name: str) -> bool:
    try:
        get_indicator_value(snapshot, indicator_name)
    except KeyError:
        return False
    return True
