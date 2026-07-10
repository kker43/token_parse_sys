# Trend Consolidation Rebreakout Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic `research_only` pipeline that classifies the strategy’s core samples, detects the trend-consolidation-rebreakout state machine, compares anomaly/full-market/union candidate pools, and produces H5/H10/H20 evidence for a later L2-L5 promotion decision.

**Architecture:** This plan deliberately stops at the Research layer. It reads external factual inputs through existing TSV contracts, computes candidate factors in focused `stock_lobster.research` modules, writes replayable JSON artifacts, and reuses the existing L6 event-backtest and candidate-pool benchmark services. Formal L2/L3/L4/L5 registration is a second implementation plan after the research evidence passes the design gates.

**Tech Stack:** Python 3.12, standard-library `dataclasses`/`enum`/`json`/`statistics`, repository `unittest`, existing `KlineBar`/`StockSignalContext` readers, existing L6 event backtest and candidate-pool benchmark.

## Global Constraints

- Execute with `/opt/homebrew/bin/python3.12`; the default machine Python does not satisfy the project version floor.
- Execute this plan in an isolated worktree created from commit `f668304`; do not implement in the dirty main checkout.
- The dirty main checkout’s sample library may be read from `/Users/kk/git_project/token_parse_sys/configs/research_samples/steady_uptrend_breakout_samples.json`; do not edit, stage, or commit that source file in this plan.
- Add new focused files. Do not modify the currently dirty `stock_lobster/research/trend_breakout_scan.py`, `stock_lobster/research/__init__.py`, `workflows/jobs/daily_strategy_signal_production.py`, or existing v3/v3.1 configs.
- All outputs remain `research_only`; do not emit `stock_lobster.l5_signal_engine.StrategySignal` and do not change the routine production schedule.
- Use `qfq_asof` price inputs and preserve input path, strategy version, policy version, code commit, and as-of date in every source-of-truth JSON artifact.
- Every prior high, base high, and base low used by the signal-day decision must exclude the current bar.
- JSON is the source of truth; CSV and Markdown are review views only.
- Use TDD: failing test, observed failure, minimal implementation, passing test, commit.

## File Structure

New source files:

- `stock_lobster/research/rebreakout_sample_catalog.py`: deterministic classification of existing annotated events into core, adjacent, and negative/wait families.
- `stock_lobster/research/rebreakout_models.py`: research-only policy, state, factor, anomaly, seed, and pool schemas.
- `stock_lobster/research/rebreakout_factors.py`: fixed-window trend, consolidation, trigger, and failure calculations.
- `stock_lobster/research/rebreakout_candidate_pool.py`: cross-sectional anomaly detection and anomaly/full-market/union pool construction.
- `stock_lobster/research/rebreakout_evaluation.py`: sample recall, state conversion, pool concentration, and acceptance evidence.
- `workflows/jobs/trend_consolidation_sample_catalog_build.py`: stable sample-catalog job.
- `workflows/jobs/trend_consolidation_rebreakout_research_scan.py`: stable research scan and artifact writer.
- `workflows/jobs/trend_consolidation_rebreakout_event_backtest.py`: explicit-pool H5/H10/H20 backtest wrapper.
- `workflows/jobs/trend_consolidation_rebreakout_closed_loop.py`: scan/backtest/benchmark/evaluation orchestration.

New configs and reports:

- `configs/research_workflows/trend_consolidation_rebreakout_scan.example.json`
- `configs/research_workflows/trend_consolidation_rebreakout_closed_loop.example.json`
- `docs/research_reports/20260710-trend-consolidation-rebreakout-research.md`

New tests:

- `tests/research_tests/test_rebreakout_sample_catalog.py`
- `tests/research_tests/test_rebreakout_factors.py`
- `tests/research_tests/test_rebreakout_candidate_pool.py`
- `tests/research_tests/test_rebreakout_evaluation.py`
- `tests/workflows_tests/test_trend_consolidation_sample_catalog_build.py`
- `tests/workflows_tests/test_trend_consolidation_rebreakout_research_scan.py`
- `tests/workflows_tests/test_trend_consolidation_rebreakout_event_backtest.py`
- `tests/workflows_tests/test_trend_consolidation_rebreakout_closed_loop.py`

---

### Task 1: Build the strategy-specific sample catalog

**Files:**
- Create: `stock_lobster/research/rebreakout_sample_catalog.py`
- Create: `workflows/jobs/trend_consolidation_sample_catalog_build.py`
- Test: `tests/research_tests/test_rebreakout_sample_catalog.py`
- Test: `tests/workflows_tests/test_trend_consolidation_sample_catalog_build.py`

**Interfaces:**
- Consumes: the JSON object from `configs/research_samples/steady_uptrend_breakout_samples.json`.
- Produces: `classify_event_family(event: Mapping[str, object]) -> str` and `build_rebreakout_sample_catalog(payload: Mapping[str, object]) -> dict[str, object]`.
- Produces family values: `trend_consolidation_rebreakout`, `adjacent_family`, `negative_or_wait`, and `context_only`.

- [ ] **Step 1: Write the failing domain tests**

Create `tests/research_tests/test_rebreakout_sample_catalog.py`:

```python
from __future__ import annotations

import unittest

from stock_lobster.research.rebreakout_sample_catalog import (
    build_rebreakout_sample_catalog,
    classify_event_family,
)


class RebreakoutSampleCatalogTest(unittest.TestCase):
    def test_classifies_core_rebreakout_labels(self) -> None:
        event = {
            "event_id": "core-1",
            "trade_date": "2026-04-09",
            "timeframe": "daily",
            "event_class": "positive_attention_high_value",
            "derived_l3_candidates": ["technical_pattern.long_base_early_trend_breakout"],
        }

        self.assertEqual("trend_consolidation_rebreakout", classify_event_family(event))

    def test_keeps_early_reversal_as_adjacent(self) -> None:
        event = {
            "event_id": "adjacent-1",
            "trade_date": "2026-01-05",
            "timeframe": "daily",
            "event_class": "positive_attention_mid_value",
            "derived_l3_candidates": ["technical_pattern.early_trend_reversal_breakout"],
        }

        self.assertEqual("adjacent_family", classify_event_family(event))

    def test_builds_catalog_with_counts_and_provenance(self) -> None:
        payload = {
            "sample_library_id": "library-v1",
            "schema_version": 1,
            "samples": [
                {
                    "sample_id": "sample-1",
                    "asset_id": "000001.SZ",
                    "asset_name": "测试股份",
                    "events": [
                        {
                            "event_id": "core-1",
                            "trade_date": "2026-04-09",
                            "timeframe": "daily",
                            "event_class": "positive_attention_high_value",
                            "derived_l3_candidates": ["technical_pattern.uptrend_consolidation_breakout"],
                        },
                        {
                            "event_id": "negative-1",
                            "trade_date": "2026-04-10",
                            "timeframe": "daily",
                            "event_class": "hard_negative_recall",
                            "derived_l3_candidates": [],
                        },
                    ],
                }
            ],
        }

        catalog = build_rebreakout_sample_catalog(payload)

        self.assertEqual("research_only", catalog["status"])
        self.assertEqual("library-v1", catalog["source_sample_library_id"])
        self.assertEqual(1, catalog["family_counts"]["trend_consolidation_rebreakout"])
        self.assertEqual(1, catalog["family_counts"]["negative_or_wait"])
        self.assertEqual("000001.SZ", catalog["events"][0]["asset_id"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the domain test and verify the import failure**

Run:

```bash
/opt/homebrew/bin/python3.12 -m unittest tests.research_tests.test_rebreakout_sample_catalog -v
```

Expected: `ERROR` with `ModuleNotFoundError: No module named 'stock_lobster.research.rebreakout_sample_catalog'`.

- [ ] **Step 3: Implement deterministic family classification**

Create `stock_lobster/research/rebreakout_sample_catalog.py` with these exact classification sets and functions:

```python
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence


