# 2026-04-04-001 Phase 3.7 Raw Panel Four Legends

## Summary

- Clarified the raw hotspot 2x3 panel legend model.
- In raw mode, the three source datasets use three independent source-class
  systems, so the panel now shows four separate classification legends:
  - `Unified Majority`
  - `G2017`
  - `GLWD v2`
  - `GWD30`
- `Entropy` remains on its own colorbar and is no longer visually conflated
  with the class legends.

## Code

- `/Users/mac/Code/WA/src/WA/visualization/phase37.py`
  - Reworked raw-mode legend layout into two rows.
  - Added an explicit regression path that ensures all four class legends are
    drawn independently.
- `/Users/mac/Code/WA/tests/test_phase3_7_hotspot_panels.py`
  - Added a test that captures raw-mode legend draw calls and verifies the
    four expected legend titles.

## Verification

- `ruff check src/WA/visualization/phase37.py tests/test_phase3_7_hotspot_panels.py`
- `python -m pytest tests/test_phase3_7_hotspot_panels.py -q`
- `python -m pytest tests/`

## HPC

```bash
python scripts/plot_phase3_7_hotspot_panels.py \
  --hotspots-manifest results/phase3.7_hotspots/phase3_7_hotspots_2016.json \
  --s2-artifacts-manifest results/phase3.7_hotspots/phase3_7_s2_artifacts_2016_20160701.json \
  --input-dir results/phase3.6 \
  --output-dir results/figures/phase3.7_hotspots \
  --year 2016 \
  --dpi 300
```
