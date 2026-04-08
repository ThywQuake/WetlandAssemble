# PR Draft

## Title
fix(phase4): fallback berkeley mask window before coverage

## Summary
Fix Phase 4 Berkeley valid-mask warm-up for year-split runs whose requested year predates standardized Berkeley coverage.

## Root cause
`_resolve_phase4_berkeley_mask_source_time_range()` assumed the requested analysis window must overlap standardized Berkeley files. That assumption is wrong for the Berkeley valid-mask path: it only needs one real Berkeley spatial footprint, not a year-matched analysis series. Year-split runs such as `2017` therefore failed with `FileNotFoundError` even though later Berkeley files were available.

## Fix
- Keep the current overlap-first behavior when the requested window does overlap Berkeley coverage.
- If there is no overlap, fall back to the earliest available standardized Berkeley file.
- Continue selecting only that file's first real time slice for valid-mask generation.
- Add a regression test covering the pre-coverage fallback path.

## Tests
- `ruff check src/WA/comparison/phase4_regional.py tests/test_comparison/test_phase4_regional.py`
- `python -m pytest tests/test_comparison/test_phase4_regional.py -q`
- `python scripts/run_related_tests.py src/WA/comparison/phase4_regional.py`
- `python -m pytest tests/test_comparison/test_phase4_regional.py tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_visualization/test_phase4.py tests/test_submit_phase4_gwd30_pixel_stats.py tests/test_submit_phase4_gwd30_regional_year_split.py tests/test_submit_phase4_gwd30_tropical_shards.py -q`

## HPC retry command
```bash
python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --region pan_trop_subtrop \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --start-year 2017 \
  --end-year 2017 \
  --no-skip
```