CORE_LABELS = frozenset(
    {
        "technical_pattern.long_base_early_trend_breakout",
        "technical_pattern.uptrend_consolidation_breakout",
        "technical_pattern.pullback_reacceleration_breakout",
        "technical_pattern.high_level_w_base_breakout_watch",
        "technical_pattern.high_level_base_breakout",
        "technical_pattern.high_level_rest_after_breakout_continuation",
    }
)
ADJACENT_LABELS = frozenset(
    {
        "technical_pattern.early_trend_reversal_breakout",
        "technical_pattern.uptrend_continuation_breakout",
        "technical_pattern.steady_late_acceleration_breakout",
        "technical_pattern.high_level_trend_extension",
        "technical_pattern.steady_ma10_walkup_new_high_acceleration",
    }
)
NEGATIVE_CLASSES = frozenset(
    {
        "hard_negative_recall",
        "weak_or_excluded_attention",
        "borderline_negative_recall",
        "negative_after_close_recall",
    }
)


def classify_event_family(event: Mapping[str, object]) -> str:
    if str(event.get("timeframe", "")) != "daily" or not event.get("trade_date"):
        return "context_only"
    event_class = str(event.get("event_class", ""))
    if event_class in NEGATIVE_CLASSES:
        return "negative_or_wait"
    raw_labels = event.get("derived_l3_candidates", ())
    labels = {str(item) for item in raw_labels} if isinstance(raw_labels, Sequence) else set()
    if labels & CORE_LABELS:
        return "trend_consolidation_rebreakout"
    if event_class.startswith("positive") or labels & ADJACENT_LABELS:
        return "adjacent_family"
    return "negative_or_wait"


def build_rebreakout_sample_catalog(payload: Mapping[str, object]) -> dict[str, object]:
    events: list[dict[str, object]] = []
    for sample in payload.get("samples", ()):  # type: ignore[union-attr]
        if not isinstance(sample, Mapping):
            continue
        for event in sample.get("events", ()):  # type: ignore[union-attr]
            if not isinstance(event, Mapping):
                continue
            family = classify_event_family(event)
            if family == "context_only":
                continue
            events.append(
                {
                    "sample_id": str(sample.get("sample_id", "")),
                    "asset_id": str(sample.get("asset_id", "")),
                    "asset_name": str(sample.get("asset_name", "")),
                    "event_id": str(event.get("event_id", "")),
                    "trade_date": str(event.get("trade_date", "")).replace("-", ""),
                    "event_class": str(event.get("event_class", "")),
                    "value_tier": event.get("value_tier"),
                    "target_family": family,
                    "human_interpretation": str(event.get("human_interpretation", "")),
                    "derived_l3_candidates": [str(item) for item in event.get("derived_l3_candidates", ())],
                }
            )
    events.sort(key=lambda item: (str(item["trade_date"]), str(item["asset_id"]), str(item["event_id"])))
    counts = Counter(str(item["target_family"]) for item in events)
    return {
        "schema_version": 1,
        "catalog_id": "trend_consolidation_rebreakout_samples_v1",
        "status": "research_only",
        "source_sample_library_id": str(payload.get("sample_library_id", "")),
        "classification_policy_version": "candidate_v1",
        "family_counts": dict(sorted(counts.items())),
        "events": events,
    }
```

- [ ] **Step 4: Run the domain test and verify it passes**

Run the same unittest command. Expected: `Ran 3 tests` and `OK`.

- [ ] **Step 5: Write the failing workflow test**

Create `tests/workflows_tests/test_trend_consolidation_sample_catalog_build.py` with a temporary source JSON, call `main` with explicit `--source-path` and `--output-path` arguments, and assert the output contains `catalog_id`, `family_counts`, and normalized `YYYYMMDD` dates:

```python
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workflows.jobs.trend_consolidation_sample_catalog_build import main


