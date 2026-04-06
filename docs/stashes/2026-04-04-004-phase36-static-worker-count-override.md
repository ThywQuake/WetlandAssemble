# 2026-04-04-004 Phase 3.6 Static Worker Count Override

## Summary

- Added an explicit `--static-worker-count` CLI argument to Phase 3.6.
- This allows the `g2017` and `glwd_v2` stage[01] global cache builds to run
  in parallel instead of always running serially.
- If the static worker pool fails on HPC, Phase 3.6 now logs the error and
  falls back to serial cache generation instead of aborting immediately.

## Code

- `/Users/mac/Code/WA/scripts/run_phase3_6_global_entropy.py`
  - Added `--static-worker-count`.
  - Passes the value into `run_phase36_analysis(...)`.
- `/Users/mac/Code/WA/src/WA/comparison/phase36.py`
  - Added `_write_global_static_phase36_caches_from_standardized(...)`.
  - `run_phase36_analysis(...)` now parallelizes pending static cache builds
    across `g2017` and `glwd_v2` when `static_worker_count > 1`.
  - Parallel static execution catches broad `Exception` and falls back to the
    serial path, matching the HPC error-handling requirement.
- `/Users/mac/Code/WA/tests/test_phase3_6_analysis.py`
  - Added coverage for:
    - successful static parallel dispatch
    - serial fallback when the static executor fails
    - CLI forwarding of both `static_worker_count` and `gwd30_worker_count`

## Verification

- `ruff check src/WA/comparison/phase36.py scripts/run_phase3_6_global_entropy.py tests/test_phase3_6_analysis.py`
- `python -m pytest tests/test_phase3_6_analysis.py -q`
- `python -m pytest tests/`

## HPC Example

Try both static and GWD30 parallelism together on the first rebuild:

```bash
python scripts/run_phase3_6_global_entropy.py \
  --standardized-dir ~/Wetland_Assemble/data/standardized \
  --output-dir results/phase3.6 \
  --cache-dir results/cache/phase3_6 \
  --year 2016 \
  --lat-chunk-size 1024 \
  --static-worker-count 2 \
  --gwd30-worker-count 8 \
  --no-prefer-cache
```

If that first rebuild succeeds, later reruns should usually drop
`--no-prefer-cache` and only rebuild when cache versions change.
