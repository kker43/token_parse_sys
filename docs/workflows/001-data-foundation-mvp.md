# Workflow 001: Data Foundation MVP

## Purpose

Define the first executable slice for bringing basic factual data capability
into `token_parse_sys`.

This workflow covers:

- external factual data contracts
- basic data product interfaces
- routine data production entrypoints
- routine quality monitoring
- Stock Lobster L0 consumption boundaries

It does not cover:

- pattern research
- primitives
- labels
- strategy DSL
- signal generation
- backtest execution
- observation review

Those belong to later workflows after this data foundation slice is stable.

## Model Recommendation

Do not switch to a smaller model before this workflow is accepted.

Recommended split:

| Work | Model |
| --- | --- |
| workflow design, boundary decisions, schema decisions | GPT-5.5 |
| deterministic code implementation and tests | GPT-5.4 |
| registry scanning, config draft generation, repetitive checks | GPT-5.4-Mini |
| tiny local fixes only | GPT-5.3-Codex-Spark |

The first code implementation after this document can use GPT-5.4 as long as
the session reads this workflow, `AGENTS.md`, and the standards first.

## Current Upstream Assumption

The upstream factual producer is:

```text
host: ubuntu@111.229.103.59
path: /home/ubuntu/token_fetch
branch: dev/basic_fetch_20260704
latest inspected commit: b598b34
```

`token_fetch` remains the running producer during this MVP. This project should
not rewrite or move it yet.

`token_parse_sys` consumes stable contracts and readiness state from it.

## Target Boundary

```text
token_fetch
  -> produces factual tables and pub_* products
  -> exposes registry files and quality status

token_parse_sys/data_foundation
  -> mirrors or reads contracts
  -> validates product readiness
  -> exports DataAsset configs for Stock Lobster
  -> provides routine bridge jobs

token_parse_sys/stock_lobster/l0_data_access
  -> consumes DataAsset configs
  -> never reads token_fetch internals directly unless explicitly marked
     transitional
```

## MVP Components

### 1. Shared Contracts

Location:

```text
shared/contracts/
```

Initial objects:

```text
DataProductContract
DataProductField
DataQualityStatus
IndicatorContract
PublishedProductRef
```

Responsibilities:

- define common vocabulary
- preserve product, field, version, date, quality, and source semantics
- be importable by `data_foundation` and `stock_lobster`

Non-goals:

- database access
- production scheduling
- strategy semantics

### 2. Token Fetch Bridge

Location:

```text
data_foundation/token_fetch_bridge/
```

Initial services:

```text
RegistryReader
TokenFetchProductCatalog
TokenFetchQualityReader
```

Responsibilities:

- read or mirror selected registry files from `/home/ubuntu/token_fetch`
- expose normalized contract objects
- keep source path, branch, commit, and registry version in metadata

Non-goals:

- direct strategy use
- moving `token_fetch`
- rewriting `token_fetch` tasks
- writing to upstream tables

### 3. Data Asset Export

Location:

```text
data_foundation/catalog_export/
configs/data_assets/
stock_lobster/l0_data_access/
```

Initial output:

```text
configs/data_assets/token_fetch_pub_products.yaml
```

Initial products:

```text
pub_data_quality_status
pub_stock_daily_kline
pub_stock_weekly_kline
pub_stock_monthly_kline
pub_stock_daily_basic
pub_stock_asset_basic
pub_stock_daily_indicator
```

Responsibilities:

- turn upstream `pub_*` contracts into Stock Lobster L0 `DataAsset` configs
- include field schema, quality gate, source product, data version, and date
  semantics
- keep configs stable enough for L1 snapshot builders

### 4. Routine Job Entrypoints

Location:

```text
workflows/jobs/
```

Initial jobs:

```text
daily_fact_data_production.py
daily_data_quality_monitor.py
daily_data_asset_export.py
```

Responsibilities:

- act as stable scheduler entrypoints
- preserve `run_id`
- call deterministic services
- return non-zero on failure
- write structured job results

Transition behavior:

- `daily_fact_data_production.py` may wrap the existing
  `/home/ubuntu/token_fetch` scheduler during the transition.
- It must not inline `token_fetch` production logic.
- It must record which upstream commit or contract snapshot was used.

### 5. Public Interfaces

Location:

```text
interfaces/cli/
interfaces/sql/
```