class TrendConsolidationSampleCatalogBuildTest(unittest.TestCase):
    def test_writes_strategy_specific_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "samples.json"
            output = root / "catalog.json"
            source.write_text(json.dumps({
                "sample_library_id": "library-v1",
                "samples": [{
                    "sample_id": "s1",
                    "asset_id": "000001.SZ",
                    "events": [{
                        "event_id": "e1",
                        "trade_date": "2026-04-09",
                        "timeframe": "daily",
                        "event_class": "positive_attention_high_value",
                        "derived_l3_candidates": ["technical_pattern.long_base_early_trend_breakout"],
                    }],
                }],
            }), encoding="utf-8")

            exit_code = main(["--source-path", str(source), "--output-path", str(output)])
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        self.assertEqual("trend_consolidation_rebreakout_samples_v1", payload["catalog_id"])
        self.assertEqual("20260409", payload["events"][0]["trade_date"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 6: Implement the sample-catalog job**

Create `workflows/jobs/trend_consolidation_sample_catalog_build.py` with `--source-path` and `--output-path`, load a JSON object, call `build_rebreakout_sample_catalog`, and write it using `workflows.jobs.support.write_json_payload`. Return `0` on success and let invalid JSON or invalid object shape raise.

- [ ] **Step 7: Run both Task 1 test modules**

Run:

```bash
/opt/homebrew/bin/python3.12 -m unittest \
  tests.research_tests.test_rebreakout_sample_catalog \
  tests.workflows_tests.test_trend_consolidation_sample_catalog_build -v
```

Expected: `Ran 4 tests` and `OK`.

- [ ] **Step 8: Commit Task 1**

```bash
git add stock_lobster/research/rebreakout_sample_catalog.py \
  workflows/jobs/trend_consolidation_sample_catalog_build.py \
  tests/research_tests/test_rebreakout_sample_catalog.py \
  tests/workflows_tests/test_trend_consolidation_sample_catalog_build.py
git commit -m "feat: classify trend consolidation research samples"
```

---

### Task 2: Implement fixed-window factors and the research state machine

**Files:**
- Create: `stock_lobster/research/rebreakout_models.py`
- Create: `stock_lobster/research/rebreakout_factors.py`
- Test: `tests/research_tests/test_rebreakout_factors.py`

**Interfaces:**
- Consumes: `Sequence[KlineBar]` ordered by `trade_date` for one asset.
- Produces: `scan_rebreakout_factors(bars: Iterable[KlineBar], policy: RebreakoutPolicy) -> tuple[RebreakoutMetric, ...]`.
- Produces states: `S1_TREND`, `S2_CONSOLIDATION`, `S3_OBSERVATION`, `S4_CONFIRMED_BREAKOUT`, `SX_INVALIDATED`.

- [ ] **Step 1: Write failing tests for current-day exclusion and state transitions**

Create `tests/research_tests/test_rebreakout_factors.py`. Build 90 rising bars, 10 contracting base bars, then one near-trigger bar and one breakout bar. Assert:

```python
from __future__ import annotations

import unittest

from stock_lobster.research.rebreakout_factors import scan_rebreakout_factors
from stock_lobster.research.rebreakout_models import RebreakoutPolicy, RebreakoutState
from stock_lobster.research.trend_breakout_scan import KlineBar


class RebreakoutFactorsTest(unittest.TestCase):
    def test_excludes_current_bar_from_trigger_level(self) -> None:
        bars = _trend_base_and_breakout("000001.SZ")

        metrics = scan_rebreakout_factors(bars, RebreakoutPolicy(require_weekly_trend=False))
        latest = metrics[-1]

        self.assertEqual(RebreakoutState.S4_CONFIRMED_BREAKOUT, latest.state)
        self.assertLess(latest.trigger_level, latest.close)
        self.assertAlmostEqual(latest.close / latest.trigger_level - 1, latest.breakout_margin_pct)

    def test_marks_near_trigger_as_observation_only(self) -> None:
        bars = _trend_base_and_breakout("000001.SZ")[:-1]

        latest = scan_rebreakout_factors(
            bars,
            RebreakoutPolicy(require_weekly_trend=False),
        )[-1]

        self.assertEqual(RebreakoutState.S3_OBSERVATION, latest.state)
        self.assertLessEqual(abs(latest.distance_to_trigger_pct), 0.05)

    def test_rejects_base_that_breaks_ma30_support(self) -> None:
        bars = _trend_base_and_breakout("000001.SZ")
        broken = list(bars)
        broken[-4] = KlineBar(
            asset_id="000001.SZ",
            trade_date=broken[-4].trade_date,
            open=6.0,
            high=6.2,
            low=5.8,
            close=6.0,
            amount=80.0,
        )

        latest = scan_rebreakout_factors(
            broken,
            RebreakoutPolicy(require_weekly_trend=False),
        )[-1]

        self.assertEqual(RebreakoutState.SX_INVALIDATED, latest.state)
        self.assertIn("base_support_failed", latest.reasons)


def _trend_base_and_breakout(asset_id: str) -> list[KlineBar]:
    bars: list[KlineBar] = []
    for index in range(70):
        close = 10.0 + index * 0.05
        bars.append(KlineBar(asset_id, f"2026{index + 1:04d}", close, close + 0.15, close - 0.15, close, 140.0))
    for offset in range(20):
        close = 13.5 + offset * 0.30
        bars.append(KlineBar(asset_id, f"2026{71 + offset:04d}", close - 0.10, close + 0.30, close - 0.30, close, 200.0))
    for offset in range(10):
        close = 18.75 + (0.05 if offset % 2 else -0.05)
        bars.append(KlineBar(asset_id, f"2026{91 + offset:04d}", close, close + 0.10, close - 0.10, close, 100.0))
    trigger = max(bar.close for bar in bars[-60:])
    near_close = trigger * 0.98
    bars.append(KlineBar(asset_id, "20260101", near_close, near_close + 0.10, near_close - 0.10, near_close, 120.0))
    breakout_close = trigger * 1.01
    bars.append(KlineBar(asset_id, "20260102", trigger, breakout_close + 0.10, trigger - 0.10, breakout_close, 180.0))
    return bars


if __name__ == "__main__":
    unittest.main()
```

The helper uses an impulse average amount of `200`, a base average amount of `100`, a near-trigger close 2% below the prior high, and a breakout close 1% above it with amount `180`.

- [ ] **Step 2: Run the test and verify the module import failure**

Run:

```bash
/opt/homebrew/bin/python3.12 -m unittest tests.research_tests.test_rebreakout_factors -v
```

Expected: `ERROR` because `rebreakout_factors` and `rebreakout_models` do not exist.

- [ ] **Step 3: Create the research schemas**

Create `stock_lobster/research/rebreakout_models.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum


class RebreakoutState(StrEnum):
    S1_TREND = "S1_TREND"
    S2_CONSOLIDATION = "S2_CONSOLIDATION"
    S3_OBSERVATION = "S3_OBSERVATION"
    S4_CONFIRMED_BREAKOUT = "S4_CONFIRMED_BREAKOUT"
    SX_INVALIDATED = "SX_INVALIDATED"


@dataclass(frozen=True, slots=True)
class RebreakoutPolicy:
    version: str = "candidate_v1"
    impulse_days: int = 20
    min_base_days: int = 5
    max_base_days: int = 20
    min_prior_impulse_return: float = 0.10
    max_base_drawdown: float = 0.15
    max_base_atr_contraction_ratio: float = 0.90
    max_base_amount_contraction_ratio: float = 0.80
    min_base_ma30_support_ratio: float = 0.70
    max_observation_distance_pct: float = 0.05
    max_breakout_margin_pct: float = 0.03
    min_breakout_amount_ratio: float = 1.00
    min_close_location_value: float = 0.60
    require_weekly_trend: bool = True
    max_weekly_drawdown_26w: float = 0.55


@dataclass(frozen=True, slots=True)
class RebreakoutMetric:
    asset_id: str
    trade_date: str
    state: RebreakoutState
    close: float
    return_1d: float
    return_3d: float
    return_5d: float
    amount_ratio_20d: float
    prior_impulse_return: float
    base_days: int
    base_start_date: str
    base_end_date: str
    base_high: float
    base_low: float
    base_drawdown: float
    base_atr_contraction_ratio: float
    base_amount_contraction_ratio: float
    base_ma30_support_ratio: float
    trigger_level: float
    distance_to_trigger_pct: float
    breakout_margin_pct: float
    close_location_value: float
    weekly_asof_trade_date: str | None
    weekly_trend_pass: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def to_mapping(self) -> dict[str, object]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["reasons"] = list(self.reasons)
        return payload
```

- [ ] **Step 4: Implement the fixed-window algorithm**

Create `stock_lobster/research/rebreakout_factors.py` with these rules:

1. Group daily and weekly bars by asset and sort by date.
2. For each index with at least `60 + max_base_days + impulse_days` prior bars, evaluate every `base_days` value in the configured range using `bars[index-base_days:index]`; never include `bars[index]` in the base or trigger level.
3. Use the preceding `impulse_days` bars as the impulse window.
4. Calculate:

```python
prior_impulse_return = base[0].close / impulse[0].close - 1
base_high = max(bar.high for bar in base)
base_low = min(bar.low for bar in base)
base_drawdown = base_low / base_high - 1
base_atr_contraction_ratio = mean_true_range(base) / mean_true_range(impulse)
base_amount_contraction_ratio = mean(base.amount) / mean(impulse.amount)
trigger_level = max(base_high, max(bar.close for bar in prior_60_bars))
distance_to_trigger_pct = current.close / trigger_level - 1
breakout_margin_pct = max(distance_to_trigger_pct, 0.0)
amount_ratio_20d = current.amount / mean(previous_20_amounts)
close_location_value = (current.close - current.low) / (current.high - current.low)
```

5. For every base bar, calculate MA30 using bars available through that base date; `base_ma30_support_ratio` is the share of base closes greater than or equal to their MA30.
6. A base is valid when impulse return, drawdown, ATR contraction, amount contraction, and MA30 support all pass. Choose the valid candidate with the smallest tuple `(base_range_pct, -base_days)`; this prefers tighter and then longer bases.
7. State assignment:

```python
if no candidate has prior_impulse_return >= min_prior_impulse_return:
    state = RebreakoutState.SX_INVALIDATED
elif no valid base exists:
    state = RebreakoutState.SX_INVALIDATED
elif (
    current.close > trigger_level
    and breakout_margin_pct <= policy.max_breakout_margin_pct
    and amount_ratio_20d >= policy.min_breakout_amount_ratio
    and close_location_value >= policy.min_close_location_value
):
    state = RebreakoutState.S4_CONFIRMED_BREAKOUT
elif -policy.max_observation_distance_pct <= distance_to_trigger_pct <= 0:
    state = RebreakoutState.S3_OBSERVATION
else:
    state = RebreakoutState.S2_CONSOLIDATION
```

8. Align the latest weekly bar whose `trade_date <= current.trade_date`. Weekly trend passes when weekly close is above weekly MA20, weekly MA10 is above MA20, weekly MA20 is above its value four weeks earlier, and absolute 26-week drawdown is at most `max_weekly_drawdown_26w`. When `require_weekly_trend` is true, a missing or failed weekly context prevents S2/S3/S4 and records `weekly_trend_failed`.
9. Record explicit reasons including `prior_impulse_failed`, `base_drawdown_failed`, `base_atr_contraction_failed`, `base_amount_contraction_failed`, `base_support_failed`, `weekly_trend_failed`, `breakout_volume_failed`, `breakout_close_quality_failed`, and `breakout_overextended`.

Implement helpers `_true_range`, `_mean_true_range`, `_ma_at`, `_return_over`, `_candidate_base`, `_weekly_context_asof`, `_weekly_trend_pass`, and `scan_rebreakout_factors`. The public signature is:

```python
def scan_rebreakout_factors(
    bars: Iterable[KlineBar],
    policy: RebreakoutPolicy,
    *,
    weekly_bars: Iterable[KlineBar] = (),
) -> tuple[RebreakoutMetric, ...]:
```

Reject mixed asset ids in a single per-asset evaluation helper; the public scan groups mixed input safely.

- [ ] **Step 5: Run the factor tests and fix only formula defects**

Run the Task 2 unittest command. Expected: `Ran 3 tests` and `OK`.

- [ ] **Step 6: Add edge-case tests**

Add tests asserting:

- insufficient history yields no metric for that date;
- a flat bar produces `close_location_value == 0.5` instead of division by zero;
- a breakout 4% above trigger is `SX_INVALIDATED` with `breakout_overextended`;
- a daily S4 setup becomes `SX_INVALIDATED` with `weekly_trend_failed` when the as-of weekly MA20 is falling;
- identical input produces identical `to_mapping()` output.

Run again. Expected: `Ran 8 tests` and `OK`.

- [ ] **Step 7: Commit Task 2**

```bash
git add stock_lobster/research/rebreakout_models.py \
  stock_lobster/research/rebreakout_factors.py \
  tests/research_tests/test_rebreakout_factors.py
git commit -m "feat: add trend consolidation research state machine"
```

---

### Task 3: Add anomaly seeds and replayable dual candidate pools

**Files:**
- Create: `stock_lobster/research/rebreakout_candidate_pool.py`
- Test: `tests/research_tests/test_rebreakout_candidate_pool.py`

**Interfaces:**
- Consumes: one date’s `RebreakoutMetric` records plus `industry_by_asset: Mapping[str, str]`.
- Produces: `build_candidate_pools(metrics: Iterable[RebreakoutMetric], industry_by_asset: Mapping[str, str], policy: AnomalyPolicy) -> CandidatePoolSnapshot`.
- Produces pool keys: `anomaly_seed_pool`, `full_market_trend_pool`, and `trend_consolidation_union_pool`.

- [ ] **Step 1: Write failing dual-pool tests**

Create tests with three synthetic metrics:

- `000001.SZ`: S1, top-decile 5-day return, high amount ratio; must enter anomaly and union.
- `000002.SZ`: S3 quiet base, ordinary return and volume; must enter full-market fallback and union, but not anomaly.
- `000003.SZ`: invalidated; must enter no pool.

Assert a stock present in both source pools has sorted source tags `("anomaly_seed_v1", "full_market_trend_fallback_v1")` in the union record.

- [ ] **Step 2: Run the test and verify the import failure**

Run:

```bash
/opt/homebrew/bin/python3.12 -m unittest tests.research_tests.test_rebreakout_candidate_pool -v
```

Expected: `ERROR` because `rebreakout_candidate_pool` does not exist.

- [ ] **Step 3: Extend the research schemas**

Add to `rebreakout_models.py`:

```python
@dataclass(frozen=True, slots=True)
class AnomalyPolicy:
    version: str = "candidate_v1"
    relative_strength_percentile: float = 0.90
    industry_strength_percentile: float = 0.70
    min_industry_excess_return_5d: float = 0.03
    min_price_volume_return_1d: float = 0.01
    min_price_volume_amount_ratio: float = 1.50
    max_wakeup_atr_ratio: float = 0.80
    min_wakeup_amount_ratio: float = 1.20


@dataclass(frozen=True, slots=True)
class CandidateSeed:
    asset_id: str
    trade_date: str
    source_tags: tuple[str, ...]
    anomaly_types: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_mapping(self) -> dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "trade_date": self.trade_date,
            "source_tags": list(self.source_tags),
            "anomaly_types": list(self.anomaly_types),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class CandidatePoolSnapshot:
    asof_date: str
    policy_version: str
    anomaly_seed_pool: tuple[CandidateSeed, ...]
    full_market_trend_pool: tuple[CandidateSeed, ...]
    trend_consolidation_union_pool: tuple[CandidateSeed, ...]

    def to_mapping(self) -> dict[str, object]:
        return {
            "asof_date": self.asof_date,
            "policy_version": self.policy_version,
            "pools": {
                "anomaly_seed_pool": [item.to_mapping() for item in self.anomaly_seed_pool],
                "full_market_trend_pool": [item.to_mapping() for item in self.full_market_trend_pool],
                "trend_consolidation_union_pool": [
                    item.to_mapping() for item in self.trend_consolidation_union_pool
                ],
            },
        }
```

- [ ] **Step 4: Implement cross-sectional anomaly detection**

Create `rebreakout_candidate_pool.py` with:

- a deterministic nearest-rank percentile helper;
- market 5-day return cutoff;
- industry median 5-day return and industry top-30% cutoff;
- anomaly tags:
  - `price_relative_strength_acceleration` when return 5d is above market 90th percentile;
  - `price_volume_expansion` when return 1d and amount ratio pass;
  - `low_volatility_wakeup` when base ATR contraction and amount ratio pass;
  - `industry_context_acceleration` when industry median is top 30% and stock 5d return exceeds industry median by at least 3 percentage points;
- fallback membership for states S1, S2, S3, and S4;
- union merge by `(asset_id, trade_date)`, preserving and sorting all source/anomaly/reason values.

The function must reject mixed dates with `ValueError("metrics must share one trade_date")` so each pool snapshot remains replayable.

- [ ] **Step 5: Run and extend tests**

Run the Task 3 unittest. Then add tests for:

- stable percentile results with ties;
- mixed dates fail loudly;
- missing industry uses only market/price-volume anomaly logic;
- union output is sorted by `(trade_date, asset_id)`.

Expected final output: `Ran 5 tests` and `OK`.

- [ ] **Step 6: Commit Task 3**

```bash
git add stock_lobster/research/rebreakout_models.py \
  stock_lobster/research/rebreakout_candidate_pool.py \
  tests/research_tests/test_rebreakout_candidate_pool.py
git commit -m "feat: add anomaly and fallback research pools"
```

---

### Task 4: Build the research scan job and deterministic artifacts

**Files:**
- Create: `configs/research_workflows/trend_consolidation_rebreakout_scan.example.json`
- Create: `workflows/jobs/trend_consolidation_rebreakout_research_scan.py`
- Test: `tests/workflows_tests/test_trend_consolidation_rebreakout_research_scan.py`

**Interfaces:**
- Consumes CLI arguments `--config-path`, `--kline-tsv-path`, `--weekly-kline-tsv-path`, optional `--stock-context-tsv-path`, `--output-dir`, and optional `--start-date`/`--end-date`.
- Produces six JSON files named in the approved design and one `report.md`.
- `confirmed_breakout_candidates.json` must declare `pool_semantics=research_only_confirmed_breakout_not_l5_strategy_signal`.

- [ ] **Step 1: Write the failing workflow test**

The test must create two assets: one anomalous breakout and one quiet S3 base. Run `main` and assert:

- `candidate_pool_snapshot.json` contains all three pool keys;
- `state_snapshot.json` contains S3 and S4 states;
- `observation_candidates.json` contains only S3;
- `confirmed_breakout_candidates.json` contains only S4 and the research-only semantics marker;
- `scan_summary.json` includes input paths, policy versions, state counts, and pool counts;
- `report.md` exists.

The JSON artifact shapes are fixed:

```text
candidate_pool_snapshot.json -> {"snapshots": [CandidatePoolSnapshot.to_mapping(), ...]}
state_snapshot.json -> {"states": [RebreakoutMetric.to_mapping(), ...]}
observation_candidates.json -> {"items": [S3 metric mappings]}
confirmed_breakout_candidates.json -> {"items": [S4 metric mappings], "pool_semantics": "research_only_confirmed_breakout_not_l5_strategy_signal"}
rejected_candidates.json -> {"items": [SX metric mappings]}
scan_summary.json -> counts, policy, provenance, paths, status
```

- [ ] **Step 2: Run the workflow test and verify the import failure**

Run:

```bash
/opt/homebrew/bin/python3.12 -m unittest \
  tests.workflows_tests.test_trend_consolidation_rebreakout_research_scan -v
```

Expected: `ERROR` because the job module does not exist.

- [ ] **Step 3: Add the scan config**

Create the JSON config with exact keys:

```json
{
  "schema_version": 1,
  "strategy_id": "strategy.trend_consolidation_rebreakout",
  "strategy_version": "candidate_v1",
  "status": "research_only",
  "price_basis": "qfq_asof",
  "rebreakout_policy": {
    "version": "candidate_v1",
    "impulse_days": 20,
    "min_base_days": 5,
    "max_base_days": 20,
    "min_prior_impulse_return": 0.1,
    "max_base_drawdown": 0.15,
    "max_base_atr_contraction_ratio": 0.9,
    "max_base_amount_contraction_ratio": 0.8,
    "min_base_ma30_support_ratio": 0.7,
    "max_observation_distance_pct": 0.05,
    "max_breakout_margin_pct": 0.03,
    "min_breakout_amount_ratio": 1.0,
    "min_close_location_value": 0.6,
    "require_weekly_trend": true,
    "max_weekly_drawdown_26w": 0.55
  },
  "anomaly_policy": {
    "version": "candidate_v1",
    "relative_strength_percentile": 0.9,
    "industry_strength_percentile": 0.7,
    "min_industry_excess_return_5d": 0.03,
    "min_price_volume_return_1d": 0.01,
    "min_price_volume_amount_ratio": 1.5,
    "max_wakeup_atr_ratio": 0.8,
    "min_wakeup_amount_ratio": 1.2
  }
}
```

- [ ] **Step 4: Implement the job**

Implement this exact orchestration order:

1. Load and validate the config object.
2. Read daily and weekly bars with `read_kline_tsv` and contexts with `read_stock_signal_context_tsv`.
3. Group context industry by `(asset_id, trade_date)`.
4. Run `scan_rebreakout_factors` once with the daily and weekly inputs.
5. Group metrics by trade date and build one `CandidatePoolSnapshot` per date.
6. Write:
   - candidate pool snapshots;
   - all state metrics;
   - S3 observations;
   - S4 confirmed research candidates;
   - SX rejected candidates;
   - aggregate counts and provenance.
7. Render a concise Markdown table with date, pool counts, S3 count, S4 count, and SX count.

Every output object must contain `schema_version`, `strategy_id`, `strategy_version`, `status`, `price_basis`, `policy`, `input_paths`, and `generated_at`. Use `utc_now_iso()` only for metadata; it must not affect selection contents.

- [ ] **Step 5: Run the workflow test**

Expected: `Ran 1 test` and `OK`.

- [ ] **Step 6: Add failure-path tests**

Add tests that assert nonzero exit and a written `scan_summary.json` with `status=failed` for:

- missing config file;
- malformed config object;
- missing explicit kline path;
- no metrics in the requested date range.

Expected final output: `Ran 5 tests` and `OK`.

- [ ] **Step 7: Commit Task 4**

```bash
git add configs/research_workflows/trend_consolidation_rebreakout_scan.example.json \
  workflows/jobs/trend_consolidation_rebreakout_research_scan.py \
  tests/workflows_tests/test_trend_consolidation_rebreakout_research_scan.py
git commit -m "feat: add trend consolidation research scan"
```

---

### Task 5: Add explicit-pool event backtests and benchmarks

**Files:**
- Create: `workflows/jobs/trend_consolidation_rebreakout_event_backtest.py`
- Test: `tests/workflows_tests/test_trend_consolidation_rebreakout_event_backtest.py`

**Interfaces:**
- Consumes: `--scan-output-dir`, `--candidate-pool-key`, `--kline-tsv-path`, `--holding-horizons`, and `--output-path`.
- Valid pool keys: `anomaly_seed_pool`, `full_market_trend_pool`, `trend_consolidation_union_pool`, `observation_candidates`, and `confirmed_breakout_candidates`.
- Produces one JSON with event reports plus the same-pool equal-weight benchmark reports.

- [ ] **Step 1: Write the failing explicit-pool test**

Create a temporary scan directory containing a candidate-pool snapshot and confirmed candidates. Assert:

- requesting `confirmed_breakout_candidates` backtests exactly those events;
- H5 and H10 reports use T+1 open and horizon close;
- benchmark events come from `trend_consolidation_union_pool` when `--benchmark-pool-key trend_consolidation_union_pool` is passed;
- a missing explicit key raises `ValueError` and never falls back.

- [ ] **Step 2: Run the test and verify the import failure**

Run:

```bash
/opt/homebrew/bin/python3.12 -m unittest \
  tests.workflows_tests.test_trend_consolidation_rebreakout_event_backtest -v
```

Expected: `ERROR` because the job module does not exist.

- [ ] **Step 3: Implement the backtest wrapper**

Use existing L6 interfaces exactly:

```python
events = tuple(
    BacktestEvent(
        asset_id=str(item["asset_id"]),
        signal_date=str(item["trade_date"]),
        event_id=f"{item['asset_id']}.{item['trade_date']}",
    )
    for item in selected_items
)
policy = EventBacktestPolicy(
    strategy_id="strategy.trend_consolidation_rebreakout",
    strategy_version="candidate_v1",
    holding_horizon=horizon,
    entry_offset=1,
    benchmark="CANDIDATE_POOL_EQUAL_WEIGHT",
)
report = run_event_backtest(bars=bars, events=events, policy=policy)
benchmark = run_candidate_pool_equal_weight_benchmark(
    bars=bars,
    candidate_events=benchmark_events,
    policy=policy,
    benchmark_id=f"{benchmark_pool_key}_equal_weight_v1",
)
```

Write selected pool key, benchmark pool key, source paths, event count, skipped events, and reports for every requested horizon.

Pool loading is explicit:

- for anomaly/fallback/union keys, flatten `candidate_pool_snapshot.json["snapshots"][*]["pools"][key]`;
- for `observation_candidates`, read `observation_candidates.json["items"]`;
- for `confirmed_breakout_candidates`, read `confirmed_breakout_candidates.json["items"]`;
- if any requested object or key is absent, raise `ValueError` naming the missing key.

- [ ] **Step 4: Run and extend tests**

Add tests for horizons `5,10,20`, empty explicit pool, and insufficient future bars. Expected final output: `Ran 4 tests` and `OK`.

- [ ] **Step 5: Commit Task 5**

```bash
git add workflows/jobs/trend_consolidation_rebreakout_event_backtest.py \
  tests/workflows_tests/test_trend_consolidation_rebreakout_event_backtest.py
git commit -m "feat: backtest explicit rebreakout research pools"
```

---

### Task 6: Build closed-loop evaluation and acceptance evidence

**Files:**
- Create: `stock_lobster/research/rebreakout_evaluation.py`
- Create: `configs/research_workflows/trend_consolidation_rebreakout_closed_loop.example.json`
- Create: `workflows/jobs/trend_consolidation_rebreakout_closed_loop.py`
- Test: `tests/research_tests/test_rebreakout_evaluation.py`
- Test: `tests/workflows_tests/test_trend_consolidation_rebreakout_closed_loop.py`

**Interfaces:**
- Consumes: sample catalog, scan artifacts, and explicit-pool backtest artifacts.
- Produces: `evaluate_research_evidence(sample_catalog: Mapping[str, object], scan_payloads: Mapping[str, object], backtest_payload: Mapping[str, object]) -> dict[str, object]` and a closed-loop summary JSON/Markdown.
- Gate remains `research_only`; output may recommend `ready_for_promotion_plan` but may not change lifecycle status.

- [ ] **Step 1: Write failing evaluation tests**

Use synthetic sample events and pools to assert:

- core recall is matched by `(asset_id, trade_date)`;
- anomaly recall loss equals full-market recall minus anomaly recall in percentage points;
- pool concentration equals `1 - anomaly_count/full_market_count`;
- state conversion counts S1/S2/S3/S4/SX;
- acceptance fails when core recall is below 70%, H5 sample size below 50, median return is not positive, or excess versus candidate benchmark is not positive;
- acceptance never returns `active_production` or `test_tracking`.

- [ ] **Step 2: Run the test and verify the import failure**

Run:

```bash
/opt/homebrew/bin/python3.12 -m unittest tests.research_tests.test_rebreakout_evaluation -v
```

Expected: `ERROR` because `rebreakout_evaluation` does not exist.

- [ ] **Step 3: Implement evidence calculations**

Create `stock_lobster/research/rebreakout_evaluation.py` with these concrete pure functions and payload contracts:

```python
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence


def _mapping_items(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def event_keys(items: Iterable[Mapping[str, object]]) -> set[tuple[str, str]]:
    return {
        (str(item.get("asset_id", "")), str(item.get("trade_date", "")).replace("-", ""))
        for item in items
        if item.get("asset_id") and item.get("trade_date")
    }


def sample_recall(
    sample_events: Iterable[Mapping[str, object]],
    candidate_items: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    sample_keys = event_keys(sample_events)
    matched = sorted(sample_keys & event_keys(candidate_items))
    sample_count = len(sample_keys)
    return {
        "sample_count": sample_count,
        "matched_count": len(matched),
        "recall": len(matched) / sample_count if sample_count else 0.0,
        "matched_event_keys": [list(item) for item in matched],
        "missed_event_keys": [list(item) for item in sorted(sample_keys - set(matched))],
    }


def state_conversion(state_items: Iterable[Mapping[str, object]]) -> dict[str, object]:
    counts = Counter(str(item.get("state", "")) for item in state_items)
    ordered = {
        state: counts.get(state, 0)
        for state in (
            "S1_TREND",
            "S2_CONSOLIDATION",
            "S3_OBSERVATION",
            "S4_CONFIRMED_BREAKOUT",
            "SX_INVALIDATED",
        )
    }
    return {"state_counts": ordered, "total": sum(ordered.values())}


def pool_concentration(pool_snapshot: Mapping[str, object]) -> dict[str, float]:
    pools = pool_snapshot.get("pools", {})
    if not isinstance(pools, Mapping):
        raise ValueError("pool snapshot pools must be an object")
    anomaly_count = len(_mapping_items(pools.get("anomaly_seed_pool")))
    fallback_count = len(_mapping_items(pools.get("full_market_trend_pool")))
    union_count = len(_mapping_items(pools.get("trend_consolidation_union_pool")))
    return {
        "anomaly_count": float(anomaly_count),
        "full_market_count": float(fallback_count),
        "union_count": float(union_count),
        "anomaly_vs_full_market_reduction": (
            1.0 - anomaly_count / fallback_count if fallback_count else 0.0
        ),
    }


def _h5_report(backtest_payload: Mapping[str, object]) -> tuple[Mapping[str, object], Mapping[str, object]]:
    reports = _mapping_items(backtest_payload.get("reports"))
    for report in reports:
        if int(report.get("holding_horizon", 0)) == 5:
            result = report.get("result", {})
            benchmark = report.get("benchmark", {})
            if isinstance(result, Mapping) and isinstance(benchmark, Mapping):
                return result, benchmark
    raise ValueError("H5 report is required")


def evaluate_research_evidence(
    sample_catalog: Mapping[str, object],
    scan_payloads: Mapping[str, object],
    backtest_payload: Mapping[str, object],
) -> dict[str, object]:
    sample_events = _mapping_items(sample_catalog.get("events"))
    core_events = tuple(
        item
        for item in sample_events
        if str(item.get("target_family", "")) == "trend_consolidation_rebreakout"
    )
    pools = scan_payloads.get("pools", {})
    if not isinstance(pools, Mapping):
        raise ValueError("scan payload pools must be an object")
    anomaly_items = _mapping_items(pools.get("anomaly_seed_pool"))
    fallback_items = _mapping_items(pools.get("full_market_trend_pool"))
    confirmed_items = _mapping_items(scan_payloads.get("confirmed_breakout_candidates"))
    core_result = sample_recall(core_events, confirmed_items)
    anomaly_result = sample_recall(core_events, anomaly_items)
    fallback_result = sample_recall(core_events, fallback_items)
    anomaly_recall_loss = max(
        float(fallback_result["recall"]) - float(anomaly_result["recall"]),
        0.0,
    )

    h5_result, h5_benchmark = _h5_report(backtest_payload)
    return_metrics = h5_result.get("return_metrics", {})
    benchmark_metrics = h5_benchmark.get("return_metrics", {})
    if not isinstance(return_metrics, Mapping) or not isinstance(benchmark_metrics, Mapping):
        raise ValueError("H5 return metrics are required")
    h5_sample_size = int(h5_result.get("sample_size", 0))
    h5_avg_return = float(return_metrics.get("avg_return", 0.0))
    h5_median_return = float(return_metrics.get("median_return", 0.0))
    h5_win_rate = float(h5_result.get("win_rate", 0.0))
    h5_benchmark_return = float(benchmark_metrics.get("avg_signal_date_return", 0.0))
    h5_excess = h5_avg_return - h5_benchmark_return
    core_recall = float(core_result["recall"])

    gates = {
        "core_recall_ge_70pct": core_recall >= 0.70,
        "anomaly_recall_loss_le_10pp": anomaly_recall_loss <= 0.10,
        "h5_sample_size_ge_50": h5_sample_size >= 50,
        "h5_avg_return_positive": h5_avg_return > 0,
        "h5_median_return_positive": h5_median_return > 0,
        "h5_win_rate_ge_55pct": h5_win_rate >= 0.55,
        "h5_excess_vs_candidate_pool_positive": h5_excess > 0,
    }
    recommendation = "ready_for_promotion_plan" if all(gates.values()) else "continue_research"
    return {
        "status": "research_only",
        "recommendation": recommendation,
        "gates": gates,
        "failed_gates": [name for name, passed in gates.items() if not passed],
        "sample_recall": {
            "confirmed_breakout": core_result,
            "anomaly_seed_pool": anomaly_result,
            "full_market_trend_pool": fallback_result,
            "anomaly_recall_loss": anomaly_recall_loss,
        },
        "state_conversion": state_conversion(_mapping_items(scan_payloads.get("states"))),
        "h5": {
            "sample_size": h5_sample_size,
            "avg_return": h5_avg_return,
            "median_return": h5_median_return,
            "win_rate": h5_win_rate,
            "candidate_pool_return": h5_benchmark_return,
            "excess_vs_candidate_pool": h5_excess,
        },
    }
```

The caller separately applies `pool_concentration` to each dated pool snapshot and includes the weighted aggregate in the closed-loop output.

- [ ] **Step 4: Run the evaluation tests**

Expected: all evaluation tests pass.

- [ ] **Step 5: Write and test the closed-loop job**

Create `configs/research_workflows/trend_consolidation_rebreakout_closed_loop.example.json`:

```json
{
  "schema_version": 1,
  "strategy_id": "strategy.trend_consolidation_rebreakout",
  "strategy_version": "candidate_v1",
  "status": "research_only",
  "holding_horizons": [5, 10, 20],
  "primary_holding_horizon": 5,
  "candidate_pool_keys": [
    "anomaly_seed_pool",
    "full_market_trend_pool",
    "trend_consolidation_union_pool",
    "observation_candidates",
    "confirmed_breakout_candidates"
  ],
  "benchmark_pool_key": "trend_consolidation_union_pool",
  "entry_rule": "T+1 open",
  "exit_rule": "holding horizon close"
}
```

The job must:

1. load the already-built sample catalog;
2. load and normalize the six scan JSON artifacts from `--scan-output-dir`;
3. invoke explicit-pool backtests for anomaly, fallback, union, observations, and confirmed candidates;
4. pass the confirmed-candidate backtest plus normalized pools/states to `evaluate_research_evidence`;
5. calculate dated pool concentration with `pool_concentration`;
6. write `closed_loop_summary.json` and `closed_loop_report.md`.

The workflow test must patch only file inputs, not domain results, and assert all expected child artifact paths are present and exist.

- [ ] **Step 6: Run Task 6 tests**

Run:

```bash
/opt/homebrew/bin/python3.12 -m unittest \
  tests.research_tests.test_rebreakout_evaluation \
  tests.workflows_tests.test_trend_consolidation_rebreakout_closed_loop -v
```

Expected: all tests pass with `OK`.

- [ ] **Step 7: Commit Task 6**

```bash
git add stock_lobster/research/rebreakout_evaluation.py \
  configs/research_workflows/trend_consolidation_rebreakout_closed_loop.example.json \
  workflows/jobs/trend_consolidation_rebreakout_closed_loop.py \
  tests/research_tests/test_rebreakout_evaluation.py \
  tests/workflows_tests/test_trend_consolidation_rebreakout_closed_loop.py
git commit -m "feat: close the rebreakout research loop"
```

---

### Task 7: Run the real research window and publish the evidence report

**Files:**
- Create: `docs/research_reports/20260710-trend-consolidation-rebreakout-research.md`
- Runtime output: `runtime/strategy_backtests/trend_consolidation_rebreakout_research_v1/`

**Interfaces:**
- Consumes the dirty main checkout’s latest annotated sample library read-only.
- Consumes the existing full-range qfq research inputs read-only.
- Produces the first evidence package and a decision on whether a second formal-promotion plan is justified.

- [ ] **Step 1: Run all new tests before the real data run**

```bash
/opt/homebrew/bin/python3.12 -m unittest \
  tests.research_tests.test_rebreakout_sample_catalog \
  tests.research_tests.test_rebreakout_factors \
  tests.research_tests.test_rebreakout_candidate_pool \
  tests.research_tests.test_rebreakout_evaluation \
  tests.workflows_tests.test_trend_consolidation_sample_catalog_build \
  tests.workflows_tests.test_trend_consolidation_rebreakout_research_scan \
  tests.workflows_tests.test_trend_consolidation_rebreakout_event_backtest \
  tests.workflows_tests.test_trend_consolidation_rebreakout_closed_loop -v
```

Expected: all new tests pass and the process exits `0`.

- [ ] **Step 2: Run architecture and adjacent regression tests**

```bash
/opt/homebrew/bin/python3.12 -m unittest \
  tests.test_import_boundaries \
  tests.research_tests.test_trend_breakout_scan \
  tests.l6_backtest_engine_tests.test_event_backtest \
  tests.l6_backtest_engine_tests.test_candidate_pool_benchmark -v
```

Expected: all tests pass and the process exits `0`.

- [ ] **Step 3: Build the real strategy-specific sample catalog**

```bash
/opt/homebrew/bin/python3.12 workflows/jobs/trend_consolidation_sample_catalog_build.py \
  --source-path /Users/kk/git_project/token_parse_sys/configs/research_samples/steady_uptrend_breakout_samples.json \
  --output-path runtime/strategy_backtests/trend_consolidation_rebreakout_research_v1/sample_catalog.json
```

Expected: output status `research_only`, nonzero core sample count, and no modification to the source library.

- [ ] **Step 4: Run the full research scan**

```bash
/opt/homebrew/bin/python3.12 workflows/jobs/trend_consolidation_rebreakout_research_scan.py \
  --config-path configs/research_workflows/trend_consolidation_rebreakout_scan.example.json \
  --kline-tsv-path /Users/kk/git_project/token_parse_sys/runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/input/kline.tsv \
  --weekly-kline-tsv-path /Users/kk/git_project/token_parse_sys/runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/input/weekly_kline.tsv \
  --stock-context-tsv-path /Users/kk/git_project/token_parse_sys/runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/input/stock_context.tsv \
  --output-dir runtime/strategy_backtests/trend_consolidation_rebreakout_research_v1/scan
```

Expected: all seven scan artifacts exist, state counts are nonzero, and the summary status is `success`.

- [ ] **Step 5: Run the closed-loop evaluation**

```bash
/opt/homebrew/bin/python3.12 workflows/jobs/trend_consolidation_rebreakout_closed_loop.py \
  --config-path configs/research_workflows/trend_consolidation_rebreakout_closed_loop.example.json \
  --sample-catalog-path runtime/strategy_backtests/trend_consolidation_rebreakout_research_v1/sample_catalog.json \
  --scan-output-dir runtime/strategy_backtests/trend_consolidation_rebreakout_research_v1/scan \
  --kline-tsv-path /Users/kk/git_project/token_parse_sys/runtime/strategy_backtests/sl_eval_steady_uptrend_20250102_20260707/input/kline.tsv \
  --output-dir runtime/strategy_backtests/trend_consolidation_rebreakout_research_v1/results
```

Expected: `closed_loop_summary.json` and `closed_loop_report.md` exist and state either `continue_research` or `ready_for_promotion_plan`; neither output may state `test_tracking` or `active_production`.

- [ ] **Step 6: Write the durable research report**

Create `docs/research_reports/20260710-trend-consolidation-rebreakout-research.md` from the JSON evidence. It must contain:

- input coverage and provenance;
- core/adjacent/negative sample counts;
- anomaly/fallback/union pool counts and concentration;
- sample recall by pool;
- S1→S2→S3→S4/SX conversions;
- H5/H10/H20 results and candidate-pool excess;
- false positives and false negatives with explicit reasons;
- gate table;
- one decision: continue research or write the formal L2-L5 promotion plan.

Do not copy runtime JSON rows into the report; summarize measured aggregates and link repository-relative artifact paths.

- [ ] **Step 7: Run final verification**

```bash
git diff --check
/opt/homebrew/bin/python3.12 -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: `git diff --check` emits no errors; the complete repository test suite exits `0`.

- [ ] **Step 8: Commit the report and any final deterministic fixes**

```bash
git add docs/research_reports/20260710-trend-consolidation-rebreakout-research.md
git commit -m "docs: report trend consolidation research evidence"
```

Do not commit `runtime/` outputs unless repository policy changes explicitly.

## Spec Coverage and Deferred Promotion

- Design sections 2-4 (goal, state machine, dual pools): Tasks 1-4.
- Design section 5 research factor口径: Tasks 2-4.
- Design section 9 sample, pool, H5/H10/H20, and gate evidence: Tasks 1, 5, 6, and 7.
- Design sections 10-12 provenance, missing-key failure, deterministic artifacts, and tests: Tasks 2-7.
- Formal design sections 5-8 for approved L1/L2/L3/L4/L5 contracts are intentionally deferred until Task 7 produces `ready_for_promotion_plan`; promoting them before evidence would violate the Research layer standard.
- The `stop_loss_pct=-0.10` trade-management diagnostic is deferred to the formal-promotion plan because commit `f668304` does not contain the current dirty checkout’s uncommitted trade-management module. Task 7 evaluates the unmanaged selection baseline so risk management cannot hide a selection failure.
- The weak-market Top2 versus normal-market Top5 ranking rule is deferred until the research scan produces a stable ranking feature set; this plan records market/context inputs and pool membership but does not claim an approved L5 ranking model.

## Plan Completion Gate

This plan is complete only when:

- all Task 1-7 commits exist;
- all new and repository tests pass;
- the real-data evidence report exists;
- the recommendation is evidence-derived;
- the routine production strategy remains unchanged;
- no formal L2/L3/L4/L5 promotion has occurred.

If the recommendation is `ready_for_promotion_plan`, write a second plan covering L1 feature contracts, L2 primitives, L3 labels, L4 CandidatePoolPolicy/StagePipeline, L5 ObservationCandidate/StrategySignal generation, L6 promotion evidence, and a separate `test_tracking` job. If the recommendation is `continue_research`, use the failed gates and false-negative reasons to define the next research iteration instead.
