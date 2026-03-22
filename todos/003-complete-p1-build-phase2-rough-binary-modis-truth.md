---
status: complete
priority: p1
issue_id: "003"
tags: [phase2, comparison, gee, modis]
dependencies: []
---

# Build Phase 2 Rough Binary Comparison And MODIS Truth Workflow

Implement the Phase 2 deliverables from the canonical wetland comparison plan:
shared binary harmonization, rough-scale disagreement metrics, focus AOI selection,
and MODIS reference chip download plumbing through GEE.

## Problem Statement

Phase 1 completed the loader foundation, but the repository still cannot:

- harmonize the eight documented datasets into a common binary wetland view,
- compare eligible datasets on a shared grid and overlap window,
- identify rough-scale disagreement AOIs for analyst review,
- request MODIS reference imagery for those AOIs through GEE.

Without these pieces, the project cannot transition from raw data access to
reviewable comparison outputs.

## Findings

- The canonical execution plan is `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md`.
- Loader outputs already normalize common dynamic variables such as
  `wetland_fraction`, `watermask`, and `wetland_class`.
- Static classification products use dataset-specific native codes:
  `g2017.wetland`, `glwd_v2.combined_classes`, and `gwd30.wetland_class`.
- `config/datasets.yaml` already provides analysis-level defaults:
  region definitions, trend tests, and aggregation levels.
- `config/gee_config.yaml` already exists and should remain read-only.
- The legacy project includes mapping/alignment references that can guide
  class-to-binary conversions and grid harmonization.

## Proposed Solutions

### Option 1: Build a minimal but end-to-end Phase 2 slice

**Approach:** Add comparison and validation modules with deterministic pure-Python
interfaces, then cover them with unit tests and isolated GEE-facing tests.

**Pros:**
- Ships a usable Phase 2 foundation quickly.
- Keeps the design testable without live GEE dependency.
- Preserves room for Phase 3/4 extensions.

**Cons:**
- Some export-policy and manifest details will still be basic until later phases.
- Synchronous-only test coverage cannot prove real GEE auth in CI.

**Effort:** 1 working session

**Risk:** Medium

---

### Option 2: Delay comparison until all future phases are designed together

**Approach:** Design rough comparison, fine-grained comparison, trends, and full
validation manifests before writing code.

**Pros:**
- More globally consistent architecture.

**Cons:**
- Delays any executable Phase 2 deliverable.
- Repeats planning work that already exists in the canonical plan.

**Effort:** 1-2 sessions

**Risk:** Medium

## Recommended Action

Implement Option 1. Build the comparison foundation and MODIS reference flow now,
using deterministic local interfaces and test doubles for GEE interactions. Keep
the code scoped to Phase 2 deliverables only.

## Technical Details

**Affected files:**
- `src/WA/comparison/`
- `src/WA/validation/`
- `tests/test_comparison/`
- `tests/test_validation/`
- `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md`

**Related components:**
- `src/WA/config.py`
- `src/WA/loaders/*`
- `config/datasets.yaml`
- `config/gee_config.yaml`

**Database changes (if any):**
- No database changes.

## Resources

- Canonical plan:
  `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md`
- Legacy reference memory:
  `../../.claude/projects/-Users-mac-Code-WA/memory/reference_legacy_project.md`
- Latest validation stash:
  `docs/stashes/2026-03-19-002-fix-phase1-loader-hpc-verified.md`

## Acceptance Criteria

- [x] `src/WA/comparison/harmonize.py` converts supported datasets into binary wetland classes.
- [x] `src/WA/comparison/rough_binary.py` computes pairwise rough-scale metrics and disagreement surfaces.
- [x] `src/WA/comparison/focus_areas.py` derives stratified rough AOIs from disagreement outputs.
- [x] `src/WA/validation/gee_client.py` initializes GEE from config via an isolated client wrapper.
- [x] `src/WA/validation/modis_reference.py` builds MODIS requests and local output plans for AOIs.
- [x] Phase 2 tests cover harmonization, AOI selection, and MODIS request/state handling.
- [x] Relevant plan checkboxes are updated.
- [x] `pytest`, `ruff`, and `mypy` pass for the implemented slice.

## Work Log

### 2026-03-19 - Phase 2 Execution Start

**By:** Codex

**Actions:**
- Read `AGENTS.md`, `CLAUDE.md`, memory files, and the latest stash summaries.
- Confirmed Phase 1 is complete and Phase 2 is the next execution target.
- Read the canonical Phase 2 plan section and current loader output contracts.
- Created branch `feat/phase2-rough-binary-modis-truth`.
- Created this ready todo to track the implementation.

**Learnings:**
- Loader outputs are already normalized enough to support a focused Phase 2 build.
- The main design work now is class-to-binary mapping, comparison grid alignment,
  and isolating GEE integration behind testable wrappers.

### 2026-03-19 - Phase 2 Slice Completed

**By:** Codex

**Actions:**
- Added `src/WA/comparison/harmonize.py` for binary wetland harmonization,
  monthly subsetting, and shared-grid reprojection.
- Added `src/WA/comparison/rough_binary.py` for pairwise rough metrics and
  disagreement-score surfaces.
- Added `src/WA/comparison/focus_areas.py` for stratified AOI selection over
  Brazil, Indonesia, Southeast Asia, and Africa.
- Added `src/WA/validation/gee_client.py` and
  `src/WA/validation/modis_reference.py` for isolated GEE initialization and
  deterministic MODIS quicklook/chip downloads with explicit terminal states.
- Added comparison/validation tests, including an end-to-end synthetic Phase 2
  pipeline test using a fake Earth Engine module.
- Ran:
  - `uv run pytest -q`
  - `uv run ruff check .`
  - `uv run mypy src tests`
- Updated the canonical plan checkboxes for the completed Phase 2 items.

**Learnings:**
- G2017 rough-scale binary comparison should prefer `wetland_nolake`, while
  fine-grained comparison can still rely on native `wetland` class codes later.
- TOPMODEL needs ensemble collapse before cross-dataset comparison; mean across
  `config` and `forcing` is a workable Phase 2 default.
- Explicit AOI terminal states such as `unsupported_time_window`,
  `gee_auth_failed`, `empty_collection`, and `cached` materially simplify
  downstream orchestration.

## Notes

- Keep `config/` read-only.
- Do not expand into Phase 3 trend or Sentinel-2 work in this todo.
