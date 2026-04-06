# 2026-04-05-001 Phase 3.6 GWD30 Source Dominant Wetland Priority

## Summary

- Fixed `gwd30_source_dominant_class` so it no longer uses a plain raw-class
  `argmax`.
- GWD30 raw/source dominance now follows the same annual selection policy as
  the unified GWD30 dominant class:
  - prefer wetland source classes first
  - then prefer water source classes
  - only fall back to non-wetland when neither wetland nor water is present

## Code

- `/Users/mac/Code/WA/src/WA/comparison/phase36.py`
  - Added `_compute_source_dominant_values(...)`.
  - `compute_source_dominant_class(...)` now uses the shared GWD30
    wetland-first source selection rule.
  - `compute_source_dominant_class_from_fractions(...)` now uses the same rule,
    so both direct standardized reads and reduced-tile aggregation agree.
  - Bumped `PHASE36_CACHE_VERSION` to `4` so stale pre-fix source-dominant
    caches are not silently reused.
- `/Users/mac/Code/WA/tests/test_phase3_6_analysis.py`
  - Added a regression that confirms a low-fraction wetland source class beats
    higher-fraction water and non-wetland source classes for GWD30 annual
    source dominance.
  - Added a regression that confirms the reduced-fraction path still prefers
    water over non-wetland when no wetland class is present.

## Verification

- `ruff check src/WA/comparison/phase36.py tests/test_phase3_6_analysis.py`
- `python -m pytest tests/test_phase3_6_analysis.py -q`
- `python -m pytest tests/`

## HPC Rerun

Because this changes the precomputed `gwd30_source_dominant_class`, rerun
Phase 3.6 and then redraw the hotspot panels.

Conservative rerun:

```bash
python scripts/run_phase3_6_global_entropy.py \
  --standardized-dir ~/Wetland_Assemble/data/standardized \
  --output-dir results/phase3.6 \
  --cache-dir results/cache/phase3_6 \
  --year 2016 \
  --lat-chunk-size 512 \
  --static-worker-count 1 \
  --gwd30-worker-count 4 \
  --no-prefer-cache
```

Then redraw hotspots:

```bash
python scripts/plot_phase3_7_hotspot_panels.py \
  --hotspots-manifest results/phase3.7_hotspots/phase3_7_hotspots_2016.json \
  --s2-artifacts-manifest results/phase3.7_hotspots/phase3_7_s2_artifacts_2016_20160701.json \
  --standardized-dir ~/Wetland_Assemble/data/standardized \
  --input-dir results/phase3.6 \
  --output-dir results/figures/phase3.7_hotspots \
  --year 2016 \
  --dpi 300
```
