# 2026-04-04-005 Phase 3.6 Static Stripe Parallelism

## Summary

- Upgraded the Phase 3.6 static-dataset acceleration path from coarse
  dataset-level parallelism to a shared stripe-level worker pool.
- This means `GLWD v2` can now use more than one worker when
  `--static-worker-count` is greater than `2`, instead of being limited to a
  single process while `G2017` uses the other slot.
- The static parallel path still catches broad `Exception` and falls back to
  the serial cache builder on HPC.

## Code

- `/Users/mac/Code/WA/src/WA/comparison/phase36.py`
  - Added `Phase36StaticStripeResult`.
  - Added `_compute_static_phase36_stripe_from_standardized(...)` to compute a
    single `g2017` or `glwd_v2` stripe from standardized inputs.
  - Added `_write_global_static_phase36_caches_parallel(...)` to coordinate a
    shared worker pool across all pending static stripes and write results back
    to the stage[01] NetCDF caches in the main process.
  - `run_phase36_analysis(...)` now routes `--static-worker-count > 1` through
    this stripe-parallel path before falling back to the serial builder.

## Verification

- `ruff check src/WA/comparison/phase36.py tests/test_phase3_6_analysis.py scripts/run_phase3_6_global_entropy.py`
- `python -m pytest tests/test_phase3_6_analysis.py -q`

## HPC Example

To give `GLWD v2` more room to speed up, raise `--static-worker-count` above 2:

```bash
python scripts/run_phase3_6_global_entropy.py \
  --standardized-dir ~/Wetland_Assemble/data/standardized \
  --output-dir results/phase3.6 \
  --cache-dir results/cache/phase3_6 \
  --year 2016 \
  --lat-chunk-size 1024 \
  --static-worker-count 6 \
  --gwd30-worker-count 8 \
  --no-prefer-cache
```

If the node stays comfortable on CPU, memory, and I/O, try `--static-worker-count 8`.
