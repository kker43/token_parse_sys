# Stock Lobster Execution Plan

This plan turns `requirements.md` and `sys_command.md` into an implementation
sequence. It is the working map for Codex sessions and should be updated when
architecture decisions are made.

## Current State

- Existing project files: `requirements.md`, `sys_command.md`, `AGENTS.md`,
  and this plan.
- The workspace is initialized as a Git repository on `main`.
- M1 has a minimal Python package scaffold with strict import-boundary tests.
- Standard system structure and model guidance is documented in
  `docs/standards/001-system-structure-and-model-guidance.md`.
- The next implementation step should define the first data asset contracts and
  the research workflow objects that turn real pattern samples into registered
  experience artifacts.

## Non-Negotiable Boundaries

- Stock Lobster does not produce canonical factual data.
- Stock Lobster does produce versioned experience data, such as pattern cases,
  primitive candidates, approved primitive contracts, label definitions,
  strategy candidates, evaluation evidence, approval records, and observation
  records.
- External data comes through registered `DataAsset` contracts.
- `token_fetch` remains an external producer; this project builds adapters and
  catalogs instead of merging that repository.
- `StrategyDSL` cannot reference raw price or volume tables directly.
- Agents cannot create facts, approved primitives, approved labels, approved
  strategies, formal signals, or backtest results by themselves.
- User confirmation is required before a candidate strategy becomes approved,
  enters the observation pool, replaces an approved version, or publishes formal
  signals.

## Pattern Research to Experience Production

Stock Lobster has a production research workflow in addition to the L0-L6
execution layers. This workflow starts from real stock pattern samples and
turns research evidence into versioned experience artifacts.

Reference decision: `docs/decisions/001-pattern-research-to-experience-production.md`.

Core flow:

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
-> ObservationRecord
-> ReviewFinding
-> NewCandidateVersion
```

Responsibilities:

- Research orchestration owns sample cases, factor observations, candidate
  semantics, approval evidence, and review findings.
- L2 owns approved primitive definitions and pure primitive execution.
- L3 owns approved label definitions and repeatable label snapshot production.
- L4 owns approved strategy DSL versions and candidate strategy schemas.
- L5 owns formal signal production.
- L6 owns formal backtest results.

Rules:

- Research artifacts are experience data, not canonical factual data.
- Candidate primitives, labels, and strategies are not production artifacts
  until approved and registered.
- Scheduled production is allowed only for approved layer artifacts.
- Every approved artifact must preserve links to sample evidence, upstream
  `DataAsset` dependencies, version, and `run_id`.
- Research orchestration may coordinate L0-L6, but L0-L6 must not depend on
  research orchestration.

## Target Directory Layout

First code scaffold:

```text
stock_lobster/
  __init__.py
  core/
    __init__.py
    ids.py
    versioning.py
    audit.py
    errors.py
  l0_data_access/
    __init__.py
    contracts.py
    catalog.py
    repositories.py
    adapters/
      __init__.py
      token_fetch_mysql.py
  l1_analysis_snapshot/
    __init__.py
    schema.py
    builder.py
    repository.py
  l2_primitives/
    __init__.py
    registry.py
    functions.py
  l3_labels/
    __init__.py
    registry.py
    snapshot.py
    generator.py
  l4_strategy_dsl/
    __init__.py
    schema.py
    candidate_pool.py
    stage_pipeline.py
    validator.py
  l5_signal_engine/
    __init__.py
    engine.py
    ranking.py
    explanation.py
  l6_backtest_engine/
    __init__.py
    profiles.py
    engine.py
    metrics.py
    result.py
  research/
    __init__.py
    pattern_case.py
    factor_observation.py
    candidates.py
    approval.py
  app/
    __init__.py
    cli.py
configs/
  data_assets/
  labels/
  strategies/
docs/
  decisions/
  standards/
  examples/
tests/
  test_import_boundaries.py
  l0_data_access/
  l1_analysis_snapshot/
  l2_primitives/
  l3_labels/
  l4_strategy_dsl/
  l5_signal_engine/
  l6_backtest_engine/
