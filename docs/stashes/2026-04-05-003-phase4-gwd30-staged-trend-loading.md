# 2026-04-05-003 Phase 4 GWD30 Staged Trend Loading

## Summary

- Phase 4 trend probing now avoids `GWD30Loader.load()` for `gwd30`.
- `gwd30` trend surfaces are now built year-by-year on the requested trend
  reference grid via `stage_time_fraction_tiles()` plus
  `merge_staged_time_fraction_tiles()`.
- Staged trend tile partials are cached under
  `results/cache/phase4_trends/<grid-token>/gwd30_<year>/tile_partials` so
  repeated probes can resume without silently reusing the wrong grid.

## Code

- `/Users/mac/Code/WA/src/WA/comparison/trends.py`
  - Added `load_trend_surface(...)`.
  - Added the GWD30 staged-tile trend dataset loader and deterministic
    cache-token helpers.
- `/Users/mac/Code/WA/scripts/hpc_probe_trends.py`
  - Probe now uses `load_trend_surface(...)`.
  - Added `--gwd30-cache-dir` and `--gwd30-worker-count`.
  - Updated usage text to `python`, not `uv`.
- `/Users/mac/Code/WA/tests/test_comparison/test_trends.py`
  - Added regression coverage for the GWD30 staged-tile trend path.
- `/Users/mac/Code/WA/CHANGELOG.md`
  - Added a user-facing note for the Phase 4 GWD30 staged trend change.

## Verification

- `ruff check src/WA/comparison/trends.py src/WA/comparison/__init__.py scripts/hpc_probe_trends.py tests/test_comparison/test_trends.py`
- `python -m pytest tests/test_comparison/test_trends.py -q`
- `python -m pytest tests/`

## HPC

Run the GWD30 Phase 4 probe with staged-tile caching like this:

```bash
python scripts/hpc_probe_trends.py \
  --dataset-id gwd30 \
  --aggregation annual \
  --bbox -65 -20 -45 5 \
  --gwd30-cache-dir results/cache/phase4_trends \
  --gwd30-worker-count 4 \
  --json-out results/phase4/probe_gwd30_annual.json
```

## Risks

- This change caches staged tiles for the requested trend grid, but it does
  not yet write a dedicated merged annual/monthly trend-input cache; each run
  still merges cached tile partials per year.
- Cross-dataset Phase 4 batch execution is still not wired through a dedicated
  `run_phase4_trend_analysis.py` workflow.
