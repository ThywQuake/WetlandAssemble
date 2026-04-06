# GWD30 Merge Review And On-Demand Pivot

**Date:** 2026-03-30
**Branch:** refactor/loader-reference-grid-alignment
**Commit Range:** unknown (HEAD 3325e72)
**Status:** GWD30 merge path was hardened and partially accelerated, but HPC merge remained operationally fragile; user decided to pivot toward tile-backed on-demand access instead of forcing annual merged outputs.

---

## Key Changes

| File | Change |
|------|--------|
| [src/WA/loaders/gwd30.py](/Users/mac/Code/WA/src/WA/loaders/gwd30.py) | Added staged tile partial workflow, manifest bbox indexing, merge candidate lookup, and related GWD30 coarse staging helpers. |
| [src/WA/standardize.py](/Users/mac/Code/WA/src/WA/standardize.py) | Added shard-manifest restore, GWD30-specific merge flow, streaming final pack, serial GWD30 chunk merge safety, and tile-driven rebucket pipeline. |
| [scripts/standardize_gwd30.py](/Users/mac/Code/WA/scripts/standardize_gwd30.py) | Added merge-only CLI path that restores shard manifests and calls the new GWD30 staged-tile build path. |
| [tests/test_standardize.py](/Users/mac/Code/WA/tests/test_standardize.py) | Added tests for GWD30 streaming final merge, rebucket open-once behavior, and GWD30 serial chunk worker behavior. |

## Verification

- pytest: `python -m pytest tests/test_standardize.py tests/test_loaders/test_gwd30.py -q` -> 67 passed, 4 warnings
- ruff: `ruff check src/WA/standardize.py scripts/standardize_gwd30.py tests/test_standardize.py src/WA/loaders/gwd30.py` -> clean
- HPC:
  - merge previously hit `NetCDF: Can't open HDF5 attribute` plus segfault under threaded chunk merge; local code was adjusted to keep GWD30 serial
  - later merge-only job failed before Python with `scripts/standardize_gwd30.py: Permission denied` because the script was executed directly instead of via the Python interpreter
  - no confirmed successful full-year HPC merge run in this session

## Open Risks / TODOs

- Shard-manifest restore currently skips missing staged tiles with a warning instead of failing hard, which can silently truncate output.
- Shard-manifest restore does not validate run-level metadata consistency such as `bbox`, `resolution_m`, `year`, or `shard_count`.
- Rebucket partial reuse under `skip_existing` only checks readability, not spatial compatibility with the current chunk/grid contract.
- Current downstream standardized-data flow still assumes `output/standardized/*.nc`; a tile-backed GWD30 source needs a dedicated loader path.

## Next Steps

1. Stop pushing the annual GWD30 merge pipeline for now; keep `tile_partials/` and shard manifests as the durable intermediate.
2. Implement a GWD30 on-demand loader that uses `stage_shard_*.json` + `tile_partials/*.nc` to answer `year + bbox + reference_grid` requests lazily.
3. Extend [src/WA/standardized_loader.py](/Users/mac/Code/WA/src/WA/standardized_loader.py) and harmonization entrypoints to special-case GWD30 without requiring `gwd30_YYYY.nc`.
4. Keep tile storage as netCDF first; only evaluate Zarr later if object-store style access or shared caching becomes necessary.
