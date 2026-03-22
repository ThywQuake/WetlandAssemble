---
status: complete
priority: p1
issue_id: "005"
tags: [phase2, bugfix, rough, hpc]
dependencies: ["003", "004"]
---

# Fix Rough Probe HPC Result Integrity

Repair the correctness and reporting issues revealed by `temp/job.03.out.txt`:
WAD2M month selection, GLWD effective participation, and rough probe overall
status semantics.

## Problem Statement

The rough HPC probe currently produces a misleading mix of real results and
silent failures:

- `wad2m` fails due to month-start vs month-mid time selection mismatch,
- `glwd_v2` can be treated as participating even when its harmonized surface is
  empty,
- the probe can still report `overall_status: completed` despite failed
  datasets.

These problems undermine trust in rough comparison outputs.

## Findings

- `select_comparison_slice()` currently does exact timestamp selection only.
- WAD2M monthly timestamps are mid-month according to `docs/datasets/WAD2M.md`.
- `GLWDLoader` currently picks the first combined raster file by sort order.
- `job.03.out.txt` shows `glwd_v2` harmonized to all `NaN` and `wad2m` failing
  after successful loading.
- `run_rough_probe()` currently marks any run with >=2 participant surfaces as
  `completed`.

## Proposed Solutions

### Option 1: Fix the comparison core and propagate explicit probe statuses

**Approach:** Repair month-aware selection in `harmonize.py`, stabilize GLWD
combined-raster selection, and make `rough_probe.py` reflect failures/skips in
its final status.

**Pros:**
- Fixes the real source of incorrect behavior.
- Keeps probe/reporting aligned with comparison semantics.

**Cons:**
- Touches multiple layers at once.

**Effort:** 1 session

**Risk:** Medium

## Recommended Action

Implement Option 1.

## Acceptance Criteria

- [x] WAD2M monthly data can be selected by target month without exact timestamp equality.
- [x] GLWD combined raster selection is stable and bbox-aware.
- [x] Empty GLWD binary surfaces become explicit failure states instead of silent participants.
- [x] rough probe overall status distinguishes completed, completed_with_skips, and completed_with_failures.
- [x] Tests cover WAD2M month-aware selection, GLWD empty-surface handling, and rough probe status semantics.
- [x] `pytest`, `ruff`, and `mypy` pass.

## Work Log

### 2026-03-19 - Todo Created

**By:** Codex

**Actions:**
- Created the bugfix todo from `docs/plans/2026-03-19-007-fix-rough-probe-hpc-result-integrity-plan.md`.

**Learnings:**
- This is a correctness-first fix. GWD30 performance hardening can stay
  secondary unless it blocks verification.

### 2026-03-19 - Integrity Fix Implemented

**By:** Codex

**Actions:**
- Updated `src/WA/comparison/harmonize.py` so month-start target months can
  select month-mid monthly timestamps and record `comparison_source_time`.
- Added `EmptyBinarySurfaceError` so comparison code can reject all-empty binary
  surfaces explicitly.
- Updated `src/WA/loaders/glwd.py` so GLWD combined-class raster selection is
  bbox-aware and prefers the candidate with the highest valid-pixel count while
  masking explicit `255` nodata.
- Updated `src/WA/rough_probe.py` so runs now distinguish
  `completed`, `completed_with_skips`, `completed_with_failures`, and `failed`,
  and add warnings for zero-overlap pairwise metric rows.
- Added and updated tests for WAD2M month-aware slicing, GLWD valid-raster
  selection, empty GLWD surface rejection, and rough probe failure-aware status.
- Ran:
  - `uv run pytest -q`
  - `uv run ruff check .`
  - `uv run mypy src tests`

**Learnings:**
- The WAD2M issue belonged in comparison-core time selection, not in probe-only
  branching.
- GLWD should only count as a participant when it produces actual usable
  harmonized comparison cells.
