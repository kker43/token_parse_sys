"""Single-stock research workflow for L2/L3/L4 strategy sedimentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from stock_lobster.l1_analysis_snapshot.schema import AnalysisSnapshot
from stock_lobster.l1_analysis_snapshot.feature_access import (
    FeatureNotFoundError,
    has_requirement,
)
from stock_lobster.l2_primitives.registry import PrimitiveRegistry
from stock_lobster.l3_labels.registry import LabelRegistry
from stock_lobster.l4_strategy_dsl.candidate_pool import CandidatePoolPolicy
from stock_lobster.l4_strategy_dsl.schema import StrategyDSL
from stock_lobster.l4_strategy_dsl.stage_pipeline import StageDefinition, StagePipeline
from stock_lobster.l4_strategy_dsl.validator import validate_no_raw_data_references
from stock_lobster.l6_backtest_engine.result import BacktestResult


@dataclass(frozen=True, slots=True)
class PrimitiveHypothesis:
    """A proposed or required L2 primitive for one research case."""

    primitive_id: str
    category: str
    proposed_logic: str
    reason: str
    required_features: tuple[str, ...] = field(default_factory=tuple)
    threshold_refs: tuple[str, ...] = field(default_factory=tuple)
    version: str = "candidate_v1"
    output_type: str = "bool"


@dataclass(frozen=True, slots=True)
class LabelHypothesis:
    """A proposed or required L3 label for one research case."""

    label_id: str
    category: str
    primitive_ids: tuple[str, ...]
    proposed_logic: str
    reason: str
    version: str = "candidate_v1"


@dataclass(frozen=True, slots=True)
class BacktestAcceptancePolicy:
    """Minimum gate for promoting a draft L4 strategy to test tracking."""

    min_sample_size: int = 30
    min_win_rate: float = 0.55
    return_metric_name: str = "annual_return"
    min_return_metric: float = 0.0
    drawdown_metric_name: str = "max_drawdown"
    max_abs_drawdown: float = 0.25


@dataclass(frozen=True, slots=True)
class PatternCase:
    """Research evidence for why one stock/date is being studied."""

    case_id: str
    stock_code: str
    case_date: str
    title: str
    thesis: str
    evidence_features: Mapping[str, object]
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class FactorObservation:
    """A deterministic observation over one L1 feature."""

    feature_name: str
    value: object
    interpretation: str
    source_layer: str = "L1"


@dataclass(frozen=True, slots=True)
class PrimitiveAssessment:
    """Computed output from an existing L2 primitive."""

    primitive_id: str
    version: str
    value: bool | float
    source: str = "existing_registry"


@dataclass(frozen=True, slots=True)
class PrimitiveBuildRequirement:
    """Missing L2 primitive that should be implemented or approved."""

    primitive_id: str
    category: str
    proposed_logic: str
    reason: str
    required_features: tuple[str, ...]
    missing_features: tuple[str, ...]
    threshold_refs: tuple[str, ...]
    data_status: str
    version: str
    output_type: str


@dataclass(frozen=True, slots=True)
class LabelAssessment:
    """Existing L3 label that can be evaluated from L2 outputs."""

    label_id: str
    version: str
    primitive_ids: tuple[str, ...]
    primitive_values: Mapping[str, bool | float]
    matched: bool
    source: str = "existing_registry"


@dataclass(frozen=True, slots=True)
class LabelBuildRequirement:
    """Missing L3 label that should be implemented or approved."""

    label_id: str
    category: str
    primitive_ids: tuple[str, ...]
    proposed_logic: str
    reason: str
    missing_primitives: tuple[str, ...]
    data_status: str
    version: str


@dataclass(frozen=True, slots=True)
class ExperienceBuildPlan:
    """L2/L3 construction gaps discovered by the workflow."""

    primitive_requirements: tuple[PrimitiveBuildRequirement, ...]
    label_requirements: tuple[LabelBuildRequirement, ...]
    threshold_questions: tuple[str, ...]

    @property
    def has_gaps(self) -> bool:
        """Return whether this research case needs new experience assets."""

        return bool(self.primitive_requirements or self.label_requirements)


@dataclass(frozen=True, slots=True)
class BacktestGateDecision:
    """Decision for strategy test-tracking promotion."""

    passed: bool
    status: str
    reasons: tuple[str, ...]
    failed_conditions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class IndividualStockStrategyResearchRequest:
    """Input for one single-stock research-to-strategy workflow run."""

    case_id: str
    title: str
    thesis: str
    snapshot: AnalysisSnapshot
    primitive_hypotheses: tuple[PrimitiveHypothesis, ...]
    label_hypotheses: tuple[LabelHypothesis, ...]
    strategy_id: str
    strategy_name: str
    benchmark: str = "000300.SH"
    holding_horizon: int = 20
    acceptance_policy: BacktestAcceptancePolicy = field(
        default_factory=BacktestAcceptancePolicy
    )
    backtest_result: BacktestResult | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class IndividualStockStrategyResearchResult:
    """Output of the single-stock research workflow."""

    pattern_case: PatternCase
    factor_observations: tuple[FactorObservation, ...]
    primitive_assessments: tuple[PrimitiveAssessment, ...]
    label_assessments: tuple[LabelAssessment, ...]
    experience_build_plan: ExperienceBuildPlan
    strategy: StrategyDSL
    backtest_decision: BacktestGateDecision
    next_actions: tuple[str, ...]


class IndividualStockStrategyResearchWorkflow:
    """Coordinate L2 primitive, L3 label, L4 strategy, and L6 evidence checks."""

    def __init__(
        self,
        primitive_registry: PrimitiveRegistry,
        label_registry: LabelRegistry,
    ) -> None:
        self.primitive_registry = primitive_registry
        self.label_registry = label_registry

    def run(
        self,
        request: IndividualStockStrategyResearchRequest,
    ) -> IndividualStockStrategyResearchResult:
        """Run a deterministic single-stock research workflow."""

        pattern_case = _build_pattern_case(request)
        observations = _build_factor_observations(
            request.snapshot,
            request.primitive_hypotheses,
        )

        primitive_assessments: list[PrimitiveAssessment] = []
        primitive_requirements: list[PrimitiveBuildRequirement] = []
        primitive_values: dict[str, bool | float] = {}
        threshold_questions: list[str] = []

        for hypothesis in request.primitive_hypotheses:
            missing_features = _missing_features(
                request.snapshot,
                hypothesis.required_features,
            )
            if missing_features:
                primitive_requirements.append(
                    PrimitiveBuildRequirement(
                        primitive_id=hypothesis.primitive_id,
                        category=hypothesis.category,
                        proposed_logic=hypothesis.proposed_logic,
                        reason=hypothesis.reason,
                        required_features=hypothesis.required_features,
                        missing_features=missing_features,
                        threshold_refs=hypothesis.threshold_refs,
                        data_status="need_l1_features",
                        version=hypothesis.version,
                        output_type=hypothesis.output_type,
                    )
                )
                threshold_questions.extend(
                    _threshold_questions(hypothesis.primitive_id, hypothesis.threshold_refs)
                )
                continue

            if hypothesis.primitive_id in self.primitive_registry.primitives:
                definition = self.primitive_registry.get(hypothesis.primitive_id)
                try:
                    value = definition.function(request.snapshot)
                except FeatureNotFoundError:
                    primitive_requirements.append(
                        PrimitiveBuildRequirement(
                            primitive_id=hypothesis.primitive_id,
                            category=hypothesis.category,
                            proposed_logic=hypothesis.proposed_logic,
                            reason=hypothesis.reason,
                            required_features=hypothesis.required_features,
                            missing_features=hypothesis.required_features,
                            threshold_refs=hypothesis.threshold_refs,
                            data_status="need_l1_features",
                            version=hypothesis.version,
                            output_type=hypothesis.output_type,
                        )
                    )
                    continue
                primitive_values[hypothesis.primitive_id] = value
                primitive_assessments.append(
                    PrimitiveAssessment(
                        primitive_id=definition.primitive_id,
                        version=definition.version,
                        value=value,
                    )
                )
                continue

            primitive_requirements.append(
                PrimitiveBuildRequirement(
                    primitive_id=hypothesis.primitive_id,
                    category=hypothesis.category,
                    proposed_logic=hypothesis.proposed_logic,
                    reason=hypothesis.reason,
                    required_features=hypothesis.required_features,
                    missing_features=(),
                    threshold_refs=hypothesis.threshold_refs,
                    data_status="data_ready",
                    version=hypothesis.version,
                    output_type=hypothesis.output_type,
                )
            )
            threshold_questions.extend(
                _threshold_questions(hypothesis.primitive_id, hypothesis.threshold_refs)
            )

        label_assessments: list[LabelAssessment] = []
        label_requirements: list[LabelBuildRequirement] = []
        strategy_label_fields: list[str] = []

        for hypothesis in request.label_hypotheses:
            definition = self.label_registry.labels.get(hypothesis.label_id)
            required_primitive_ids = (
                definition.primitive_ids if definition is not None else hypothesis.primitive_ids
            )
            missing_primitives = tuple(
                primitive_id
                for primitive_id in required_primitive_ids
                if primitive_id not in primitive_values
            )
            if definition is not None and not missing_primitives:
                values = {
                    primitive_id: primitive_values[primitive_id]
                    for primitive_id in definition.primitive_ids
                }
                matched = _label_matched(values)
                label_assessments.append(
                    LabelAssessment(
                        label_id=definition.label_id,
                        version=definition.version,
                        primitive_ids=definition.primitive_ids,
                        primitive_values=values,
                        matched=matched,
                    )
                )
                if matched:
                    strategy_label_fields.append(definition.label_id)
                continue

            label_requirements.append(
                LabelBuildRequirement(
                    label_id=hypothesis.label_id,
                    category=hypothesis.category,
                    primitive_ids=hypothesis.primitive_ids,
                    proposed_logic=hypothesis.proposed_logic,
                    reason=hypothesis.reason,
                    missing_primitives=missing_primitives,
                    data_status="data_ready" if not missing_primitives else "need_l2_primitives",
                    version=hypothesis.version,
                )
            )
            if not missing_primitives:
                strategy_label_fields.append(hypothesis.label_id)

        build_plan = ExperienceBuildPlan(
            primitive_requirements=tuple(primitive_requirements),
            label_requirements=tuple(label_requirements),
            threshold_questions=tuple(dict.fromkeys(threshold_questions)),
        )
        backtest_decision = _decide_backtest_gate(
            request.backtest_result,
            request.acceptance_policy,
        )
        strategy_status = _strategy_status(build_plan, backtest_decision)
        strategy = _build_strategy(request, tuple(strategy_label_fields), strategy_status)
        validate_no_raw_data_references(strategy)

        return IndividualStockStrategyResearchResult(
            pattern_case=pattern_case,
            factor_observations=tuple(observations),
            primitive_assessments=tuple(primitive_assessments),
            label_assessments=tuple(label_assessments),
            experience_build_plan=build_plan,
            strategy=strategy,
            backtest_decision=backtest_decision,
            next_actions=_next_actions(build_plan, backtest_decision),
        )


def _build_pattern_case(request: IndividualStockStrategyResearchRequest) -> PatternCase:
    evidence_features = {
        feature_name: request.snapshot.features[feature_name]
        for hypothesis in request.primitive_hypotheses
        for feature_name in hypothesis.required_features
        if feature_name in request.snapshot.features
    }
    return PatternCase(
        case_id=request.case_id,
        stock_code=request.snapshot.stock_code,
        case_date=request.snapshot.snapshot_date,
        title=request.title,
        thesis=request.thesis,
        evidence_features=evidence_features,
        notes=request.notes,
    )


def _build_factor_observations(
    snapshot: AnalysisSnapshot,
    primitive_hypotheses: tuple[PrimitiveHypothesis, ...],
) -> list[FactorObservation]:
    observations: list[FactorObservation] = []
    seen: set[str] = set()
    for hypothesis in primitive_hypotheses:
        for feature_name in hypothesis.required_features:
            if feature_name in seen:
                continue
            seen.add(feature_name)
            if feature_name in snapshot.features:
                observations.append(
                    FactorObservation(
                        feature_name=feature_name,
                        value=snapshot.features[feature_name],
                        interpretation=f"Used by {hypothesis.primitive_id}",
                    )
                )
            else:
                observations.append(
                    FactorObservation(
                        feature_name=feature_name,
                        value=None,
                        interpretation=f"Missing for {hypothesis.primitive_id}",
                    )
                )
    return observations


def _missing_features(
    snapshot: AnalysisSnapshot,
    required_features: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        feature_name
        for feature_name in required_features
        if not has_requirement(snapshot, feature_name)
    )


def _label_matched(values: Mapping[str, bool | float]) -> bool:
    return all(bool(value) for value in values.values())


def _threshold_questions(
    primitive_id: str,
    threshold_refs: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        f"{primitive_id} needs threshold calibration for {threshold_ref}"
        for threshold_ref in threshold_refs
    )


def _build_strategy(
    request: IndividualStockStrategyResearchRequest,
    label_fields: tuple[str, ...],
    status: str,
) -> StrategyDSL:
    recall_conditions = label_fields or tuple(
        hypothesis.label_id for hypothesis in request.label_hypotheses
    )
    return StrategyDSL(
        strategy_id=request.strategy_id,
        version="candidate_v1",
        name=request.strategy_name,
        candidate_pool=CandidatePoolPolicy(
            policy_id=f"{request.strategy_id}.candidate_pool",
            version="candidate_v1",
            source_type="research_label_recall",
            parameters={
                "case_id": request.case_id,
                "seed_stock_code": request.snapshot.stock_code,
                "seed_date": request.snapshot.snapshot_date,
                "labels": list(recall_conditions),
            },
        ),
        pipeline=StagePipeline(
            stages=(
                StageDefinition(
                    stage_id="recall_by_l3_labels",
                    stage_name="Recall by L3 labels",
                    stage_type="recall",
                    pass_conditions=recall_conditions,
                ),
                StageDefinition(
                    stage_id="rank_by_research_confidence",
                    stage_name="Rank by research confidence",
                    stage_type="rank",
                    score_fields=label_fields,
                ),
            )
        ),
        label_fields=label_fields,
        status=status,
    )


def _decide_backtest_gate(
    backtest_result: BacktestResult | None,
    policy: BacktestAcceptancePolicy,
) -> BacktestGateDecision:
    if backtest_result is None:
        return BacktestGateDecision(
            passed=False,
            status="draft",
            reasons=("Backtest result is required before test tracking.",),
            failed_conditions=("missing_backtest_result",),
        )

    failed_conditions: list[str] = []
    reasons: list[str] = []

    if backtest_result.sample_size < policy.min_sample_size:
        failed_conditions.append("sample_size")
        reasons.append(
            f"sample_size {backtest_result.sample_size} < {policy.min_sample_size}"
        )

    if backtest_result.win_rate < policy.min_win_rate:
        failed_conditions.append("win_rate")
        reasons.append(f"win_rate {backtest_result.win_rate:.4f} < {policy.min_win_rate:.4f}")

    return_metric = backtest_result.return_metrics.get(policy.return_metric_name)
    if return_metric is None:
        failed_conditions.append(policy.return_metric_name)
        reasons.append(f"missing return metric {policy.return_metric_name}")
    elif return_metric < policy.min_return_metric:
        failed_conditions.append(policy.return_metric_name)
        reasons.append(
            f"{policy.return_metric_name} {return_metric:.4f} < {policy.min_return_metric:.4f}"
        )

    drawdown_metric = backtest_result.drawdown_metrics.get(policy.drawdown_metric_name)
    if drawdown_metric is None:
        failed_conditions.append(policy.drawdown_metric_name)
        reasons.append(f"missing drawdown metric {policy.drawdown_metric_name}")
    elif abs(drawdown_metric) > policy.max_abs_drawdown:
        failed_conditions.append(policy.drawdown_metric_name)
        reasons.append(
            f"abs({policy.drawdown_metric_name}) {abs(drawdown_metric):.4f} > "
            f"{policy.max_abs_drawdown:.4f}"
        )

    if failed_conditions:
        return BacktestGateDecision(
            passed=False,
            status="draft",
            reasons=tuple(reasons),
            failed_conditions=tuple(failed_conditions),
        )

    return BacktestGateDecision(
        passed=True,
        status="test_tracking",
        reasons=("Backtest result satisfies the acceptance policy.",),
    )


def _strategy_status(
    build_plan: ExperienceBuildPlan,
    backtest_decision: BacktestGateDecision,
) -> str:
    if build_plan.has_gaps:
        return "draft"
    if backtest_decision.passed:
        return "test_tracking"
    return "draft"


def _next_actions(
    build_plan: ExperienceBuildPlan,
    backtest_decision: BacktestGateDecision,
) -> tuple[str, ...]:
    actions: list[str] = []
    if build_plan.primitive_requirements:
        actions.append("Implement or approve missing L2 primitive definitions.")
    if build_plan.label_requirements:
        actions.append("Implement or approve missing L3 label definitions.")
    if build_plan.threshold_questions:
        actions.append("Calibrate thresholds with sample groups before approval.")
    if not backtest_decision.passed:
        actions.append("Run or improve L6 backtest evidence before test tracking.")
    if not actions:
        actions.append("Register the L4 strategy as test_tracking and schedule observation.")
    return tuple(actions)
