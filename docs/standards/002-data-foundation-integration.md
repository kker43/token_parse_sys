# Standard 002: Data Foundation Integration

## Purpose

This standard records how the upstream factual data project should fit into the
larger Stock Lobster system.

It is based on a read-only inspection of:

- remote host: `ubuntu@111.229.103.59`
- upstream path: `/home/ubuntu/token_fetch`
- branch: `dev/basic_fetch_20260704`
- inspected commit: `207fcf9 Prepare production data pipeline baseline`
- inspection date: 2026-07-04

The inspected branch has uncommitted and untracked changes. Treat the findings
as the latest working state, not as a clean release snapshot.

## Remote Deployment Target

Preferred future project directory:

```text
/home/ubuntu/lobster_system
```

This name matches the large-project structure from
`docs/standards/001-system-structure-and-model-guidance.md`.

Do not overwrite existing remote projects such as:

- `/home/ubuntu/token_fetch`
- `/home/ubuntu/token_parse`
- `/home/ubuntu/token_parse_recall`
- `/home/ubuntu/token_recall`

When the project is deployed to the server, create a new directory under
`/home/ubuntu` and copy or clone this repository there. Do not move the existing
`token_fetch` directory until the integration plan is complete.

## Upstream Current Direction

The inspected `token_fetch` branch already matches the desired separation:

```text
source/raw -> fact -> statistic/basic_indicator -> publish/pub_*
```

It explicitly excludes:

- primitive
- signal
- strategy
- backtest
- portfolio
- trading candidates or buy/sell decisions

This is compatible with Stock Lobster:

```text
data_foundation
-> shared contracts
-> stock_lobster.l0_data_access
-> stock_lobster.l1_analysis_snapshot
-> stock_lobster.research
-> L2-L6
```

## Recommended Placement

If this repository evolves into `lobster_system`, place the upstream project as:

```text
lobster_system/
  data_foundation/
    token_fetch_legacy/
    sources/
    ingestion/
    normalization/
    indicators/
    quality/
    catalog_export/
    jobs/

  shared/
    contracts/
    schemas/

  stock_lobster/
    l0_data_access/
    l1_analysis_snapshot/
    research/
    l2_primitives/
    l3_labels/
    l4_strategy_dsl/
    l5_signal_engine/
    l6_backtest_engine/
```

Migration should be gradual:

1. Keep `/home/ubuntu/token_fetch` running independently.
2. Export stable contracts from `token_fetch`.
3. Consume those contracts in Stock Lobster L0.
4. Move or mirror selected source files into `data_foundation` only after the
   contract is stable.

## Do Not Migrate Runtime Artifacts

Do not copy these from `token_fetch` into the clean project:

- `venv/`
- `logs/`
- `tracker/`
- local backup zips
- runtime tracker JSON files at project root
- `.git/`
- machine-local secrets such as `config/config.ini`

These can remain on the server where the running producer lives.

## Contract Assets to Reuse

The following upstream files are useful as starting points:

```text
config/table_registry.yaml
config/task_registry.yaml
config/data_product_registry.yaml
config/indicator_registry.yaml
docs/DATA_STANDARD.md
docs/DATA_PRODUCTS.md
docs/PROJECT_STRUCTURE.md
product_engine/models.py
product_engine/registry.py
```

The SQL files should be treated as drafts:

```text
sql/views/pub_stock_kline_views.sql
sql/views/pub_stock_basic_views.sql
sql/migrations/002_create_pub_stock_daily_indicator.sql
```

## Data Products to Expose to Stock Lobster

Initial L0 `DataAsset` entries should come from `pub_*` products:

| Data product | Stock Lobster use |
| --- | --- |
| `pub_data_quality_status` | readiness gate before consuming any product |
| `pub_stock_daily_kline` | daily price/volume facts |
| `pub_stock_weekly_kline` | weekly price/volume facts |
| `pub_stock_monthly_kline` | monthly price/volume facts |
| `pub_stock_daily_basic` | daily valuation and basic facts |
| `pub_stock_asset_basic` | asset identity and classification |
| `pub_stock_daily_indicator` | long-table basic indicators |

