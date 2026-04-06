# 2026-04-06-004 Phase4 GWD30 Pixel Stats Submit Script

## Summary

- Added `scripts/submit_phase4_gwd30_pixel_stats.sh`.
- The script submits one SLURM job per `gwd30` year for
  `scripts/build_phase4_gwd30_pixel_stats.py`.
- Years are discovered from `config/datasets.yaml` and can be filtered with
  `--years`.

## Key Files

- [scripts/submit_phase4_gwd30_pixel_stats.sh](/Users/mac/Code/WA/scripts/submit_phase4_gwd30_pixel_stats.sh)
- [tests/test_submit_phase4_gwd30_pixel_stats.py](/Users/mac/Code/WA/tests/test_submit_phase4_gwd30_pixel_stats.py)
- [CHANGELOG.md](/Users/mac/Code/WA/CHANGELOG.md)

## Verification

- `bash -n scripts/submit_phase4_gwd30_pixel_stats.sh`
- `python -m pytest tests/test_submit_phase4_gwd30_pixel_stats.py -q`
- `ruff check tests/test_submit_phase4_gwd30_pixel_stats.py`
- `python -m pytest tests/`

## HPC Example

```bash
bash scripts/submit_phase4_gwd30_pixel_stats.sh \
  --aggregation monthly \
  --worker-count 1 \
  --cpus 1 \
  --time 480 \
  --partition C064M0256G \
  --no-skip
```
