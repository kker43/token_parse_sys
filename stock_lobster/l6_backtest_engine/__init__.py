"""L6 Backtest Engine Layer."""

from stock_lobster.l6_backtest_engine.evidence import (
    BacktestGateReview,
    build_promotion_evidence_mapping,
    review_backtest_result,
)
from stock_lobster.l6_backtest_engine.candidate_pool_benchmark import (
    CandidatePoolBenchmarkResult,
    CandidatePoolSignalDateReturn,
    run_candidate_pool_equal_weight_benchmark,
)
from stock_lobster.l6_backtest_engine.event_backtest import (
    BacktestEvent,
    EventBacktestPolicy,
    EventBacktestReport,
    EventTradeResult,
    PriceBar,
    run_event_backtest,
)
from stock_lobster.l6_backtest_engine.profiles import (
    BacktestAcceptancePolicy,
    BenchmarkDefinition,
    EvaluationProfile,
    load_evaluation_profile,
)
from stock_lobster.l6_backtest_engine.result import BacktestResult

__all__ = [
    "BacktestAcceptancePolicy",
    "BacktestEvent",
    "BacktestGateReview",
    "BacktestResult",
    "BenchmarkDefinition",
    "CandidatePoolBenchmarkResult",
    "CandidatePoolSignalDateReturn",
    "EvaluationProfile",
    "EventBacktestPolicy",
    "EventBacktestReport",
    "EventTradeResult",
    "PriceBar",
    "build_promotion_evidence_mapping",
    "load_evaluation_profile",
    "review_backtest_result",
    "run_candidate_pool_equal_weight_benchmark",
    "run_event_backtest",
]
