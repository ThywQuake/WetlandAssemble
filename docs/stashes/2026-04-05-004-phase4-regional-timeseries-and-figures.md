# 2026-04-05 Phase 4 Regional Time Series and Figures

## Summary

Phase 4 now has a new regional workflow centered on cache-backed area-weighted
time series instead of per-pixel trend rasters.

Primary entrypoint:

- `scripts/run_phase4_regional.py`

Core implementation:

- `src/WA/comparison/phase4_regional.py`
- `src/WA/visualization/phase4.py`

Tests:

- `tests/test_comparison/test_phase4_regional.py`
- `tests/test_visualization/test_phase4.py`

## What Changed

### Regional analysis pipeline

- Added a fixed Phase 4 region catalog:
  - macro regions:
    - `pan_trop_subtrop`
    - `north_tropics`
    - `south_tropics`
    - `southeast_asia`
    - `africa`
    - `south_america`
  - plus all 10 `config/priority_regions.yaml` regions
- Added Phase 4 raw-loader overrides for:
  - `topmodel` -> raw `topmodel` loader instead of standardized config
  - `berkeley_rwawc` -> raw `berkeley` loader instead of standardized config
- Added Phase 3.6 shared-mask loading from the 500 m `joint_valid_mask`
- Added per-dataset, per-region shared-mask downsampling caches under:
  - `results/phase4/cache/masks/<dataset_id>/<region_id>_shared_mask_fraction.nc`
- Added area-weighted regional reduction that outputs:
  - monthly series
  - annual complete-year series
  - 12-month climatology
- Added per-dataset regional cache tables under:
  - `results/phase4/cache/<dataset_id>/<region_id>/regional_series.csv`
- Added combined per-region tables under:
  - `results/phase4/tables/<region_id>.csv`

### GWD30 handling

- Phase 4 GWD30 no longer needs to merge one full regional time cube before
  regional statistics.
- The workflow stages GWD30 tile partials on the Phase 3.6 500 m mask grid,
  then reduces wetland area and valid area directly from staged tile partials.
- This keeps the `staged_tiles` strategy requested for Phase 4 while avoiding
  the large merged intermediate for broad regions.

### Figure export

- Added interannual figures:
  - `results/figures/phase4/interannual/<region_id>.png`
- Added climatology figures:
  - `results/figures/phase4/climatology/<region_id>.png`
- Plot style keeps a fixed dataset order:
  - `gwd30`
  - `giems_mc`
  - `topmodel`
  - `swamps`
  - `wad2m`
  - `berkeley_rwawc`
- `berkeley_rwawc` is plotted as a grey dashed auxiliary line.

## Verification

- `python -m compileall src/WA/comparison/phase4_regional.py src/WA/visualization/phase4.py scripts/run_phase4_regional.py`
- `ruff check src/WA/comparison/phase4_regional.py src/WA/visualization/phase4.py scripts/run_phase4_regional.py tests/test_comparison/test_phase4_regional.py tests/test_visualization/test_phase4.py`
- `python -m pytest tests/test_comparison/test_phase4_regional.py tests/test_visualization/test_phase4.py -q`
- `python -m pytest tests/`

Result:

- `ruff` passed on all new/changed Phase 4 files
- targeted tests: `7 passed`
- full suite: `400 passed`

## HPC Commands

Run one priority region first:

```bash
python scripts/run_phase4_regional.py \
  --region amazon \
  --dataset-id gwd30 \
  --dataset-id giems_mc \
  --dataset-id topmodel \
  --dataset-id swamps \
  --dataset-id wad2m \
  --dataset-id berkeley_rwawc \
  --topmodel-raw-path ~/Wetland_Assemble/data/TOPMODEL \
  --berkeley-raw-path ~/Wetland_Assemble/data/Berkeley_RWAWC \
  --gwd30-cache-dir results/cache/phase4_trends \
  --gwd30-worker-count 4 \
  --output-root results/phase4 \
  --figures-root results/figures/phase4 \
  --no-skip
```

Run all configured regions:

```bash
python scripts/run_phase4_regional.py \
  --topmodel-raw-path ~/Wetland_Assemble/data/TOPMODEL \
  --berkeley-raw-path ~/Wetland_Assemble/data/Berkeley_RWAWC \
  --gwd30-cache-dir results/cache/phase4_trends \
  --gwd30-worker-count 4 \
  --output-root results/phase4 \
  --figures-root results/figures/phase4 \
  --no-skip
```

## Known Risks

- `berkeley_rwawc` remains a very high-resolution auxiliary dataset, so very
  large macro-region runs may still be slow even with stripe-based spatial
  reduction.
- The Phase 4 script intentionally does not modify `config/datasets.yaml`;
  raw `topmodel` and `berkeley_rwawc` access currently depends on CLI path
  overrides.
- Figure titles currently use the English region label for safer HPC font
  behavior. If Chinese plot titles are required later, a font-aware plotting
  pass should be added rather than forcing `label_zh` immediately.
