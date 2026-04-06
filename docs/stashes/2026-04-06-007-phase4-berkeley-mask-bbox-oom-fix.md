# 2026-04-06-007 Phase4 Berkeley Mask BBox OOM Fix

## Summary

- Fixed the immediate OOM in Phase 4 regional runs that occurred before
  `gwd30` Stage 2 processing started.
- Root cause: Berkeley valid-mask construction opened the standardized Berkeley
  time series first and only applied the region bbox afterward.
- Fix: pass `bbox` directly into Berkeley `open_time_series(...)` so the loader
  reads only the requested region before materialization.

## Key Files

- [src/WA/comparison/phase4_regional.py](/Users/mac/Code/WA/src/WA/comparison/phase4_regional.py)
- [tests/test_comparison/test_phase4_regional.py](/Users/mac/Code/WA/tests/test_comparison/test_phase4_regional.py)
- [CHANGELOG.md](/Users/mac/Code/WA/CHANGELOG.md)

## Verification

- `ruff check src/WA/comparison/phase4_regional.py tests/test_comparison/test_phase4_regional.py`
- `python -m pytest tests/test_comparison/test_phase4_regional.py -q`
- `python -m pytest tests/`

## HPC Retry

```bash
python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --start-year 2013 \
  --end-year 2022 \
  --no-skip
```
