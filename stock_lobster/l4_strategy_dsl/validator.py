"""Validation helpers for strategy DSL definitions."""

from __future__ import annotations

from stock_lobster.core.errors import StockLobsterError
from stock_lobster.l4_strategy_dsl.schema import StrategyDSL

RAW_DATA_TOKENS = ("open", "high", "low", "close", "volume", "amount")


class StrategyDSLValidationError(StockLobsterError):
    """Raised when a strategy DSL violates layer rules."""


def validate_no_raw_data_references(strategy: StrategyDSL) -> None:
    """Reject label field names that look like raw factual data references."""

    for field_name in strategy.label_fields:
        if field_name.lower() in RAW_DATA_TOKENS:
            raise StrategyDSLValidationError(
                f"StrategyDSL cannot reference raw data field: {field_name}"
            )
