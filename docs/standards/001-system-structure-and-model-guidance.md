# Standard 001: System Structure and Model Guidance

## Purpose

This standard defines the target project structure, workflow boundaries, tool
boundaries, and model-selection rules for Stock Lobster.

Future Codex or GPT sessions should read this document before implementing
features that touch project structure, workflows, research production, strategy
production, or recurring jobs.

## Core Thesis

Stock Lobster should be built as one large system with separate bounded
contexts:

```text
data_foundation
-> shared_contracts
-> stock_lobster
-> workflows
-> tools
-> skills
```

The system should not become one flat package where strategy code reads
collector internals. The larger project may contain the data foundation, but
Stock Lobster must consume factual data through contracts and registered
assets.

## Main Production Chain

The main chain is:

```text
Factual Data
-> DataAsset Contract
-> AnalysisSnapshot
-> Experience Data
-> Strategy Composition
-> Signal Generation
-> Backtest Analysis
-> Observation Tracking
-> Routine Optimization
```

Layer mapping:

| Chain step | Owner |
| --- | --- |
| factual data production | `data_foundation` |
| field schema and asset contract | `shared_contracts` and L0 |
| analysis snapshot | L1 |
| sample research and experience candidates | `stock_lobster.research` |
| approved primitives | L2 |
| approved labels and label snapshots | L3 |
| strategy composition | L4 |
| formal signals | L5 |
| formal backtests | L6 |
| observation and optimization | `observation` or `app` workflow area |

## Target Large Project Layout

If the repository evolves into a large project, use this shape:

```text
token_parse_sys/
  shared/
    contracts/
    schemas/
    calendar/

  data_foundation/
    sources/
    ingestion/
    normalization/
    indicators/
    quality/
    catalog_export/
    jobs/

  stock_lobster/
    core/
    l0_data_access/
    l1_analysis_snapshot/
    research/
    l2_primitives/
    l3_labels/
    l4_strategy_dsl/
    l5_signal_engine/
    l6_backtest_engine/
    observation/
    app/

  workflows/
    fact_data_production/
    snapshot_production/
    pattern_research/
    strategy_construction/
    backtest_evaluation/
    routine_optimization/

  tools/
    data_asset_tools/
    snapshot_tools/
    research_tools/
    strategy_tools/
    backtest_tools/
    approval_tools/
    observation_tools/

  configs/
    data_sources/
    data_assets/
    primitives/
    labels/
    strategies/
    evaluation_profiles/
    schedules/

  docs/
    decisions/
    standards/
    workflows/
    examples/
    data_contracts/
```

The current repository can evolve toward this structure gradually. Do not move
files just to match the target shape unless the next implementation step needs
that boundary.

## Bounded Context Rules

### `data_foundation`

Owns factual data production.

Allowed outputs:

- raw and normalized market data
- adjusted prices
- volume and amount facts
- moving averages
- volatility and ATR
- interval high/low statistics
- stock, industry, concept, and calendar metadata
- data quality status
- exported `DataAsset` catalog

Not allowed:

- strategy meanings
- buy/sell signals
- approved primitives
- approved labels
- production strategy decisions

### `shared/contracts`

Owns cross-context contracts.

Examples:

- field schema
- asset identifiers
- date and symbol conventions
- quality status vocabulary
- version and run id conventions

Contracts must be stable enough that Stock Lobster can reproduce historical
analysis when upstream production code changes.

### `stock_lobster`

Owns experience data, strategy semantics, signal generation, backtesting, and
observation.

Stock Lobster may create:

- `PatternCase`
- `FactorObservation`
- `PrimitiveCandidate`
- approved `PrimitiveDefinition`
- `LabelCandidate`
- approved `LabelDefinition`
- `LabelSnapshot`
- `StrategyCandidate`
- approved `StrategyDSL`
- `StrategySignal`
- `BacktestResult`
- `ApprovalDecision`
- `ObservationRecord`
- `ReviewFinding`

Stock Lobster must not create canonical factual data.

### `workflows`

Owns executable process composition.

Workflows call public APIs from bounded contexts. They must not hide business
logic that belongs in layer packages or registries.

### `tools`

Owns reusable callable capabilities.

Tools should be thin wrappers around stable application services. They should
not become the source of strategy truth.

### `skills`

Own agent playbooks.

Skills describe how a Codex/GPT session should perform a repeatable workflow.
They should not contain production business logic.

## Workflow Split

Use separate workflows. Do not compress everything into one giant workflow.

### W1 Factual Data Production

```text
Source
-> Ingestion
-> Normalization
-> Indicator Production
-> Quality Check
-> DataAsset Catalog Export
```

Output: factual data tables/files and `DataAsset` contracts.

### W2 Snapshot Production

```text
DataAsset
-> Query Contract
-> AnalysisSnapshot
-> Snapshot Dependency Record
```

Output: reproducible L1 snapshots.

