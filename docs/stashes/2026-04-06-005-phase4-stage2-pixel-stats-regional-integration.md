# 2026-04-06-005 Phase4 Stage2 Pixel-Stats Regional Integration

## Summary

- Implemented Phase 4 Stage 2 for `gwd30`.
- Regional `gwd30` analysis now consumes Stage-1 native pixel-statistics tiles
  from `results/phase4/pixel_stats/gwd30/gwd30_<year>/monthly/`.
- Berkeley valid mask is now applied at Stage 2 on each native tile grid
  before the region-level monthly series is assembled.

## Key Files

- [src/WA/comparison/phase4_regional.py](/Users/mac/Code/WA/src/WA/comparison/phase4_regional.py)
- [scripts/run_phase4_regional.py](/Users/mac/Code/WA/scripts/run_phase4_regional.py)
- [tests/test_comparison/test_phase4_regional.py](/Users/mac/Code/WA/tests/test_comparison/test_phase4_regional.py)
- [CHANGELOG.md](/Users/mac/Code/WA/CHANGELOG.md)

## What Changed

- Added helpers to locate and load Stage-1 `tile_manifest.json` files.
- Added a native-tile reducer that reads `wetland_fraction(time, y, x)` and
  `cell_area_km2(y, x)` from each transformed tile.
- Added on-the-fly Berkeley-mask projection to each native tile grid using
  average resampling.
- Switched `compute_phase4_region_dataset_table(..., dataset_id="gwd30")`
  from `_staging` restoration to Stage-1 pixel-statistics tile consumption.

## Verification

- `ruff check src/WA/comparison/phase4_regional.py scripts/run_phase4_regional.py tests/test_comparison/test_phase4_regional.py`
- `python -m compileall src/WA/comparison/phase4_regional.py scripts/run_phase4_regional.py tests/test_comparison/test_phase4_regional.py`
- `python -m pytest tests/test_comparison/test_phase4_regional.py -q`
- `python -m pytest tests/`

## HPC Next Command

For a single region and Stage-1 outputs that already exist:

```bash
python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --region amazon \
  --output-root results/phase4 \
  --berkeley-raw-path /lustre/home/2200013429/Wetland_Assemble/data/Berkeley/data \
  --start-year 2022 \
  --end-year 2022 \
  --no-skip
```
