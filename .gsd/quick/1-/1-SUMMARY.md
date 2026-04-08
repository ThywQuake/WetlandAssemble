# Quick Task: 两个都做

**Date:** 2026-04-07
**Branch:** gsd/quick/1-

## What Changed
- Added `scripts/submit_phase4_gwd30_regional_year_split.sh` to submit one `run_phase4_regional.py` job per selected year for `gwd30` and one dependent merge job.
- Updated the Phase 4 test-family catalog and changed-path selector so the new submit script maps into the `phase4` related-test subset.
- Recorded the year-split / merge workflow in `CHANGELOG.md` and `docs/stashes/2026-04-07-012-phase4-gwd30-year-split-regional-cache-merge.md`.

## Files Modified
- `CHANGELOG.md`
- `docs/testing/test-categories.md`
- `docs/stashes/2026-04-07-012-phase4-gwd30-year-split-regional-cache-merge.md`
- `scripts/submit_phase4_gwd30_regional_year_split.sh`
- `src/WA/test_selection.py`
- `tests/test_submit_phase4_gwd30_regional_year_split.py`
- `.gsd/quick/1-/1-SUMMARY.md`

## Verification
- `ruff check src/WA/test_selection.py tests/test_submit_phase4_gwd30_regional_year_split.py tests/test_test_selection.py`
- `bash -n scripts/submit_phase4_gwd30_regional_year_split.sh`
- `python -m pytest tests/test_submit_phase4_gwd30_regional_year_split.py tests/test_test_selection.py -q`
- `python scripts/run_related_tests.py scripts/submit_phase4_gwd30_regional_year_split.sh`
