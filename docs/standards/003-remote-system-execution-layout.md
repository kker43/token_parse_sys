# Standard 003: Remote System Execution Layout

## Purpose

This standard defines how the large project should be organized on the remote
server and where routine jobs, external interfaces, common tools, contracts,
and bounded-context code should live.

Target remote root:

```text
/home/ubuntu/token_parse_sys
```

## Design Rule

The project should be one operational system, but not one flat codebase.

Use one root directory with separate bounded contexts:

```text
token_parse_sys/
  shared/
  data_foundation/
  stock_lobster/
  workflows/
  interfaces/
  tools/
  configs/
  ops/
  docs/
```

Each area has one job. If a file does not clearly belong to one area, keep it
out of production until ownership is clear.

## Target Remote Directory

```text
/home/ubuntu/token_parse_sys/
  README.md

  shared/
    contracts/
    schemas/
    calendar/
    enums/

  data_foundation/
    token_fetch_bridge/
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
    definitions/
    jobs/
    runners/

  interfaces/
    cli/
    api/
    sql/
    reports/

  tools/
    data_asset/
    snapshot/
    research/
    strategy/
    backtest/
    approval/
    observation/

  configs/
    data_sources/
    data_assets/
    primitives/
    labels/
    strategies/
    evaluation_profiles/
    schedules/

  ops/
    crontab/
    systemd/
    env/
    runbooks/
    logs/

  docs/
    decisions/
    standards/
    workflows/
    examples/
```

## Area Responsibilities

### `shared/`

Owns cross-context language and contracts.

Put here:

- shared field names
- asset id conventions
- date semantics
- quality status enums
- schema fragments
- version and run id conventions

Do not put executable production workflows here.

### `data_foundation/`

Owns factual data production and basic indicators.

Put here:

- data source adapters
- ingestion tasks
- normalization logic
- basic statistics and basic indicators
- quality checks
- `pub_*` catalog export
- wrappers around the existing `/home/ubuntu/token_fetch` project

Do not put:

- primitives
- labels
- strategies
- signals
- backtests
- trading candidates

Current transition rule:

```text
/home/ubuntu/token_fetch remains the running producer.
/home/ubuntu/token_parse_sys/data_foundation/token_fetch_bridge wraps or mirrors
stable contracts from token_fetch when needed.
```

Do not copy `token_fetch` runtime artifacts into the new root.

### `stock_lobster/`

Owns experience data, strategy semantics, signal generation, backtesting, and
observation.

Put here:

- L0-L6 layer packages
- pattern research objects
- candidate and approval models
- observation and review logic
- application services used by interfaces and tools

Do not put source ingestion or upstream data repair logic here.

### `workflows/`

Owns process composition.

Use this for entrypoints that combine several bounded contexts into one
business process.

Recommended layout:

```text
workflows/
  definitions/
    daily_fact_data_production.yaml
    daily_snapshot_production.yaml
    daily_label_production.yaml
    daily_signal_generation.yaml
    daily_observation_review.yaml
  jobs/
    daily_fact_data_production.py
    daily_snapshot_production.py
    daily_label_production.py
    daily_signal_generation.py
    daily_observation_review.py
  runners/
    local_runner.py
    cron_runner.py
```

Routine schedulers should call files under `workflows/jobs/`.

Workflow jobs should orchestrate public services. They should not hide domain
rules that belong in `data_foundation/` or `stock_lobster/`.

### `interfaces/`

Owns stable entrypoints for humans and external systems.

Put here:

- CLI commands exposed to users or operators
- API adapters, if a service is added later
- stable SQL or view consumption examples
- report renderers and export adapters

Examples:

```text
interfaces/cli/lobster.py
interfaces/api/
interfaces/sql/
interfaces/reports/
```

Interfaces call application services and workflows. They do not own business
truth.

### `tools/`

Owns reusable callable helpers for agents, scripts, and operators.

Put here:

- data asset inspection helpers
- snapshot builders
- pattern case utilities
- strategy composition helpers
- backtest runner wrappers
- approval helpers
- observation review helpers

Tool rules:

- tools are thin wrappers
- tools preserve version and provenance
- tools must not silently approve anything
- tools must not produce canonical factual data inside Stock Lobster
- tools must not become the only place where a business rule exists

