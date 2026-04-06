# 2026-04-04-002 Phase 3.6 GWD30 Source Dominant OOM Fix

## Problem

- HPC Phase 3.6 rerun was OOM-killed in `stage[01]` immediately after reduced
  tiles were produced.
- The failing path was the new `gwd30_source_dominant_class` export.
- Root cause: `stage[01]` restored a full-stripe staged GWD30 time cube via
  `merge_staged_time_fraction_tiles(...)` in order to derive raw/source
  dominance, which multiplied memory by `time x raw_class x stripe`.

## Fix

- `/Users/mac/Code/WA/src/WA/loaders/gwd30.py`
  - `phase36_reduce_staged_time_fraction_tile(...)` now also writes
    `annual_source_weighted_sum` in each reduced tile.
- `/Users/mac/Code/WA/src/WA/comparison/phase36.py`
  - Bumped `PHASE36_GWD30_REDUCE_VERSION` to `2`.
  - `stage[01]` GWD30 source-dominant export now accumulates
    `annual_source_weighted_sum` from reduced tiles and computes
    `gwd30_source_dominant_class` from the annual raw/source fractions.
  - This removes the staged time-cube reconstruction from the global cache
    path and keeps memory closer to the existing unified-dominant workflow.

## Why Raw Classes Were Missing In The New PNG

- The Phase 3.6 rerun died before it could finish writing the new
  `phase3_6_unified_classes_global_500m_2016.nc` that includes
  `*_source_dominant_class`.
- Then the Phase 3.7 plot command logged:
  `standardized-dir 不存在，将优先依赖 classes 文件中的预计算 source dominant vars；若缺失则回退 unified hotspot panel`
- Since the new Phase 3.6 file was not completed, plotting fell back to the
  older unified-only classes file, so the PNG still looked like unified mode.

## Verification

- `ruff check src/WA/comparison/phase36.py src/WA/loaders/gwd30.py tests/test_loaders/test_gwd30.py tests/test_phase3_6_analysis.py`
- `python -m pytest tests/test_loaders/test_gwd30.py tests/test_phase3_6_analysis.py -q`
- `python -m pytest tests/test_phase3_7_hotspot_panels.py tests/test_phase3_7_plotting.py tests/test_phase3_7_regional_panels.py tests/test_phase3_7_hotspots.py -q`

## HPC Rerun

First rerun Phase 3.6 so the new reduced tiles and final classes file are rebuilt:

```bash
python scripts/run_phase3_6_global_entropy.py \
  --standardized-dir ~/Wetland_Assemble/data/standardized \
  --output-dir results/phase3.6 \
  --cache-dir results/cache/phase3_6 \
  --year 2016 \
  --lat-chunk-size 512 \
  --no-prefer-cache
```

Then verify the final classes file really contains raw/source variables:

```bash
python - <<'PY'
import xarray as xr
ds = xr.open_dataset("results/phase3.6/phase3_6_unified_classes_global_500m_2016.nc")
print(list(ds.data_vars))
ds.close()
PY
```

Then redraw hotspots:

```bash
python scripts/plot_phase3_7_hotspot_panels.py \
  --hotspots-manifest results/phase3.7_hotspots/phase3_7_hotspots_2016.json \
  --s2-artifacts-manifest results/phase3.7_hotspots/phase3_7_s2_artifacts_2016_20160701.json \
  --input-dir results/phase3.6 \
  --output-dir results/figures/phase3.7_hotspots \
  --year 2016 \
  --dpi 300
```
