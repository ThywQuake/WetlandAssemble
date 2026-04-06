# 2026-04-04-003 Phase 3.6 GWD30 Worker Count Override

## Summary

- Added an explicit `--gwd30-worker-count` CLI argument to Phase 3.6.
- This allows HPC runs to raise GWD30 tile transform parallelism above the
  conservative automatic safe cap of 4 when the node has enough memory.
- Automatic behavior is unchanged when the flag is omitted.

## Code

- `/Users/mac/Code/WA/scripts/run_phase3_6_global_entropy.py`
  - Added `--gwd30-worker-count`.
- `/Users/mac/Code/WA/src/WA/comparison/phase36.py`
  - Added `gwd30_worker_count` to `run_phase36_analysis(...)`.
  - Passed the worker count into GWD30 reduced-tile transform stage.
- `/Users/mac/Code/WA/src/WA/loaders/gwd30.py`
  - `_resolve_stage_worker_count(...)` now respects explicit user overrides,
    while still keeping the old automatic cap behavior when no explicit count
    is provided.

## Verification

- `ruff check src/WA/loaders/gwd30.py src/WA/comparison/phase36.py scripts/run_phase3_6_global_entropy.py tests/test_loaders/test_gwd30.py tests/test_phase3_6_analysis.py`
- `python -m pytest tests/test_loaders/test_gwd30.py tests/test_phase3_6_analysis.py -q`
- `python -m pytest tests/`

## HPC Examples

Conservative first try:

```bash
python scripts/run_phase3_6_global_entropy.py \
  --standardized-dir ~/Wetland_Assemble/data/standardized \
  --output-dir results/phase3.6 \
  --cache-dir results/cache/phase3_6 \
  --year 2016 \
  --lat-chunk-size 1024 \
  --gwd30-worker-count 8 \
  --no-prefer-cache
```

If memory remains comfortable, try:

```bash
python scripts/run_phase3_6_global_entropy.py \
  --standardized-dir ~/Wetland_Assemble/data/standardized \
  --output-dir results/phase3.6 \
  --cache-dir results/cache/phase3_6 \
  --year 2016 \
  --lat-chunk-size 1024 \
  --gwd30-worker-count 12 \
  --no-prefer-cache
```
