# Phase 1.1 Loader Refactor Summary

**Date:** 2026-03-30
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** Phase 1.1 core refactor landed for standardized-source and raw-source loaders; GWD30 TileNC remains intentionally deferred to a dedicated follow-up.

## What Changed

| Area | Change |
|------|--------|
| Loader architecture | Added `standardized_netcdf` loader for pre-standardized annual/static netCDF datasets. |
| Standardized access | Reworked [`src/WA/standardized_loader.py`](/Users/mac/Code/WA/src/WA/standardized_loader.py) to resolve annual files, span multi-year windows, and lazily concatenate time series. |
| Config | Switched Berkeley / G2017 / GLWD v2 / TOPMODEL in [`config/datasets.yaml`](/Users/mac/Code/WA/config/datasets.yaml) to standardized-source configuration under `~/Wetland_Assemble/data/standardized`. |
| Classification logic | Added [`src/WA/classification.py`](/Users/mac/Code/WA/src/WA/classification.py) to load `classification_mappings.yaml` and derive wetland/water class masks from YAML instead of hardcoded tables. |
| Binary harmonization | Updated [`src/WA/comparison/harmonize.py`](/Users/mac/Code/WA/src/WA/comparison/harmonize.py) to support standardized `frac_*` classification datasets directly and exclude waterbody from wetland fraction. |
| Coarse-scale extraction | Updated [`src/WA/visualization/coarse_scale.py`](/Users/mac/Code/WA/src/WA/visualization/coarse_scale.py) plus `plot_global*.py` to use YAML-driven wetland class extraction so water is not counted as wetland. |

## Verification

- `ruff check src/WA/classification.py src/WA/standardized_loader.py src/WA/loaders/standardized_netcdf.py src/WA/loaders/base.py src/WA/loaders/__init__.py src/WA/comparison/harmonize.py tests/test_classification.py tests/test_comparison/test_harmonize.py tests/test_loaders/test_registry.py tests/test_loaders/test_standardized_netcdf.py tests/test_standardized_loader.py` -> clean
- `python -m pytest tests/` -> `305 passed`
- `python -m py_compile scripts/plot_global.py scripts/plot_global_v2.py` -> passed

## Open Risks / TODOs

1. GWD30 is still on the legacy/specialized loader path. TileNC + manifest-driven on-demand loading was not implemented in this step.
2. `src/WA/visualization/coarse_scale.py` and the `plot_global*.py` scripts still contain broader historical lint debt outside the refactor core; functionality was verified, but full lint cleanup was not part of this pass.
3. `config/datasets.yaml` now represents analysis-time access for Berkeley / G2017 / GLWD v2 / TOPMODEL. If a future task needs raw-to-standardized regeneration for those datasets, that workflow should use a dedicated raw-source config instead of assuming `datasets.yaml` still points at raw inputs.

## Next Steps

1. Create a dedicated GWD30 TileNC config contract: manifest location, tile-partial root, supported read modes, and required metadata checks.
2. Implement a GWD30 on-demand loader that resolves `bbox + year + reference_grid` against manifest-indexed tiles instead of annual merged netCDF.
3. Route any GWD30 coarse-scale workflow through that dedicated loader, including optional “pre-resample to 0.25deg then compute” paths.
