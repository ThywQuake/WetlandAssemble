# 2026-03-28 002 GWD30 Stage Lock Reclaim

## Context

After introducing sharded `GWD30` stage jobs, HPC logs showed messages like:

- `GWD30 staged tile already claimed elsewhere, skipping ...`
- plus occasional `RasterioIOError` on individual tiles

The lock message should only happen when another live process is genuinely writing
the same staged tile. In practice, a previous aborted shard run can leave a stale
`.lock` file behind and incorrectly block the next run.

## What changed

- Added stale-lock detection for GWD30 staged tile locks.
- If `.tile_*.nc.lock` is older than six hours, the next claimant logs a warning and
  reclaims it automatically.

## Files

- `src/WA/loaders/gwd30.py`
- `tests/test_loaders/test_gwd30.py`

## Validation

- `python -m py_compile src/WA/loaders/gwd30.py tests/test_loaders/test_gwd30.py`
- `ruff check src/WA/loaders/gwd30.py tests/test_loaders/test_gwd30.py`
- `python -m pytest tests/test_loaders/test_gwd30.py tests/test_submit_gwd30_sharded.py tests/test_submit_standardize.py -q`

## Notes

- This addresses stale lock leftovers, not real concurrent duplication or bad source
  TIFF reads.
- `RasterioIOError` warnings on specific tiles remain a separate Lustre/source I/O
  issue and may still need retries or source validation if persistent.
