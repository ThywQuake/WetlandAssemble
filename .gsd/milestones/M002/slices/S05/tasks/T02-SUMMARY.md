---
id: T02
parent: S05
milestone: M002
key_files:
  - src/WA/comparison/percentage_backbone.py
  - src/WA/comparison/percentage_hotspots.py
  - scripts/run_phase4_percentage_contract.py
  - scripts/plot_tropical_wetland_025deg.py
  - tests/test_comparison/test_percentage_backbone.py
  - tests/test_comparison/test_percentage_hotspots.py
  - tests/test_plot_tropical_wetland_025deg.py
  - src/WA/test_selection.py
  - docs/testing/test-categories.md
  - CHANGELOG.md
  - .gsd/KNOWLEDGE.md
  - docs/stashes/2026-04-09-006-m002-s05-t02-percentage-backbone.md
key_decisions:
  - D044 — treat `dataset_key=canonical` as one ordered six-dataset percentage bundle, write one stacked contract surface artifact with derived mean/std/count metrics, and rank percentage hotspots by bundle-level `mean_wetland_percentage` instead of by per-dataset files.
  - Keep the percentage line as one multi-dataset contract family per region: live Phase 4 regional tables remain the summary source, the backbone writes one shared coarse-surface bundle keyed by `dataset_key + region_id`, and hotspot JSON/CSV pairs are only trusted after semantic reload validation.
duration: 
verification_result: mixed
completed_at: 2026-04-08T18:41:30.146Z
blocker_discovered: false
---

# T02: Restored the real percentage producer chain with a shared backbone, GWD30 Stage-1 surface recovery, atomic hotspot pairs, and a contract-aware runner for one region, `canonical`, or `ten`.

**Restored the real percentage producer chain with a shared backbone, GWD30 Stage-1 surface recovery, atomic hotspot pairs, and a contract-aware runner for one region, `canonical`, or `ten`.**

## What Happened

Implemented `src/WA/comparison/percentage_backbone.py` as the shared owner of the Phase 4 percentage surface path, keeping the existing 0.25° non-GWD30 loader/aggregation logic while adding a real GWD30 Stage-1 pixel-statistics restore path plus contract-backed `surface` and `regional_summary` write/reload helpers. Added `src/WA/comparison/percentage_hotspots.py` to rank bundle-level percentage hotspots, write atomic manifest/CSV pairs, and fail closed on malformed or partial reloads. Added `scripts/run_phase4_percentage_contract.py` to compose live Phase 4 regional summaries, the restored multi-dataset coarse-surface bundle, and hotspot writes across one region, `--subset canonical`, or `--subset ten`, while making dataset selection and skip behavior explicit in logs. Refactored `scripts/plot_tropical_wetland_025deg.py` into a thin wrapper over the backbone, extended focused tests for the new backbone/hotspot/smoke surfaces, updated related-test routing plus docs, recorded decision D044, added a NetCDF string-coordinate gotcha to `.gsd/KNOWLEDGE.md`, updated `CHANGELOG.md`, and wrote the operator stash note at `docs/stashes/2026-04-09-006-m002-s05-t02-percentage-backbone.md`.

## Verification

Passed the task-plan verification commands exactly as written: `ruff check src/WA/comparison/percentage_backbone.py src/WA/comparison/percentage_hotspots.py scripts/run_phase4_percentage_contract.py scripts/plot_tropical_wetland_025deg.py tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_percentage_hotspots.py tests/test_plot_tropical_wetland_025deg.py`; `python scripts/run_phase4_percentage_contract.py --help`; `python -m pytest tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_percentage_hotspots.py tests/test_plot_tropical_wetland_025deg.py -q`; and `python scripts/run_related_tests.py src/WA/comparison/percentage_backbone.py src/WA/comparison/percentage_hotspots.py scripts/run_phase4_percentage_contract.py scripts/plot_tropical_wetland_025deg.py`. Additional verification passed for the routing update with `ruff check src/WA/test_selection.py tests/test_test_selection.py` and `python -m pytest tests/test_test_selection.py -q`. Project-wide verification was also run with `python -m pytest tests/`, which still reproduces the pre-existing unrelated `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` failure and later exits 137 before the suite completes.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `ruff check src/WA/comparison/percentage_backbone.py src/WA/comparison/percentage_hotspots.py scripts/run_phase4_percentage_contract.py scripts/plot_tropical_wetland_025deg.py tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_percentage_hotspots.py tests/test_plot_tropical_wetland_025deg.py` | 0 | ✅ pass | 40ms |
| 2 | `python scripts/run_phase4_percentage_contract.py --help` | 0 | ✅ pass | 1860ms |
| 3 | `python -m pytest tests/test_comparison/test_percentage_backbone.py tests/test_comparison/test_percentage_hotspots.py tests/test_plot_tropical_wetland_025deg.py -q` | 0 | ✅ pass | 6810ms |
| 4 | `python scripts/run_related_tests.py src/WA/comparison/percentage_backbone.py src/WA/comparison/percentage_hotspots.py scripts/run_phase4_percentage_contract.py scripts/plot_tropical_wetland_025deg.py` | 0 | ✅ pass | 240ms |
| 5 | `ruff check src/WA/test_selection.py tests/test_test_selection.py` | 0 | ✅ pass | 0ms |
| 6 | `python -m pytest tests/test_test_selection.py -q` | 0 | ✅ pass | 370ms |
| 7 | `python -m pytest tests/` | 137 | ❌ fail | 35060ms |
| 8 | `python -m pytest tests/test_mgrs_tiling.py -q` | 1 | ❌ fail | 780ms |

## Deviations

Beyond the task plan’s expected output files, I also updated `src/WA/test_selection.py`, `docs/testing/test-categories.md`, `CHANGELOG.md`, `.gsd/KNOWLEDGE.md`, and recorded D044 so the restored percentage line is discoverable and durable for downstream S05 tasks. I also made `scripts/plot_tropical_wetland_025deg.py` a pure wrapper instead of leaving a second copy of the backbone logic behind.

## Known Issues

`python -m pytest tests/` still reproduces the pre-existing unrelated red bar at `tests/test_mgrs_tiling.py::test_tile_to_extent_matches_reference_case` and later exits 137 before the full suite completes. No real HPC execution against external standardized inputs was run from this worktree.

## Files Created/Modified

- `src/WA/comparison/percentage_backbone.py`
- `src/WA/comparison/percentage_hotspots.py`
- `scripts/run_phase4_percentage_contract.py`
- `scripts/plot_tropical_wetland_025deg.py`
- `tests/test_comparison/test_percentage_backbone.py`
- `tests/test_comparison/test_percentage_hotspots.py`
- `tests/test_plot_tropical_wetland_025deg.py`
- `src/WA/test_selection.py`
- `docs/testing/test-categories.md`
- `CHANGELOG.md`
- `.gsd/KNOWLEDGE.md`
- `docs/stashes/2026-04-09-006-m002-s05-t02-percentage-backbone.md`