```

The initial scaffold should include only minimal models, validators, and tests.
Avoid building a full database schema before the first DataAsset catalog is
clear.

## Layer Ownership

### L0 Data Access Contract Layer

Purpose:

- Describe external tables, files, APIs, schemas, quality status, and update
  frequency.
- Provide safe query contracts for downstream layers.

Initial deliverables:

- `ExternalDataContract`
- `DataAsset`
- `DataAssetCatalog`
- `token_fetch` MySQL adapter draft
- catalog examples for daily, weekly, monthly, MA, volatility, amount, and
  basic stock tables

Acceptance:

- L0 never imports L1-L6.
- Every external field has source, type, date semantics, and quality status.
- No factual data is modified.

### L1 Analysis Snapshot Layer

Purpose:

- Build reproducible analytical snapshots from L0 contracts.
- Record source dependencies and query parameters.

Initial deliverables:

- `AnalysisSnapshot`
- `AnalysisSnapshotDependency`
- snapshot builder interface
- in-memory repository for tests

Acceptance:

- L1 imports L0 only through public contract objects.
- Every snapshot has `analysis_version`, `run_id`, `stock_code`, and
  `snapshot_date`.
- Snapshot output is traceable to DataAsset dependencies.

### L2 Primitive Function Layer

Purpose:

- Define pure functions over `AnalysisSnapshot`.

Initial deliverables:

- `PrimitiveDefinition`
- primitive registry
- first candidate primitive examples, such as MA convergence and volume
  expansion, using synthetic test snapshots

Acceptance:

- No external data access.
- No stateful behavior.
- Primitive outputs are boolean or numeric scores.

### L3 Label Snapshot Layer

Purpose:

- Build deterministic versioned labels from registered primitives.

Initial deliverables:

- `LabelDefinition`
- `LabelSnapshot`
- label registry
- label generator

Acceptance:

- Labels depend on L2 primitive results, not raw data.
- Label snapshots include `label_version` and `run_id`.
- Label generation is reproducible from the same input snapshot.

### L4 Strategy DSL Layer

Purpose:

- Define human-readable white-box strategy rules.

Initial deliverables:

- `StrategyDSL` schema
- `CandidatePoolPolicy`
- `StagePipeline`
- recall, filter, reject, scoring, ranking, and horizon structures
- DSL validator that rejects raw data references

Acceptance:

- DSL references approved label fields only.
- Candidate pool policy is versioned and backtest-reproducible.
- Strategy candidates remain separate from approved strategies.

### L5 Signal Engine Layer

Purpose:

- Execute approved or candidate DSLs over label snapshots and produce ranked
  signal results.

Initial deliverables:

- `StrategySignal`
- signal engine
- ranking engine
- explanation builder

Acceptance:

- Formal signals are generated only here.
- Each result explains candidate pool entry, triggered labels, filters,
  warnings, ranking score, and rank.
- Candidate strategies can run trial signals without becoming approved.

### L6 Backtest Engine Layer

Purpose:

- Reproduce strategy runs over historical dates and generate backtest results.

Initial deliverables:

- `EvaluationProfile`
- event-return backtest
- fixed-horizon backtest
- ranking bucket analysis
- `BacktestResult`

Acceptance:

- Formal backtest results are generated only here.
- Candidate pool generation is reproduced, not approximated.
- Results include benchmark, horizon, sample size, returns, drawdown, win rate,
  and failure cases.

## Milestone Plan

### M0 Project Control Baseline

Status: draft complete

Deliverables:

- `AGENTS.md`
- `PLANS.md`
- initial directory and layer ownership plan
- unresolved decision list

Done when:

- Future sessions have clear ownership boundaries.
- The first code scaffold is unambiguous.

### M1 Engineering Scaffold

Deliverables:

- Python package layout
- test runner
- import-boundary tests
- minimal core versioning and audit types
- example config directories

Done when:

- Tests can run locally.
- A dependency rule prevents upward layer imports.

### M2 Data Asset Catalog

Deliverables:

- L0 contract models
- first token_fetch catalog draft
- table and field metadata
- quality/update metadata placeholders

Done when:

- At least one real external table is represented as a `DataAsset`.
- No business layer reads external data directly.

### M3 Analysis Snapshot MVP

Deliverables:

- L1 snapshot schema
- dependency tracking
- snapshot builder from L0 rows
- synthetic tests

Done when:

- One stock/date snapshot can be built from cataloged data.
- Snapshot provenance is recorded.

### M4 Primitive and Label MVP

Deliverables:

- research workflow objects for `PatternCase`, `FactorObservation`,
  `PrimitiveCandidate`, and `LabelCandidate`
- primitive registry
- label registry
- first deterministic label snapshot generator

Done when:

- One real or synthetic pattern case can produce candidate primitive and label
  definitions without becoming approved automatically.
- A label can be reproduced from the same analysis snapshot and version.

### M5 Strategy DSL MVP

Deliverables:

- Strategy DSL schema
- candidate pool policy
- stage pipeline
- DSL validator
- example candidate strategy

Done when:

- A strategy can express quality, trend, fine-filter, entry, and ranking stages.
- Validator rejects raw data references.

### M6 Signal and Backtest MVP

Deliverables:

- signal engine
- explanation output
- event-return and fixed-horizon backtests
- backtest report structure

Done when:

- Candidate strategy can produce trial signals and a backtest report.
- Approved strategy flow is still gated by user confirmation.

### M7 Observation and Review Loop

Deliverables:

- approval state flow
- observation pool records
- future tracking results
- periodic review report draft

Done when:

- Approved strategy signals can be tracked without mutating historical strategy
  definitions.

## Recommended Session Plan

Run sessions with non-overlapping file ownership.

| Session | Model | File Scope | Mission |
| --- | --- | --- | --- |
| S0 | GPT-5.5 | `AGENTS.md`, `PLANS.md`, `docs/decisions/` | Architecture control |
| S1 | GPT-5.4-Mini | Read-only or `configs/data_assets/` | Discover external data contracts |
| S2 | GPT-5.5 | package scaffold, tests | Create engineering foundation |
| S3 | GPT-5.5 | `l0_data_access/`, `l1_analysis_snapshot/` | Data contracts and snapshots |
| S4R | GPT-5.5 | `research/`, research docs | Pattern research and experience candidates |
| S4 | GPT-5.4 | `l2_primitives/`, `l3_labels/` | Primitives and labels |
| S5 | GPT-5.5 | `l4_strategy_dsl/` | DSL, candidate pools, pipelines |
| S6 | GPT-5.5 | `l5_signal_engine/` | Signal execution and explanation |
| S7 | GPT-5.5 | `l6_backtest_engine/` | Backtesting |
| S8 | GPT-5.4 | `app/`, observation docs | Approval and observation workflow |
| S9 | GPT-5.5 | review only or narrow fixes | Boundary and quality review |

## Prompt Templates

Architecture session:

```text
You are the S0 architecture-control session for Stock Lobster.
Read requirements.md, sys_command.md, AGENTS.md, and PLANS.md.
Do not implement business code unless asked.
Clarify architecture decisions, update docs, and keep layer boundaries strict.
```

Layer implementation session:

```text
You are responsible only for <LAYER>.
Read requirements.md, sys_command.md, AGENTS.md, and PLANS.md first.
Only modify files in <ALLOWED PATHS>.
Do not bypass lower-layer contracts.
Add focused tests.
End with changed files, validation, layer-boundary check, and open questions.
```

Review session:

```text
Review the current workspace for Stock Lobster.
Prioritize layer violations, strategy/data boundary violations, missing tests,
and reproducibility gaps.
Report findings first with file and line references.
Do not refactor unless explicitly asked.
```

## Open Decisions

Decisions to settle before or during M1/M2:

- Initialize this directory as the project Git repository, or move these docs
  into an existing repository?
- Use Python packaging with `pyproject.toml`, or another runtime?
- Store registry and snapshot data in local files, MySQL, SQLite, or a mixed
  approach for the first MVP?
- Represent `StrategyDSL` as YAML, JSON, database records, Python objects, or
  a combination?
- What is the first stock pattern used to drive candidate strategy generation?
- Which benchmark is the first default: CSI 300, CSI 500, CSI 1000, all-A
  equal weight, or strategy-specific benchmarks?
- Should first user approval be CLI-based, database-status-based, Markdown
  review-file-based, or web-based?
- Should observation updates run manually at first or on a daily schedule?

## Immediate Next Step

Recommended next action:

1. Decide whether to initialize Git here.
2. Create the M1 Python scaffold.
3. Add import-boundary tests before adding business logic.
4. Use a read-only S1 session to inspect `token_fetch` data contracts and draft
   the first `configs/data_assets/` entries.
