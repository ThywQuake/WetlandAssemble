# Phase 2.5 Tech Debt Fixes Summary

**Date:** 2026-03-22
**Branch:** feat/phase2-rough-binary-modis-truth
**Status:** COMPLETE - all 4 tasks done, 82/82 tests passing, ruff clean

## Changes

### Task 5: 提取 validation 共享下载工具模块
- **Created** `src/WA/validation/_download_utils.py` — 5 shared functions extracted
  - `download_file()`: atomic download with streaming + configurable timeout
  - `collection_size()`: GEE collection count
  - `format_date()`: timestamp → GEE date string
  - `month_window()`: target time → month boundaries
  - `classify_failure()`: exception → terminal status string
- **Modified** `src/WA/validation/modis_reference.py` — removed 5 duplicated privates, now imports from `_download_utils`
- **Modified** `src/WA/validation/landsat_reference.py` — same refactor

### Task 6: 修复 tqdm fallback crash
- **Modified** `src/WA/modis_batch.py` — added `set_postfix_str()` method to `_NoOpProgress` class

### Task 7: 统一 JSON 序列化参数
- **Modified** `src/WA/landsat_review_manifest.py` — added `sort_keys=True, allow_nan=False` to both manifest writers

### Task 8: 添加 scipy 依赖
- **Modified** `pyproject.toml` — added `scipy>=1.13` to dependencies, `scipy.*` to mypy overrides
- **Modified** `uv.lock` — resolved scipy 1.17.1

## Verification
- `uv run ruff check` → All checks passed
- `uv run pytest` → 82 passed, 1 warning
- `uv run python -c "import scipy"` → scipy 1.17.1 OK

## Next Steps
- Phase 3 实现已有 plan，可直接启动
