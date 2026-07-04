# ADR 001: Pattern Research to Experience Data Production

## Status

Accepted draft.

## Context

Upstream systems are expected to provide factual data only, such as market
prices, volume, derived factual indicators, trading calendars, stock metadata,
industry metadata, and data quality status.

In early phases, there may be very little research-derived or
experience-derived data. Stock Lobster therefore needs a production research
workflow that starts from real stock pattern samples, associates observable
factors, distills primitive definitions, builds labels, evaluates strategy
combinations, and then either schedules repeatable production or registers the
calculation contract into the proper layer.

This does not change the hard boundary that Stock Lobster must not produce
canonical factual data.

## Decision

Stock Lobster owns experience data production.

Experience data means versioned research and strategy artifacts derived from
factual data, not factual data itself. Examples include:

- pattern cases and pattern cohorts
- factor observations tied to a pattern sample
- primitive candidates
- approved primitive definitions
- label candidates
- approved label definitions and label snapshots
- strategy candidates
- evaluation profiles
- backtest evidence
- production approval records
- observation and review records

The main workflow is:

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

## Layer Placement

Experience artifacts must be placed by responsibility:

| Artifact | Layer or area | Rule |
| --- | --- | --- |
| `PatternCase` | Research orchestration | Sample evidence, not a factual source |
| `FactorObservation` | Research orchestration | References L1 fields and source DataAssets |
| `PrimitiveCandidate` | Research orchestration | Proposed L2 contract, not executable production logic |
| approved `PrimitiveDefinition` | L2 | Pure function over `AnalysisSnapshot` only |
| `LabelCandidate` | Research orchestration | Proposed L3 contract |
| approved `LabelDefinition` | L3 | Deterministic label derived from L2 primitive outputs |
| `LabelSnapshot` | L3 | Repeatable semantic production output |
| `StrategyCandidate` | L4 | Candidate DSL, not approved production strategy |
| approved `StrategyDSL` | L4 | White-box versioned strategy definition |
| `StrategySignal` | L5 | Formal signal output |
| `BacktestResult` | L6 | Formal evaluation output |
| `ObservationRecord` | Observation workflow | Future tracking evidence |

Research orchestration can coordinate lower layers, but L0-L6 must not depend
on research orchestration modules.

## Production Modes

Every research-derived artifact must choose one of three outcomes:

1. Archive as research evidence only.
2. Register a calculation contract into the proper layer.
3. Schedule repeatable production for an approved layer artifact.

Examples:

- A sample note that explains why a stock looked interesting stays as
  `PatternCase`.
- A reusable pure calculation becomes an L2 `PrimitiveDefinition`.
- A deterministic semantic field becomes an L3 `LabelDefinition` and scheduled
  `LabelSnapshot` production.
- A white-box selection recipe becomes an L4 `StrategyDSL`.
- A verified candidate strategy can be approved for L5 signal generation and
  L6 backtesting.

## Approval Boundary

The system may automatically draft:

- pattern cases
- factor observations
- primitive candidates
- label candidates
- strategy candidates
- evaluation suggestions
- backtest evidence
- review findings

The system must not silently approve:

- formal primitives
- formal labels
- production strategy versions
- observation pool entry
- formal signal publishing
- replacement of an approved strategy version

Approval must record who approved it, when it was approved, the evidence set,
and the exact version being approved.

## Alignment With Upstream Data Production

Upstream factual data projects align with Stock Lobster through contracts, not
through shared strategy code.

Required links:

- `DataAsset` id and version
- field schema and field semantics
- data quality status
- `AnalysisSnapshot` version
- primitive version
- label version
- strategy version
- evaluation profile version
- run id

This lets an approved strategy explain both:

- which upstream factual data it used
- which Stock Lobster experience artifacts turned those facts into strategy
  semantics

## Consequences

Benefits:

- real samples drive primitives and labels instead of abstract guessing
- experience production remains reproducible and auditable
- upstream data production stays clean and factual
- strategy semantics can evolve through explicit versions
- scheduled label or strategy production can be traced back to research cases

Tradeoffs:

- more registry and approval objects are needed
- early research flow is slower than directly hard-coding strategies
- sample quality matters, so weak examples must remain research evidence rather
  than approved layer contracts

## First Implementation Implication

Before adding many primitives, implement a small research workflow model:

```text
PatternCase
FactorObservation
PrimitiveCandidate
LabelCandidate
StrategyCandidate
ApprovalDecision
```

Then use one real pattern family as the first end-to-end test case. The first
pattern family should be small enough to inspect manually and rich enough to
exercise L1-L6.
