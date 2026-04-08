# VERIFY

## Branch
- `gsd/bugfix/traceback-most-recent-call-last-file-lus`

## Commit
- `33260ce` — `fix(phase4): fallback berkeley mask window before coverage`

## Verification run

### Targeted fix-phase checks
- `ruff check src/WA/comparison/phase4_regional.py tests/test_comparison/test_phase4_regional.py`
- `python -m pytest tests/test_comparison/test_phase4_regional.py -q`

Result:
- `23 passed, 1 warning`

### Related Phase 4 verification set
Selector:
- `python scripts/run_related_tests.py src/WA/comparison/phase4_regional.py`

Executed subset:
- `python -m pytest tests/test_comparison/test_phase4_regional.py tests/test_comparison/test_trends.py tests/test_comparison/test_trend_agreement.py tests/test_visualization/test_phase4.py tests/test_submit_phase4_gwd30_pixel_stats.py tests/test_submit_phase4_gwd30_regional_year_split.py tests/test_submit_phase4_gwd30_tropical_shards.py -q`

Result:
- `55 passed, 1 warning`

## Notes
- The remaining warning is the pre-existing pandas `FutureWarning` around `pd.concat(...)` in the year-cache merge path. It did not cause failures in this bugfix verification run.
- Per repository guidance, verification used the full related Phase 4 subset instead of `python -m pytest tests/`.
