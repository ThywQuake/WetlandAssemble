# 2026-04-03-003 Phase 3.6 Precompute Source Dominant Classes

## Summary

- Moved raw/source dominant-class derivation for hotspot inspection from
  Phase 3.7 plotting into the Phase 3.6 `stage -> cache` pipeline.
- `phase3_6_unified_classes_*.nc` now includes:
  - `g2017_source_dominant_class`
  - `glwd_v2_source_dominant_class`
  - `gwd30_source_dominant_class`
- Phase 3.7 hotspot plotting now prefers those precomputed variables and only
  falls back to standardized/staged source reconstruction when they are absent.

## Key Changes

- `/Users/mac/Code/WA/src/WA/comparison/phase36.py`
  - Added `compute_source_dominant_class(...)`.
  - Stage[01] static caches now also write per-dataset source-dominant files.
  - Stage[01] GWD30 now writes `01_gwd30_source_dominant_class.nc` by restoring
    stripe-wise staged tiles through the existing merge path.
  - Stage[03] now merges unified dominant classes and source dominant classes
    into `03_dominant_classes.nc`.
  - Bumped `PHASE36_CACHE_VERSION` to `3`.
- `/Users/mac/Code/WA/src/WA/visualization/phase37.py`
  - `build_phase37_hotspot_plot_dataset(...)` now prefers precomputed
    `*_source_dominant_class` vars from the Phase 3.6 classes file.
- `/Users/mac/Code/WA/scripts/plot_phase3_7_hotspot_panels.py`
  - Always opens the Phase 3.6 classes file when present.
  - If `standardized-dir` is missing, it now uses precomputed source vars when
    available and only falls back to unified plotting if they are absent.

## Verification

- `ruff check src/WA/comparison/phase36.py src/WA/visualization/phase37.py scripts/plot_phase3_7_hotspot_panels.py tests/test_phase3_6_analysis.py tests/test_phase3_7_hotspot_panels.py`
- `python -m pytest tests/test_phase3_6_analysis.py tests/test_phase3_7_hotspot_panels.py -q`
- `python -m pytest tests/test_phase3_7_plotting.py tests/test_phase3_7_regional_panels.py tests/test_phase3_7_hotspots.py tests/test_phase3_7_hotspot_panels.py -q`

## HPC Rerun

```bash
python scripts/run_phase3_6_global_entropy.py \
  --standardized-dir ~/Wetland_Assemble/data/standardized \
  --output-dir results/phase3.6 \
  --cache-dir results/cache/phase3_6 \
  --year 2016 \
  --lat-chunk-size 512 \
  --no-prefer-cache
```

Then redraw hotspot panels:

```bash
python scripts/plot_phase3_7_hotspot_panels.py \
  --hotspots-manifest results/phase3.7_hotspots/phase3_7_hotspots_2016.json \
  --s2-artifacts-manifest results/phase3.7_hotspots/phase3_7_s2_artifacts_2016_20160701.json \
  --input-dir results/phase3.6 \
  --output-dir results/figures/phase3.7_hotspots \
  --year 2016 \
  --dpi 300
```
