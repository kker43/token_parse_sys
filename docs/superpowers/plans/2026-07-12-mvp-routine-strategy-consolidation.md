# MVP Routine Strategy Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the approved steady-uptrend MVP the only routine stock-selection strategy while preserving legacy strategy chains, factors, sample replay, and research evidence without allowing them to produce routine selections.

**Architecture:** Keep the MVP in `test_tracking`, not `active_production`. Treat strategy configs and policies as the replaceable business selection layer, while preserving routine jobs, input contracts, replay, factors, audit output, and reporting as the supported technical system. Introduce one business-strategy registry, archive only legacy business configurations, and keep routine execution on the manifest-validated MVP scan path. Preserve all divergent Git work before consolidation.

**Tech Stack:** Python 3.12, unittest, JSON strategy/config artifacts, deterministic TSV scan jobs, Git worktrees.

## Global Constraints

- Stock Lobster consumes factual data and must not become the authoritative factual-data producer.
- Only one strategy may have `routine_selection_enabled=true`.
- Legacy strategies remain replayable but may not be referenced by a routine selection schedule.
- Technical workflow capability is not retired when a legacy business strategy binding is disabled.
- `test_tracking` outputs are observation candidates, not formal L5 production signals.
- Existing user changes and unpushed research branches must be preserved before cleanup.

---

### Task 1: Preserve Divergent Work

**Files:**
- Preserve: main worktree tracked and untracked research files except local log output.
- Preserve: `codex/trend-consolidation-research` branch.

**Interfaces:**
- Produces: pushed preservation branches that make later cleanup non-destructive.

- [ ] Create `codex/main-wip-preservation-20260712` from the dirty main worktree.
- [ ] Stage every current main change except `longbridge.2026-07-11.log`.
- [ ] Run `/opt/homebrew/bin/python3.12 -m unittest discover -s tests -p 'test_*.py'` and commit the preservation snapshot.
- [ ] Push the preservation branch.
- [ ] Push `codex/trend-consolidation-research` before removing or parking its worktree.

### Task 2: Establish One Strategy Truth Source

**Files:**
- Create: `configs/strategies/strategy_registry.example.json`
- Rename: `configs/strategies/steady_uptrend_s1_s5_mvp_candidate_v1.example.json` to `configs/strategies/steady_uptrend_mvp.example.json`
- Move: legacy strategy JSON files to `configs/strategies/archive/steady_uptrend/`
- Modify: `workflows/jobs/sample_strategy_replay.py`
- Create: `tests/research_tests/test_strategy_registry.py`

**Interfaces:**
- Produces: exactly one routine strategy entry with stable id `strategy.steady_uptrend_mvp`, version `v1`, lifecycle `test_tracking`, and `routine_selection_enabled=true`.

- [ ] Write a failing registry test requiring exactly one enabled routine strategy and requiring every legacy strategy to be disabled.
- [ ] Run the registry test and confirm it fails because no registry exists.
- [ ] Create the registry and canonical MVP config; archive the seven legacy configs.
- [ ] Update replay paths so archived strategies remain available for historical comparison.
- [ ] Run the registry and replay tests and confirm they pass.

### Task 3: Align the MVP Scanner and Routine Schedule

**Files:**
- Modify: `workflows/jobs/steady_uptrend_s1_s5_mvp_scan.py`
- Modify: `tests/workflows_tests/test_steady_uptrend_s1_s5_mvp_scan.py`
- Create: `configs/schedules/daily_steady_uptrend_mvp_tracking.example.json`
- Modify: `configs/schedules/daily_strategy_signal_production.example.json`

**Interfaces:**
- Consumes: the canonical MVP strategy config and manifest-validated read-only input artifacts.
- Produces: deterministic `test_tracking` observation candidates; rejects `active_production` until an L5 migration is approved.

- [ ] Write failing tests that accept `research_only` and `test_tracking` but reject `active_production`.
- [ ] Run the targeted scanner tests and verify the new `test_tracking` case fails.
- [ ] Update lifecycle validation and output semantics without changing S1-S5 policy logic.
- [ ] Add a dedicated MVP tracking binding and disable only the old pre-breakout business binding; retain the routine workflow capability and runbook.
- [ ] Run scanner and schedule contract tests.

### Task 4: Synchronize Documentation and Remove Safe Duplication

**Files:**
- Modify: `PLANS.md`
- Modify: `docs/research/steady_uptrend_s1_s5_mvp.md`
- Create: `docs/research/legacy-steady-uptrend-strategies.md`
- Modify: `configs/research_samples/steady_uptrend_breakout_samples.json`
- Modify: `.gitignore`
- Delete: four byte-identical duplicate sample images after reference replacement.

**Interfaces:**
- Produces: one documented current routine strategy, one legacy strategy map, and no duplicate sample evidence references.

- [ ] Update MVP documentation to the final S5 conditions and the 25-stock Friday replay.
- [ ] Replace stale `PLANS.md` scaffold status with the current integration and lifecycle state.
- [ ] Document which legacy strategies preserve replay/factor value and explicitly prohibit routine selection.
- [ ] Point duplicate image references to one canonical file and delete only byte-identical copies.
- [ ] Ignore `longbridge*.log`.
- [ ] Validate all JSON files and run `git diff --check`.

### Task 5: Verify, Publish, and Deploy the Consolidated Baseline

**Files:**
- Deploy: canonical strategy, registry, schedule, scanner, and documentation to `/home/ubuntu/token_parse_sys` test-tracking checkout.
- Archive: remote experimental result variants under an `archive/experiments/` directory while retaining the final `-5%` result as current evidence.

**Interfaces:**
- Produces: a pushed Git baseline and a remote test-tracking layout with one unambiguous current strategy artifact.

- [ ] Run `/opt/homebrew/bin/python3.12 -m unittest discover -s tests -p 'test_*.py'`.
- [ ] Run `find configs -type f -name '*.json' -exec jq empty {} +` and `git diff --check`.
- [ ] Confirm the registry has exactly one routine selection strategy.
- [ ] Commit and push the consolidation branch.
- [ ] Deploy the exact commit to the remote test-tracking worktree.
- [ ] Re-run the 2026-07-10 deterministic scan and compare its hash with the final evidence artifact.
