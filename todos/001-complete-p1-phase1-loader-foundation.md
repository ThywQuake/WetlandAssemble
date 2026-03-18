---
status: complete
priority: p1
issue_id: "001"
tags: [python, geospatial, loaders, phase1]
dependencies: []
---

# Phase 1 Loader Foundation

Implement the loader foundation from the canonical Wetland Comparison plan so the repository can read the eight documented wetland datasets through a common Python API.

## Problem Statement

The repository has planning artifacts and config files, but no executable Phase 1 implementation. Without a config loader, registry, dataset loader contract, and dataset-specific loaders, later comparison, trend, and GEE validation phases cannot start.

## Findings

- The canonical execution document is `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md`.
- The repository is still at scaffold stage: no `src/WA` package, no `tests/`, and no existing loader code.
- `CLAUDE.md` forbids editing `config/` without approval, so implementation must treat YAML config files as read-only inputs.
- `config/datasets.yaml` documents eight in-scope datasets plus one explicitly out-of-scope dataset, `lstm_wetland`.
- The superseded draft plan still contains Phase 1 acceptance details that are useful for loader-level implementation and tests.

## Proposed Solutions

### Option 1: Full Phase 1 vertical slice

**Approach:** Build config loading, loader base classes, registry, all eight dataset loaders, and synthetic tests in one pass.

**Pros:**
- Matches the requested Phase 1 scope directly
- Leaves a usable base for later phases

**Cons:**
- Broad change set touching multiple loader styles
- Requires careful synthetic fixtures to keep tests reliable

**Effort:** 1 focused implementation session

**Risk:** Medium

---

### Option 2: Framework first, dataset loaders later

**Approach:** Build only the config module, registry, and abstract base layer now, defer concrete loaders.

**Pros:**
- Smaller initial diff
- Lower implementation risk per turn

**Cons:**
- Does not satisfy the requested Phase 1 start criteria
- Leaves downstream work blocked

**Effort:** Short

**Risk:** Low

## Recommended Action

Execute Option 1 with a test-first bias: define the common loader contract and metadata model, implement loaders one by one against synthetic fixtures, and keep config files read-only. Defer Phase 2-5 modules, remote operations, and any `config/` schema change.

## Technical Details

**Target files:**
- `src/WA/config.py`
- `src/WA/loaders/*.py`
- `tests/test_config.py`
- `tests/test_loaders/*`
- `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md`
- `docs/stashes/*`

**Related constraints:**
- No `config/` edits without approval
- Local-only git workflow
- Need Chinese-aware documentation handling when plan/stash files change

## Resources

- Canonical plan: `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md`
- Superseded Phase 1 detail draft: `docs/plans/2026-03-18-feat-dataset-loaders-plan.md`
- Project objective: `docs/aim.md`
- Dataset docs: `docs/datasets/*.md`

## Acceptance Criteria

- [x] Config module loads dataset and GEE config as read-only inputs
- [x] Common loader contract and registry exist
- [x] All eight documented datasets have concrete loaders
- [x] Loaders expose consistent metadata and support subsetting where feasible
- [x] Synthetic tests cover each loader's key edge case
- [x] `pytest`, `ruff`, and `mypy` pass
- [x] Phase 1-related checkboxes are updated in the canonical plan
- [x] A stash summary records architecture, verification, and open risks

## Work Log

### 2026-03-18 - Todo Creation

**By:** Codex

**Actions:**
- Read the canonical plan, superseded draft, `CLAUDE.md`, and current project stash notes
- Confirmed the request is specifically to start Phase 1 implementation
- Chose a local feature branch workflow instead of committing on `main`
- Scoped work to Phase 1 loader foundation only

**Learnings:**
- The canonical plan includes later-phase acceptance criteria, so progress updates must be selective and limited to Phase 1 work
- Dataset documentation, not runtime data access, is the main local source of truth for loader behavior and tests

### 2026-03-18 - Implementation Complete

**By:** Codex

**Actions:**
- Added `src/WA/config.py` with read-only config loading helpers for dataset and GEE YAML files
- Added loader foundation under `src/WA/loaders/` for Berkeley-RWAWC, GIEMS-MC, WAD2M, SWAMPS, TOPMODEL, G2017, GLWD v2, and GWD30
- Added synthetic coverage in `tests/test_config.py` and `tests/test_loaders/*`
- Verified with `uv run pytest -q`, `uv run ruff check .`, and `uv run mypy src tests`
- Updated Phase 1 checkboxes in the canonical plan and wrote a new stash summary

**Learnings:**
- A single shared loader contract plus small format-specific helpers was enough to cover all eight datasets without touching `config/`
- The current GWD30 implementation provides virtual mosaic-style merged access by filtering candidate tiles and merging selected rasters after reprojection
- The geospatial stack emits a `numpy.ndarray size changed` runtime warning during NetCDF-backed tests; it does not fail the suite, but it should be watched when the environment changes

## Notes

- Do not implement `lstm_wetland` in this phase
- Do not push, open a PR, or rely on any git remote
