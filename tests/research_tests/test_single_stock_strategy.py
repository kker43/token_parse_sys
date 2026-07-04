"""Tests for single-stock research strategy sedimentation."""

from __future__ import annotations

import unittest

from stock_lobster.core.ids import RunId
from stock_lobster.l1_analysis_snapshot.schema import AnalysisSnapshot
from stock_lobster.l2_primitives import PrimitiveDefinition, PrimitiveRegistry
from stock_lobster.l3_labels import LabelDefinition, LabelRegistry
from stock_lobster.l6_backtest_engine.result import BacktestResult
from stock_lobster.research import (
    BacktestAcceptancePolicy,
    IndividualStockStrategyResearchRequest,
    IndividualStockStrategyResearchWorkflow,
    LabelHypothesis,
    PrimitiveHypothesis,
)


def sample_snapshot() -> AnalysisSnapshot:
    return AnalysisSnapshot(
        stock_code="000001.SZ",
        snapshot_date="20260703",
        analysis_version="analysis_v1",
        run_id=RunId("run_fixture"),
        features={
            "pub_stock_daily_kline.close": 12.5,
            "pub_stock_daily_indicator.ma20": 11.8,
            "pub_stock_daily_indicator.amount_ratio_20d": 1.8,
        },
    )


def close_above_ma20(snapshot: AnalysisSnapshot) -> bool:
    return (
        snapshot.features["pub_stock_daily_kline.close"]
        > snapshot.features["pub_stock_daily_indicator.ma20"]
    )


class IndividualStockStrategyResearchWorkflowTest(unittest.TestCase):
    def test_identifies_missing_l2_l3_and_keeps_strategy_draft(self) -> None:
        primitive_registry = PrimitiveRegistry()
        primitive_registry.register(
            PrimitiveDefinition(
                primitive_id="moving_average.close_above_ma20",
                version="v1",
                function=close_above_ma20,
                output_type="bool",
                description="Close is above ma20.",
            )
        )
        label_registry = LabelRegistry()

        result = IndividualStockStrategyResearchWorkflow(
            primitive_registry=primitive_registry,
            label_registry=label_registry,
        ).run(
            IndividualStockStrategyResearchRequest(
                case_id="case_001",
                title="低波收敛后放量观察",
                thesis="样本呈现均线上方放量，但需要补充量能阈值和 L3 标签。",
                snapshot=sample_snapshot(),
                primitive_hypotheses=(
                    PrimitiveHypothesis(
                        primitive_id="moving_average.close_above_ma20",
                        category="moving_average",
                        proposed_logic="close > ma20",
                        reason="确认价格处于中期均线上方。",
                        required_features=(
                            "pub_stock_daily_kline.close",
                            "pub_stock_daily_indicator.ma20",
                        ),
                    ),
                    PrimitiveHypothesis(
                        primitive_id="volume_liquidity.amount_ratio_20d_high",
                        category="volume_liquidity",
                        proposed_logic="amount_ratio_20d >= calibrated_high_threshold",
                        reason="确认突破或修复时存在量能配合。",
                        required_features=("pub_stock_daily_indicator.amount_ratio_20d",),
                        threshold_refs=("amount_ratio_20d_high",),
                    ),
                ),
                label_hypotheses=(
                    LabelHypothesis(
                        label_id="technical_pattern.volume_breakout",
                        category="technical_pattern",
                        primitive_ids=(
                            "moving_average.close_above_ma20",
                            "volume_liquidity.amount_ratio_20d_high",
                        ),
                        proposed_logic="close_above_ma20 AND amount_ratio_20d_high",
                        reason="均线上方放量可能形成突破标签。",
                    ),
                ),
                strategy_id="strategy.volume_breakout_research",
                strategy_name="放量突破研究策略",
            )
        )

        self.assertEqual("draft", result.strategy.status)
        self.assertEqual(True, result.primitive_assessments[0].value)
        self.assertEqual(1, len(result.experience_build_plan.primitive_requirements))
        self.assertEqual(1, len(result.experience_build_plan.label_requirements))
        self.assertEqual(
            ("amount_ratio_20d_high",),
            result.experience_build_plan.primitive_requirements[0].threshold_refs,
        )
        self.assertIn("missing_backtest_result", result.backtest_decision.failed_conditions)

    def test_promotes_strategy_to_test_tracking_when_assets_and_backtest_pass(self) -> None:
        primitive_registry = PrimitiveRegistry()
        primitive_registry.register(
            PrimitiveDefinition(
                primitive_id="moving_average.close_above_ma20",
                version="v1",
                function=close_above_ma20,
                output_type="bool",
                description="Close is above ma20.",
            )
        )
        label_registry = LabelRegistry()
        label_registry.register(
            LabelDefinition(
                label_id="technical_pattern.uptrend_support",
                version="v1",
                primitive_ids=("moving_average.close_above_ma20",),
                description="Price is supported by the medium moving average.",
            )
        )

        result = IndividualStockStrategyResearchWorkflow(
            primitive_registry=primitive_registry,
            label_registry=label_registry,
        ).run(
            IndividualStockStrategyResearchRequest(
                case_id="case_002",
                title="均线上方支撑",
                thesis="样本处于中期均线上方，可复用已有支撑标签。",
                snapshot=sample_snapshot(),
                primitive_hypotheses=(
                    PrimitiveHypothesis(
                        primitive_id="moving_average.close_above_ma20",
                        category="moving_average",
                        proposed_logic="close > ma20",
                        reason="确认价格处于中期均线上方。",
                        required_features=(
                            "pub_stock_daily_kline.close",
                            "pub_stock_daily_indicator.ma20",
                        ),
                    ),
                ),
                label_hypotheses=(
                    LabelHypothesis(
                        label_id="technical_pattern.uptrend_support",
                        category="technical_pattern",
                        primitive_ids=("moving_average.close_above_ma20",),
                        proposed_logic="close_above_ma20",
                        reason="复用已有均线上方支撑标签。",
                    ),
                ),
                strategy_id="strategy.uptrend_support_research",
                strategy_name="均线上方支撑研究策略",
                acceptance_policy=BacktestAcceptancePolicy(min_sample_size=10),
                backtest_result=BacktestResult(
                    strategy_id="strategy.uptrend_support_research",
                    strategy_version="candidate_v1",
                    backtest_period=("20250101", "20260703"),
                    benchmark="000300.SH",
                    holding_horizon=20,
                    return_metrics={"annual_return": 0.12},
                    drawdown_metrics={"max_drawdown": -0.18},
                    win_rate=0.6,
                    sample_size=30,
                ),
            )
        )

        self.assertEqual("test_tracking", result.strategy.status)
        self.assertEqual(("technical_pattern.uptrend_support",), result.strategy.label_fields)
        self.assertTrue(result.backtest_decision.passed)
        self.assertFalse(result.experience_build_plan.has_gaps)


if __name__ == "__main__":
    unittest.main()
