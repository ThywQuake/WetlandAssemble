# 2026-04-05-002 Phase 3.7 Hotspot Legend Labels And Order

## Summary

- Raw hotspot panel legends now append the class ID to each categorical label,
  so repeated names remain distinguishable inside one legend.
- Raw-mode legend layout was reordered to:
  - top row: `G2017`, `GLWD v2`, `GWD30`
  - bottom row: `Unified Majority`, `Entropy`

## Code

- `/Users/mac/Code/WA/src/WA/visualization/phase37.py`
  - Added `_legend_label_with_id(...)`.
  - `classification_style()` now formats unified legend labels as `Name ID`.
  - `source_class_style()` now formats raw/source legend labels as `Name ID`.
  - Raw-mode hotspot legend layout now places dataset legends first and moves
    `Unified Majority` to the second row beside `Entropy`.
- `/Users/mac/Code/WA/tests/test_phase3_7_hotspot_panels.py`
  - Updated the raw-mode legend ordering regression.
  - Added a regression that checks class labels include IDs in legend styles.

## Verification

- `ruff check src/WA/visualization/phase37.py tests/test_phase3_7_hotspot_panels.py`
- `python -m pytest tests/test_phase3_7_hotspot_panels.py -q`
- `python -m pytest tests/`

## HPC

Only the panel drawing changed, so you do not need to rerun Phase 3.6 or
hotspot selection for this. Just redraw the panels:

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