Stock Lobster should not consume internal tables by default. Direct reads from
tables such as `token_daily_details` or `ma_price_daily_statistic` are allowed
only for transitional diagnostics and must be recorded as temporary.

## Basic Indicators as Experience Inputs

These upstream indicators are acceptable as factual or basic-indicator inputs:

- `close_new_high_60d_flag`
- `pct_change_20d`
- `amount_ratio_20d`
- `volatility_60d`
- `ma20`
- `close_above_ma20_flag`
- `convergence_5_10_20`
- `convergence_5_10_20_pct`
- `return_ratio_5d_20d`
- `volatility_ratio_5d_20d`
- `volume_ratio_5d_20d`

They are not Stock Lobster primitives by themselves. Stock Lobster may use them
to build:

- `AnalysisSnapshot` fields
- `FactorObservation`
- `PrimitiveCandidate`
- approved L2 primitives after sample validation
- approved L3 labels after deterministic definition

## Items That Need Changes Before Production Use

### 1. Publish quality status first

`pub_data_quality_status` is the intended readiness gate, but implementation is
still planned. Implement this before downstream production depends on `pub_*`.

Minimum requirement:

```text
data_product
data_date
market
asset_type
status
quality_level
record_count
expected_min_records
source_tables
source_end_date
published_at
data_version
error_message
```

### 2. Do not hard-code `quality_status = 'pass'`

Current SQL drafts set `quality_status` to `pass` directly in views. That is
unsafe for downstream production.

Preferred approach:

- write or compute product-level quality results
- write `pub_data_quality_status`
- expose product rows only when the quality gate is ready
- carry row-level quality only when a real row-level check exists

### 3. Avoid dynamic `CURRENT_TIMESTAMP` in reproducible views

Draft views use `CURRENT_TIMESTAMP AS published_at`. This changes every query
and weakens reproducibility.

Preferred approach:

- materialize publish outputs with a stable `published_at`
- or join a stable publish batch/status table

### 4. Align registry and SQL fields

`pub_stock_daily_indicator` documentation mentions optional
`indicator_score` and `indicator_rank`, but the draft DDL does not include them.

Either:

- add nullable `indicator_score` and `indicator_rank`, or
- remove them from the contract until supported

### 5. Resolve `pub_stock_daily_basic` source mismatch

`data_product_registry.yaml` lists both `token_daily_basic` and
`token_valuation_daily` as source tables, but the draft SQL currently selects
only from `token_daily_basic`.

Either:

- join the valuation source, or
- update the registry to match the actual v1 product

### 6. Review `stock_recall_daily`

`stock_recall_daily` is classified as a fact/event. The name and semantics may
look like strategy recall.

Keep it in `data_foundation` only if it is defined as a neutral event fact, such
as "met objective price/volume event conditions". If it means "candidate stock
for a strategy", move that semantic into Stock Lobster research or L4.

### 7. Expand indicator metadata

`indicator_registry.yaml` should eventually include enough metadata for
reproducibility:

- formula description
- parameter schema
- input windows
- `source_start_date` rule
- `code_version`
- null and outlier handling

### 8. Treat `product_engine` as a draft framework

`product_engine.registry` can be reused soon. `product_engine.publisher` still
returns `publisher_not_implemented`, so it is not production-ready.

## Integration Sequence

Recommended next steps:

1. Stabilize and commit the working `token_fetch` branch.
2. Implement `pub_data_quality_status`.
3. Fix the SQL draft issues above.
4. Export `data_product_registry.yaml` as the first shared contract.
5. Create matching Stock Lobster L0 `DataAsset` configs for each `pub_*`
   product.
6. Build one L1 `AnalysisSnapshot` from `pub_stock_daily_kline`,
   `pub_stock_daily_basic`, `pub_stock_asset_basic`, and
   `pub_stock_daily_indicator`.
7. Use one real pattern family to validate the research workflow.

## Current Recommended Boundary

Keep this rule:

```text
data_foundation answers: what factual data and basic indicators are available?
stock_lobster answers: what pattern, primitive, label, strategy, and evidence
does that data support?
```

The two parts can live in one large project, but they should stay separate by
package, registry, workflow, and approval boundary.
