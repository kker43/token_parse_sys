# Stock Lobster Agent Guide

This file defines how Codex sessions should work in this repository. It is
binding for all project work unless the user explicitly overrides it.

## Read First

Before making changes, read:

1. `requirements.md`
2. `sys_command.md`
3. `PLANS.md`
4. `docs/standards/001-system-structure-and-model-guidance.md`
5. `docs/standards/002-data-foundation-integration.md`
6. `docs/standards/003-remote-system-execution-layout.md`
7. The nearest relevant source files and tests, once code exists

If any instruction conflicts, prefer this order:

1. The user's latest request
2. `sys_command.md`
3. `requirements.md`
4. `PLANS.md`
5. `docs/standards/001-system-structure-and-model-guidance.md`
6. `docs/standards/002-data-foundation-integration.md`
7. `docs/standards/003-remote-system-execution-layout.md`
8. This file

## Project Mission

Stock Lobster is an A-share strategy research, analysis orchestration, signal
generation, backtesting, and observation system.

It does not produce canonical factual market data. External systems such as
`<external_producer_root>` produce factual data and expose data contracts.
Stock Lobster consumes those contracts, builds reproducible analytical
snapshots, derives deterministic labels, runs white-box strategy DSLs, produces
signals, backtests them, and tracks future performance.

## Hard Architecture Rules

The system is strictly layered:

```text
L0 Data Access Contract Layer
L1 Analysis Snapshot Layer
L2 Primitive Function Layer
L3 Label Snapshot Layer
L4 Strategy DSL Layer
L5 Signal Engine Layer
L6 Backtest Engine Layer
```

Rules:

- Lower layers must not depend on upper layers.
- Upper layers may only consume lower-layer outputs.
- No cross-layer bypass is allowed.
- Stock Lobster must not collect, clean, repair, rewrite, or become the source
  of canonical factual data.
- L0 is the only layer that talks to external data contracts.
- L1 builds versioned `AnalysisSnapshot` objects from L0 outputs.
- L2 primitives are pure functions over `AnalysisSnapshot` only.
- L3 labels are deterministic snapshots derived from registered primitives.
- L4 `StrategyDSL` may only reference approved `LabelSnapshot` fields and
  approved metadata fields.
- L5 is the only layer that generates `StrategySignal`.
- L6 is the only layer that generates `BacktestResult`.
- Agents may propose candidates, orchestrate tools, explain results, and draft
  plans, but they may not produce factual data or bypass the DSL/backtest
  engines.

## External Data Boundary

Initial data access may adapt the remote `<external_producer_root>` project, but
do not merge that repository wholesale.

Do not import or copy:

- virtual environments
- logs
- runtime tracker files
- historical reports
- `old_version`
- temporary files

Prefer adapters, catalogs, registries, and reproducible query contracts.

For data foundation work, also read
`docs/workflows/001-data-foundation-mvp.md`.

## Suggested Initial Code Layout

Use this layout unless a later architecture decision changes it:

```text
stock_lobster/
  core/
  l0_data_access/
  l1_analysis_snapshot/
  l2_primitives/
  l3_labels/
  l4_strategy_dsl/
  l5_signal_engine/
  l6_backtest_engine/
  research/
  app/
configs/
  data_assets/
  labels/
  strategies/
docs/
  decisions/
  standards/
  examples/
tests/
  l0_data_access/
  l1_analysis_snapshot/
  l2_primitives/
  l3_labels/
  l4_strategy_dsl/
  l5_signal_engine/
  l6_backtest_engine/
```

Layer packages may import from `stock_lobster.core` and lower-numbered layers
only. L0-L6 must not import `stock_lobster.research` or `stock_lobster.app`.
Tests should enforce this once implementation begins.

## Multi-Session Work Rules

Use separate sessions by ownership boundary, not by vague feature names.

Recommended sessions:

- S0 Architecture control: docs, plans, unresolved decisions, boundaries.
- S1 Data contract reconnaissance: external table and field discovery, read
  only unless writing catalog drafts.
- S2 Engineering scaffold: package layout, test setup, dependency checks.
- S3 Data foundation and L0/L1: shared contracts, `data_foundation` bridge,
  L0 data assets, and analysis snapshots.
- S4R Pattern research: sample cases, factor observations, candidates, and
  approval evidence for experience data.
- S4 L2/L3: primitives, labels, registries.
- S5 L4: strategy DSL, candidate pool policy, stage pipeline, validators.
- S6 L5: signal execution, explanations, ranking.
- S7 L6: backtest profiles, metrics, result persistence.
- S8 Observation/app: approval flow, observation pool, CLI/reporting.
- S9 Review: architecture, dependency, test, and regression review.

Do not run two sessions that modify the same files at the same time.

## Model Use Guidance

- Use GPT-5.5 for architecture, ambiguous multi-step work, DSL design, signal
  engine, backtesting, and final review.
- Use GPT-5.4 for stable implementation, tests, CLI, and routine coding.
- Use GPT-5.4-Mini for scans, catalog exploration, summaries, and small
  supporting tasks.
- Use GPT-5.3-Codex-Spark only for near-instant small iterations or quick
  local questions.

For larger handoffs, follow
`docs/standards/001-system-structure-and-model-guidance.md`.

## Implementation Standards

- Keep changes scoped to the current layer/session.
- Prefer explicit schemas and registries over implicit dictionaries.
- Prefer deterministic, reproducible functions over agent-generated state.
- Every durable artifact that affects strategy behavior needs a version and,
  where applicable, a `run_id`.
- Store candidate strategy semantics separately from approved production
  strategy semantics.
- Preserve human approval boundaries for strategy promotion, observation entry,
  and approved version replacement.
- Do not add large abstractions before there is a concrete layer use case.

## Validation Expectations

When code exists, each implementation session should run the smallest relevant
checks, then report what ran and what did not run.

Expected check categories:

- formatting
- linting
- unit tests for the changed layer
- import-boundary tests
- schema validation tests
- reproducibility tests for snapshots, labels, signals, and backtests

If no test framework exists yet, the engineering scaffold session should create
one before business logic expands.

## Session Closeout Format

Every implementation session should end with:

```text
Changed:
- ...

Validated:
- ...

Layer boundary check:
- ...

Open questions:
- ...
```

Keep closeouts short and evidence-based.