### W3 Pattern Research to Experience Production

```text
PatternCase
-> FactorObservation
-> PrimitiveCandidate
-> LabelCandidate
-> StrategyCandidate
-> EvaluationProfile
-> BacktestEvidence
-> ApprovalDecision
-> RegisteredArtifact or ScheduledProduction
```

Output: approved or archived experience artifacts.

### W4 Strategy Construction

```text
Approved Label Fields
-> CandidatePoolPolicy
-> StagePipeline
-> StrategyCandidate
-> StrategyDSL
-> ApprovalDecision
```

Output: versioned L4 strategy definitions.

### W5 Backtest Evaluation

```text
StrategyDSL
-> EvaluationProfile
-> Historical Signal Replay
-> BacktestResult
-> FailureCase
-> ReviewFinding
```

Output: formal L6 evidence.

### W6 Routine Optimization

```text
Scheduled Label Production
-> Approved Strategy Run
-> Signal Generation
-> Observation Update
-> Periodic Review
-> Optimization Candidate
```

Output: observation records and new candidate versions.

## Skill Strategy

Do not build one huge skill for the whole system.

Use one thin router skill plus focused workflow skills:

```text
stock-lobster-router
stock-lobster-data-foundation
stock-lobster-pattern-research
stock-lobster-strategy-construction
stock-lobster-backtest-review
stock-lobster-routine-optimization
stock-lobster-architecture-review
```

The router skill should only decide which workflow skill applies.

Each workflow skill should specify:

- when to use it
- files and docs to read first
- allowed file scopes
- required tools or CLI commands
- required artifacts
- approval gates
- validation commands
- session closeout format

## Tool Strategy

Build tools as small reusable capabilities, not as hidden strategy engines.

Recommended tool groups:

```text
DataAssetTool
SnapshotBuilderTool
PatternCaseTool
FactorObservationTool
PrimitiveCandidateTool
LabelCandidateTool
StrategyComposerTool
BacktestRunnerTool
FailureAnalyzerTool
ApprovalTool
ScheduleTool
ObservationReviewTool
```

Tool rules:

- Tools read and write through public application services.
- Tools preserve version, provenance, and run id.
- Tools must not silently approve candidates.
- Tools must not create factual data inside Stock Lobster.
- Tools must make their input and output artifacts inspectable.

## Model Selection Standard

Coding can switch models. Use the model based on risk, ambiguity, and scope.

| Model | Use for | Avoid for |
| --- | --- | --- |
| GPT-5.5 | architecture, boundaries, schema design, difficult multi-layer code, DSL, backtest logic, final review | trivial scans |
| GPT-5.4 | routine implementation, tests, CLI, config readers, stable layer work | major ambiguous architecture decisions |
| GPT-5.4-Mini | repository scans, table/catalog discovery, summaries, small config edits, repetitive tests | final strategy semantics or complex refactors |
| GPT-5.3-Codex-Spark | quick questions, tiny local edits, fast iteration on one narrow issue | durable architecture, large changes, production semantics |

Default rule:

```text
Design with GPT-5.5.
Implement stable modules with GPT-5.4.
Scan and draft with GPT-5.4-Mini.
Use Codex-Spark only for fast small loops.
Review important changes with GPT-5.5.
```

## Model Handoff Rules

When switching models, include a handoff note:

```text
Goal:
Allowed files:
Must read:
Layer boundary:
Artifacts to produce:
Validation:
Open questions:
```

For implementation sessions, always include:

- target workflow
- layer or bounded context
- exact allowed directories
- tests to run
- approval gates

## Implementation Order

Recommended order:

1. Keep the current planning baseline and import-boundary tests.
2. Add `shared/contracts` or equivalent contract models only when needed.
3. Build first L0 `DataAsset` catalog from existing factual tables.
4. Build first L1 `AnalysisSnapshot`.
5. Add `research/` workflow objects for pattern sample analysis.
6. Use one pattern family to draft primitive and label candidates.
7. Approve one tiny primitive and one tiny label.
8. Build one candidate `StrategyDSL`.
9. Run one formal backtest.
10. Add observation and routine optimization only after the first strategy loop
    is reproducible.

## What Future Models Must Not Do

- Do not move factual production logic into L2-L6.
- Do not let strategy DSL read raw prices directly.
- Do not let `data_foundation` emit buy/sell semantics.
- Do not approve candidates automatically.
- Do not bury production logic in a skill.
- Do not put core business rules only in a tool wrapper.
- Do not add broad abstractions before one end-to-end pattern case exists.

## Minimum Done Criteria for New Code

Any new production-facing code must answer:

- Which bounded context owns it?
- Which workflow uses it?
- Which layer or registry does it belong to?
- Which artifact version does it produce or consume?
- Which tests prove it does not violate import boundaries?
- Which user approval is required before production use?

If these questions cannot be answered, keep the work as research evidence or a
candidate artifact instead of registering it as production behavior.
