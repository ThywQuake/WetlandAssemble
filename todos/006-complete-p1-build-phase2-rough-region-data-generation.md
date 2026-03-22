---
status: complete
priority: p1
issue_id: "006"
tags: [phase2, rough, batch, data-generation]
dependencies: ["003", "004", "005"]
---

# Build Phase 2 Rough Region Data Generation

Implement the first non-visual Phase 2 production path: generate rough-scale
wetland comparison data files for nine priority tropical basins/wetland regions
across two comparison windows.

## Scope

Target windows:
- `2000-03-01` (max historical participant overlap)
- `2019-07-01` (modern overlap including GWD30)

Target regions:
- amazon_basin
- orinoco_basin_llanos
- pantanal_upper_paraguay
- ngiri_tumba_maindombe
- sudd
- okavango_delta
- mekong_delta
- mekong_flooded_forest
- danau_sentarum

## Acceptance Criteria

- [x] A machine-readable region catalog exists for the nine priority regions.
- [x] A batch CLI can run rough comparison for multiple regions and multiple target months.
- [x] Each successful region/time run writes metrics and gridded comparison outputs to `results/`.
- [x] Each region/time run writes a summary/manifest-style metadata file with participant and failure statuses.
- [x] Expected domain failures (like empty GLWD surfaces) are recorded in output metadata without aborting the whole batch.
- [x] Tests cover region catalog loading, batch output writing, and multi-window batch execution.
- [x] Focused pytest and ruff checks pass.

## Work Log

### 2026-03-19 - Batch data generation implemented

**By:** Codex

**Actions:**
- Added `docs/regions/2026-03-19-priority-tropical-basins-and-wetlands.yaml` with 9 priority tropical basin/wetland analysis windows.
- Added `src/WA/rough_batch.py` to load the region catalog and generate rough Phase 2 outputs for multiple regions and target windows.
- Added `scripts/run_phase2_rough_regions.py` as the production CLI entrypoint.
- Added `tests/test_rough_batch.py` covering region loading and multi-window batch output writing.
- Ran focused validation:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_rough_batch.py tests/test_rough_probe.py tests/test_loader_probe.py tests/test_comparison/test_rough_binary.py tests/test_comparison/test_harmonize.py -q`
  - `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/WA/rough_batch.py scripts/run_phase2_rough_regions.py tests/test_rough_batch.py src/WA/rough_probe.py src/WA/loader_probe.py tests/test_rough_probe.py tests/test_loader_probe.py tests/test_comparison/test_rough_binary.py tests/test_comparison/test_harmonize.py`

**Learnings:**
- The cleanest implementation path was to reuse `probe_prepared_dataset()` for per-dataset participation and layer a separate batch writer on top for region/time outputs.
- Writing both summary JSON and gridded NetCDF outputs now gives a good non-visual Phase 2 artifact base for later plotting and QC.