### `configs/`

Owns versioned configuration and registry files.

Put here:

- data source config templates
- data asset configs
- primitive registry files
- label registry files
- strategy configs
- evaluation profiles
- schedule definitions

Secrets do not go here.

### `ops/`

Owns deployment and operations.

Put here:

- crontab entries
- systemd units
- environment templates
- runbooks
- log directory conventions

Runtime logs may live under `ops/logs/` or a server-specific log path, but
should not be committed as source artifacts.

## Routine vs Passive Components

Use this split:

| Component | Routine execution? | Location |
| --- | --- | --- |
| fact data production | yes | `workflows/jobs/daily_fact_data_production.py` wraps `data_foundation` |
| snapshot production | yes | `workflows/jobs/daily_snapshot_production.py` |
| label production | yes | `workflows/jobs/daily_label_production.py` |
| approved strategy signal run | yes | `workflows/jobs/daily_signal_generation.py` |
| observation review | yes | `workflows/jobs/daily_observation_review.py` |
| primitive functions | passive | `stock_lobster/l2_primitives/` |
| label definitions | passive contract, routine output | `stock_lobster/l3_labels/` and `configs/labels/` |
| StrategyDSL | passive contract, routine input | `stock_lobster/l4_strategy_dsl/` and `configs/strategies/` |
| backtest engine | passive service, on-demand or scheduled | `stock_lobster/l6_backtest_engine/` |
| CLI | passive entrypoint | `interfaces/cli/` |
| API | passive entrypoint | `interfaces/api/` |
| shared schema | passive | `shared/` |
| common helper | passive | `tools/` |

## Public Interface Rules

Public interfaces are the only supported entrypoints for external users or
systems.

Allowed public surfaces:

- `interfaces/cli/`
- `interfaces/api/`
- `interfaces/sql/`
- `workflows/jobs/` for schedulers
- documented `pub_*` products from `data_foundation`

Do not ask external callers to import internal layer modules directly.

## Scheduler Rules

Cron or systemd should call only stable job entrypoints:

```text
/home/ubuntu/token_parse_sys/workflows/jobs/*.py
```

Each job should:

1. load schedule config
2. check upstream readiness
3. call public application services
4. write structured result
5. return non-zero on failure
6. preserve `run_id`
7. write audit or status records

Existing `token_fetch/cron_script` remains valid during transition, but new
cross-system jobs should live under `token_parse_sys/workflows/jobs/`.

## Cross-Context Import Rules

Allowed:

```text
workflows -> data_foundation public services
workflows -> stock_lobster public services
interfaces -> workflows or application services
tools -> public services
stock_lobster L1 -> stock_lobster L0
stock_lobster L2 -> stock_lobster L1
stock_lobster L3 -> stock_lobster L2
stock_lobster L4 -> stock_lobster L3
stock_lobster L5 -> stock_lobster L4
stock_lobster L6 -> stock_lobster L5/L4 through public replay contracts
```

Forbidden:

```text
stock_lobster -> data_foundation ingestion internals
stock_lobster L0-L6 -> stock_lobster.research
data_foundation -> stock_lobster strategy semantics
shared -> data_foundation or stock_lobster runtime code
tools -> hidden production-only business rules
interfaces -> direct database writes bypassing services
```

## First Execution Plan

Use this order:

1. Create `/home/ubuntu/token_parse_sys` with the top-level directories.
2. Keep `/home/ubuntu/token_fetch` as the running data producer.
3. Add `data_foundation/token_fetch_bridge/` only when reading stable contracts
   from `token_fetch`.
4. Add first `configs/data_assets/` entries for `pub_*` products.
5. Implement Stock Lobster L0 catalog loading from those configs.
6. Implement one L1 `AnalysisSnapshot` builder.
7. Implement `research/` sample-to-candidate objects.
8. Add routine workflow entrypoints only after the passive services exist.

## Review Checklist

Before adding a file, answer:

- Is this factual production, experience production, workflow orchestration,
  external interface, or common tooling?
- Is it routine or passive?
- Which directory owns it?
- Does it need a registry entry?
- Does it need `run_id`, version, or approval metadata?
- Which test proves it did not cross a boundary?

If ownership is unclear, document it as a candidate design before writing
production code.
