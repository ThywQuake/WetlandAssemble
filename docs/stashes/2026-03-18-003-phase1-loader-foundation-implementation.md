# 2026-03-18 Phase 1 Loader Foundation Implementation

## Architecture decisions

- Phase 1 implementation stays scoped to loader foundation work only; Phase 2-5 comparison, trend, and GEE modules remain unimplemented.
- `config/` remains read-only. `src/WA/config.py` only loads and validates YAML input documents.
- All dataset loaders share one `DatasetLoader` contract and `DatasetMetadata` model in `src/WA/loaders/base.py`.
- Registry resolution is driven by `loader_type`, with `lstm_wetland` rejected explicitly as out of scope.
- Static raster loaders normalize to WGS84-backed `lat`/`lon` coordinates; dynamic loaders reconstruct or preserve time coordinates before shared subsetting.
- GWD30 currently satisfies the plan’s "virtual access" need by filtering candidate tiles and merging selected rasters into a year-wise virtual mosaic after reprojection, rather than shelling out to `gdalbuildvrt`.

## Modified files and key changes

- `pyproject.toml`
  Added runtime geospatial dependencies plus `pytest`, `ruff`, and `mypy` tooling config.
- `src/WA/config.py`
  Added dataset/GEE config loaders and `AppConfig`.
- `src/WA/loaders/base.py`
  Added loader contract, metadata model, shared bbox/time helpers.
- `src/WA/loaders/registry.py`
  Added loader registration, instantiation, and out-of-scope handling.
- `src/WA/loaders/_shared.py`
  Added raster/time helper utilities.
- `src/WA/loaders/berkeley.py`
  Added Berkeley monthly filename time parsing and loading.
- `src/WA/loaders/netcdf_generic.py`
  Added GIEMS-MC/WAD2M loading with variable normalization and flag masking.
- `src/WA/loaders/swamps.py`
  Added pre/post-2000 filename workflow handling.
- `src/WA/loaders/topmodel.py`
  Added dynamic config/forcing discovery and month-index reconstruction.
- `src/WA/loaders/g2017.py`
  Added multi-file static GeoTIFF bundle loading.
- `src/WA/loaders/glwd.py`
  Added combined-class plus area-by-class loading with scale factors.
- `src/WA/loaders/gwd30.py`
  Added year/tile discovery, bbox filtering, four-day timestamp reconstruction, and merged access.
- `tests/test_config.py`
  Added config loading validation tests.
- `tests/test_loaders/*`
  Added synthetic tests for registry and every Phase 1 loader.
- `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md`
  Checked off Phase 1 implementation items and the current quality-gate item.
- `todos/001-complete-p1-phase1-loader-foundation.md`
  Closed the Phase 1 todo with verification notes.

## Verification status

- `uv sync --extra dev`: pass
- `uv run pytest -q`: pass (`12 passed`)
- `uv run ruff check .`: pass
- `uv run mypy src tests`: pass

## Open risks, TODOs, rollback notes

- Runtime warning observed during some NetCDF-backed tests:
  `numpy.ndarray size changed, may indicate binary incompatibility`
  The suite still passes, but dependency updates should re-check this warning.
- The current GWD30 implementation uses in-process merged access rather than a persisted `.vrt` artifact. If real HPC-scale runs show performance or memory pressure, that is the first place to harden.
- No comparison, trend, GEE download, manifest, or results workflow code exists yet. Phase 2 should start from harmonization and rough binary comparison, not from more loader work.
- `docs/` is ignored by the current `.gitignore`, so any future commit that must include stash/plan changes will need explicit staging.
