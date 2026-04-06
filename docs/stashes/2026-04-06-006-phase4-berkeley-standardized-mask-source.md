# 2026-04-06-006 Phase4 Berkeley Standardized Mask Source

## Summary

- Corrected the Phase 4 Berkeley mask source back to the standardized loader path.
- `berkeley_rwawc` now follows `config/datasets.yaml` during Phase 4 analysis:
  `loader_type=standardized_netcdf`, `path=~/Wetland_Assemble/data/standardized`.
- The Phase 4 CLI no longer expects Berkeley raw-path overrides.

## Why

- Phase 1.1 loader refactor already moved Berkeley to standardized analysis-time access.
- The temporary Phase 4 raw-Berkeley override contradicted both the config contract
  and the earlier loader-refactor stash.

## Key Files

- [src/WA/comparison/phase4_regional.py](/Users/mac/Code/WA/src/WA/comparison/phase4_regional.py)
- [scripts/run_phase4_regional.py](/Users/mac/Code/WA/scripts/run_phase4_regional.py)
- [tests/test_comparison/test_phase4_regional.py](/Users/mac/Code/WA/tests/test_comparison/test_phase4_regional.py)
- [CHANGELOG.md](/Users/mac/Code/WA/CHANGELOG.md)

## Verification

- `ruff check src/WA/comparison/phase4_regional.py scripts/run_phase4_regional.py tests/test_comparison/test_phase4_regional.py`
- `python -m pytest tests/test_comparison/test_phase4_regional.py -q`
- `python -m pytest tests/`

## HPC Command

```bash
python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --start-year 2022 \
  --end-year 2022 \
  --no-skip
```
