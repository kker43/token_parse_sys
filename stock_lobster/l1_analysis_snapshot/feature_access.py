"""Helpers for reading normalized feature values from an AnalysisSnapshot."""

from __future__ import annotations

from collections.abc import Mapping

from stock_lobster.l1_analysis_snapshot.schema import AnalysisSnapshot


class FeatureNotFoundError(KeyError):
    """Raised when a required snapshot feature cannot be resolved."""


def get_feature(snapshot: AnalysisSnapshot, feature_name: str) -> object:
    """Return one exact feature value from a snapshot."""

    if feature_name not in snapshot.features:
        raise FeatureNotFoundError(feature_name)
    return snapshot.features[feature_name]


def get_float_feature(snapshot: AnalysisSnapshot, feature_name: str) -> float:
    """Return one exact feature value as float."""

    return _to_float(get_feature(snapshot, feature_name), feature_name)


def get_indicator_value(snapshot: AnalysisSnapshot, indicator_name: str) -> float:
    """Return a daily indicator value from direct or row-expanded features."""

    direct_candidates = (
        f"pub_stock_daily_indicator.{indicator_name}",
        f"pub_stock_daily_indicator.{indicator_name}.indicator_value",
    )
    for feature_name in direct_candidates:
        if feature_name in snapshot.features:
            return _to_float(snapshot.features[feature_name], feature_name)

    indicator_rows = _indicator_rows(snapshot.features)
    for row in indicator_rows.values():
        if str(row.get("indicator_name")) == indicator_name:
            if "indicator_value" not in row:
                raise FeatureNotFoundError(f"indicator:{indicator_name}.indicator_value")
            return _to_float(row["indicator_value"], f"indicator:{indicator_name}")

    raise FeatureNotFoundError(f"indicator:{indicator_name}")


def has_requirement(snapshot: AnalysisSnapshot, requirement: str) -> bool:
    """Return whether a feature requirement can be resolved."""

    try:
        resolve_requirement(snapshot, requirement)
    except FeatureNotFoundError:
        return False
    return True


def resolve_requirement(snapshot: AnalysisSnapshot, requirement: str) -> object:
    """Resolve exact features and semantic indicator/kline requirements."""

    if requirement.startswith("indicator:"):
        return get_indicator_value(snapshot, requirement.removeprefix("indicator:"))
    if requirement.startswith("kline:"):
        return get_feature(snapshot, f"pub_stock_daily_kline.{requirement.removeprefix('kline:')}")
    return get_feature(snapshot, requirement)


def _indicator_rows(features: Mapping[str, object]) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    prefix = "pub_stock_daily_indicator"
    for feature_name, value in features.items():
        if not feature_name.startswith(prefix):
            continue
        parts = feature_name.split(".")
        if len(parts) == 2:
            row_key = ""
            field_name = parts[1]
        elif len(parts) == 3 and parts[1].isdigit():
            row_key = parts[1]
            field_name = parts[2]
        else:
            continue
        rows.setdefault(row_key, {})[field_name] = value
    return rows


def _to_float(value: object, feature_name: str) -> float:
    if value is None:
        raise FeatureNotFoundError(feature_name)
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise FeatureNotFoundError(feature_name) from exc
