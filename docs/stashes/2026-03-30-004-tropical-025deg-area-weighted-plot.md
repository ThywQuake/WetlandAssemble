# Tropical 0.25deg Area-Weighted Plotting

**Date:** 2026-03-30
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** Implemented a non-GWD30 tropical plotting path that aggregates wetland fraction to 0.25 degree using cosine-latitude area weighting.

## What Changed

| File | Change |
|------|--------|
| [src/WA/visualization/coarse_scale.py](/Users/mac/Code/WA/src/WA/visualization/coarse_scale.py) | Added `area_weighted_mean_to_regular_grid()` plus supporting helpers for regular 0.25 degree aggregation from fine lat/lon surfaces. |
| [scripts/plot_tropical_wetland_025deg.py](/Users/mac/Code/WA/scripts/plot_tropical_wetland_025deg.py) | New script to load non-GWD30 datasets, compute tropical annual mean wetland fraction, aggregate to 0.25 degree, and save both PNG and NetCDF. |
| [tests/test_visualization/test_coarse_scale.py](/Users/mac/Code/WA/tests/test_visualization/test_coarse_scale.py) | Added tests for pass-through on already aligned grids and cosine-latitude weighted aggregation behavior. |

## Behavior

- Domain: tropical only (`-180, -23.5, 180, 23.5`)
- Resolution: `0.25°`
- Default target year: `2016`
- Berkeley override: `2019`
- Static datasets: use directly without year selection
- GWD30: explicitly skipped in this script
- Aggregation rule: cosine-latitude area-weighted mean, not plain cell-count mean

## Verification

- `python -m pytest tests/test_visualization/test_coarse_scale.py -q` -> `19 passed`
- `python -m py_compile scripts/plot_tropical_wetland_025deg.py` -> passed
- `python -m pytest tests/` -> `307 passed`

## Notes

1. The script currently skips datasets that produce no valid cells for the requested target year; this may happen for datasets without 2016 coverage.
2. Output files are written per dataset as both `.png` and `.nc`, making HPC validation easier before building any multi-panel figure.
