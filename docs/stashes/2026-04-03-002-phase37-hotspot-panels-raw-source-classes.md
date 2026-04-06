## Phase 3.7 Hotspot Panels: Raw Source Classes

- Date: 2026-04-03
- Scope: `Phase 3.7` hotspot panel plotting only

### What Changed

- Hotspot selection logic stays unchanged:
  - still uses `Phase 3.6` unified dominant classes and entropy
  - still extracts hotspots from coarse harmonized classes
- Hotspot panel visualization now changes from unified per-dataset classes to
  raw/source classes:
  - `G2017` panel now shows source raw dominant class
  - `GLWD v2` panel now shows source raw dominant class
  - `GWD30` panel now shows annualized raw dominant class derived from
    standardized `frac_*` variables
- `Unified Majority` is kept as the coarse cross-dataset summary panel
- `GWD30` raw hotspot plotting no longer assumes a yearly standardized file
  like `gwd30_2016.nc`; it now restores staged tiles from
  `_staging/gwd30_<year>/stage_shard_*.json` and merges the hotspot AOI
  directly from staged `weighted` + `coverage`

### Legend Rules

- Unified majority legend only shows classes present in the current hotspot AOI
- Each raw dataset uses its own fixed, dataset-specific color mapping
- Raw legends only list the classes actually present in the current panel
- The same raw class keeps the same color across all hotspot panels for that dataset

### Code Touch Points

- `src/WA/classification.py`
  - added helpers for dataset display names and raw/source class names
- `src/WA/visualization/phase37.py`
  - added raw/source class styles
  - added AOI raw dominant-class extraction from standardized datasets
  - updated hotspot panel layout and per-dataset legends
- `scripts/plot_phase3_7_hotspot_panels.py`
  - added `--standardized-dir`
  - raw mode now prefers standardized source classes
- `tests/test_phase3_7_hotspot_panels.py`
  - updated tests to cover raw/source hotspot panel behavior

### Verification

- `ruff check src/WA/classification.py src/WA/visualization/phase37.py scripts/plot_phase3_7_hotspot_panels.py tests/test_phase3_7_hotspot_panels.py`
- `python -m pytest tests/test_phase3_7_hotspot_panels.py -q`

### HPC Reminder

- Replot hotspot panels with:
  - `python scripts/plot_phase3_7_hotspot_panels.py --hotspots-manifest ... --standardized-dir ... --input-dir results/phase3.6 --output-dir ... --year 2016 --dpi 300`
- On HPC, `GWD30` raw hotspot panels depend on staged tile manifests under:
  - `<standardized-dir>/_staging/gwd30_2016/stage_shard_*.json`
