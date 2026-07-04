"""Signal explanation helpers."""

from __future__ import annotations

from stock_lobster.l5_signal_engine.engine import StrategySignal


def explain_signal(signal: StrategySignal) -> dict[str, object]:
    """Return a simple structured explanation for a generated signal."""

    return {
        "stock_code": signal.stock_code,
        "triggered_labels": signal.triggered_labels,
        "recall_reasons": signal.recall_reasons,
        "passed_filters": signal.passed_filters,
        "ranking_score": signal.ranking_score,
        "rank": signal.rank,
    }