Initial CLI commands:

```text
data-foundation list-products
data-foundation check-readiness --date YYYYMMDD
data-foundation export-data-assets
```

Initial SQL examples:

```text
interfaces/sql/check_pub_data_quality_status.sql
interfaces/sql/select_pub_stock_daily_indicator.sql
```

Responsibilities:

- provide stable operator-facing entrypoints
- avoid asking users or jobs to import internal modules

### 6. Quality Monitoring

Location:

```text
data_foundation/quality/
workflows/jobs/daily_data_quality_monitor.py
```

Initial checks:

- product readiness exists
- status is `ready`
- quality level is `pass` or `warning`
- record count meets minimum expectation
- primary date field matches requested date
- core fields are non-null according to contract
- product data version matches registry

Quality result:

```text
DataProductReadinessResult
```

The quality monitor should report readiness. It should not change strategy or
experience artifacts.

## Routine vs Passive Split

| Area | Routine? | First location |
| --- | --- | --- |
| contract dataclasses | no | `shared/contracts/` |
| registry reader | no | `data_foundation/token_fetch_bridge/` |
| readiness checker | no | `data_foundation/quality/` |
| data asset exporter | on demand or scheduled | `data_foundation/catalog_export/` |
| fact production wrapper | yes | `workflows/jobs/daily_fact_data_production.py` |
| quality monitor job | yes | `workflows/jobs/daily_data_quality_monitor.py` |
| operator CLI | passive | `interfaces/cli/` |
| SQL examples | passive | `interfaces/sql/` |
| Stock Lobster L0 catalog | passive | `stock_lobster/l0_data_access/` |

## First Code Slice

Implement this in the first coding session:

```text
shared/contracts/
  __init__.py
  data_product.py
  quality.py

data_foundation/
  __init__.py
  token_fetch_bridge/
    __init__.py
    registry_reader.py
  quality/
    __init__.py
    readiness.py
  catalog_export/
    __init__.py
    data_asset_exporter.py

configs/data_assets/
  token_fetch_pub_products.example.json

tests/
  test_import_boundaries.py
  data_foundation/
    test_data_product_contract.py
    test_readiness.py
```

Use JSON for the first checked-in example config unless YAML parsing dependency
is explicitly added. Upstream can remain YAML.

## Second Code Slice

After the first slice passes tests:

```text
workflows/jobs/
  daily_data_asset_export.py
  daily_data_quality_monitor.py

interfaces/cli/
  data_foundation.py

interfaces/sql/
  check_pub_data_quality_status.sql
  select_pub_stock_daily_indicator.sql
```

These should call services from the first slice.

## Acceptance Criteria

MVP is done when:

- `DataProductContract` can represent all first-stage `pub_*` products.
- L0 `DataAsset` config can be exported from those contracts.
- A readiness checker can deterministically approve or block a product/date.
- Routine job entrypoints exist for quality monitoring and data asset export.
- No Stock Lobster strategy layer reads `token_fetch` internals.
- Import-boundary tests prevent lower layers from importing orchestration code.
- All tests pass locally.

## Open Decisions

- Should production configs be JSON first, or should the project add PyYAML?
- Should the bridge read `/home/ubuntu/token_fetch/config/*.yaml` directly on
  the server, or should those registries be exported into this project first?
- Should `daily_fact_data_production.py` call the existing `token_fetch`
  scheduler, or only monitor its output in the first phase?
- Where should structured job results be persisted: file, MySQL, SQLite, or
  later application tables?

## Handoff Prompt for GPT-5.4 Implementation

```text
You are implementing Workflow 001: Data Foundation MVP.
Read AGENTS.md, PLANS.md, docs/standards/001-system-structure-and-model-guidance.md,
docs/standards/002-data-foundation-integration.md,
docs/standards/003-remote-system-execution-layout.md, and
docs/workflows/001-data-foundation-mvp.md.

Implement only the first code slice:
- shared/contracts data product and quality models
- data_foundation token_fetch_bridge registry reader skeleton
- data_foundation quality readiness checker
- data_foundation catalog_export data asset exporter
- example JSON data asset config
- focused tests

Do not modify token_fetch.
Do not implement strategy, primitive, label, signal, backtest, or observation.
Do not add routine jobs until the passive services pass tests.
Run unittest and report layer boundary status.
```
