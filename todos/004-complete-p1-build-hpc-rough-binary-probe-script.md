---
status: complete
priority: p1
issue_id: "004"
tags: [phase2, hpc, rough, diagnostics]
dependencies: ["003"]
---

# Build HPC Rough Binary Probe Script

Create a detailed HPC-facing diagnostic script for the Phase 2 rough binary
workflow so we can validate real dataset loading, temporal participation,
shared-grid harmonization, pairwise metrics, and focus AOI selection against the
actual PKU HPC data paths.

## Problem Statement

Phase 2 comparison code now exists locally, but there is no dedicated HPC
diagnostic entrypoint for the rough workflow. We currently have:

- loader-only probing via `scripts/hpc_probe_loaders.py`,
- local unit tests for rough harmonization and metrics,
- no real-data rough comparison script that prints detailed operational output.

Without a rough-specific HPC probe, we cannot quickly answer:

- which datasets actually participate for a chosen target month,
- which datasets are skipped because of time-window mismatch,
- whether harmonized rough surfaces look sane on the shared grid,
- what the pairwise rough metrics and disagreement hotspots are on real data.

## Findings

- The existing loader probe already provides the desired terminal style:
  timestamped progress lines plus a verbose multiline report.
- `src/WA/comparison/harmonize.py`, `rough_binary.py`, and `focus_areas.py`
  already provide the core Phase 2 rough workflow.
- `loader_probe.py` already contains reusable helpers for:
  - dataset selection,
  - bbox resolution,
  - filesystem discovery summaries,
  - dataset JSON-safe rendering.
- A safe Amazon probe bbox already exists and is appropriate as the default
  rough HPC probe area.

## Proposed Solutions

### Option 1: Add a dedicated rough probe helper + CLI script

**Approach:** Create `src/WA/rough_probe.py` plus
`scripts/hpc_probe_rough_binary.py`, mirroring the loader probe architecture.

**Pros:**
- Fits existing HPC operations style.
- Produces detailed, scriptable diagnostics.
- Keeps rough probing reusable outside the top-level script.

**Cons:**
- Some code overlaps conceptually with loader probing.

**Effort:** 1 session

**Risk:** Low

---

### Option 2: Extend the existing loader probe script

**Approach:** Add rough-comparison mode flags directly into `loader_probe.py`.

**Pros:**
- Fewer top-level scripts.

**Cons:**
- Mixes loader-only diagnostics with higher-level comparison behavior.
- Makes the existing loader probe harder to reason about.

**Effort:** 1 session

**Risk:** Medium

## Recommended Action

Implement Option 1. Keep loader probing and rough comparison probing separate,
but reuse common helper utilities from `loader_probe.py`.

## Technical Details

**Affected files:**
- `src/WA/rough_probe.py`
- `scripts/hpc_probe_rough_binary.py`
- `tests/test_rough_probe.py`

**Related components:**
- `src/WA/loader_probe.py`
- `src/WA/comparison/harmonize.py`
- `src/WA/comparison/rough_binary.py`
- `src/WA/comparison/focus_areas.py`
- `src/WA/validation/modis_reference.py`

**Database changes (if any):**
- No database changes.

## Acceptance Criteria

- [x] A dedicated HPC rough probe CLI exists and runs from `scripts/`.
- [x] The probe prints detailed per-dataset statuses, discovery info, dataset summaries, and harmonized summaries.
- [x] The probe computes and prints rough pairwise metrics and disagreement/focus AOI summaries when at least two datasets participate.
- [x] The probe reports explicit skip/failure reasons instead of silently dropping datasets.
- [x] The probe supports JSON output for later inspection.
- [x] Tests cover target-time derivation and detailed report rendering.
- [x] `pytest`, `ruff`, and `mypy` pass after implementation.

## Work Log

### 2026-03-19 - Rough Probe Task Created

**By:** Codex

**Actions:**
- Reviewed the existing loader probe architecture and confirmed it is the right
  style reference for an HPC rough-comparison probe.
- Created this todo to track the new detailed rough workflow diagnostic script.

**Learnings:**
- The rough probe should reuse the existing safe bbox, dataset discovery, and
  JSON rendering helpers rather than duplicating them.

### 2026-03-19 - Rough Probe Script Completed

**By:** Codex

**Actions:**
- Added `src/WA/rough_probe.py` with:
  - target-month derivation,
  - per-dataset participation probing,
  - shared-grid rough harmonization,
  - pairwise rough metric execution,
  - disagreement and focus AOI summaries,
  - optional MODIS download fan-out,
  - detailed multiline report rendering,
  - optional JSON dump.
- Added `scripts/hpc_probe_rough_binary.py` as the HPC-facing entrypoint.
- Added `tests/test_rough_probe.py` covering:
  - default target-time derivation,
  - CLI option resolution,
  - per-dataset participation probing,
  - full synthetic rough probe execution and report rendering.
- Ran:
  - `uv run python scripts/hpc_probe_rough_binary.py --help`
  - `uv run pytest -q`
  - `uv run ruff check .`
  - `uv run mypy src tests`

**Learnings:**
- Deriving the default comparison month from the earliest month with the maximum
  number of dynamic participants is a practical HPC default and avoids hardcoding
  one dataset family.
- Keeping MODIS download optional makes the rough probe useful even on nodes
  where GEE credentials are absent.

## Notes

- Keep the default behavior diagnostic-first.
- If MODIS download verification is included, keep it optional so the script
  still works when GEE credentials are unavailable.
