# 2026-03-28 014 Overlap Handoff And Local Skip Existing

## Context
- User observed that in overlap mode, completed files stayed inside `*.batch_*` directories and did not visibly move while rsync was expected to start.
- User also requested local skip-existing behavior to avoid redownloading already completed local files.

## Changes
- Updated overlap-mode handoff in `scripts/download_gwd30_local_then_rsync.py`:
  - batch downloads still land in `staging_root.batch_*`
  - once a batch is closed and ready to sync, completed files are moved back into the canonical `staging_root`
  - rsync then always uploads from `staging_root`
- This keeps `batch_*` directories as temporary download buffers only.
- Added local skip-existing across **all** transfer roots, not just `staging_root`:
  - `staging_root`
  - any leftover `staging_root.batch_*`
- If a matching local file already exists with the expected size, the task is counted as already staged and skipped.

## Why
- The handoff makes overlap behavior easier to reason about operationally:
  - batch buffer fills
  - files are handed off to staging
  - staging is what rsync drains
- The broader skip-existing logic avoids duplicate downloads after interrupted runs that left valid files inside old batch roots.

## Validation
- `python -m py_compile scripts/download_gwd30_local_then_rsync.py tests/test_download_gwd30_local_then_rsync.py`
- `ruff check scripts/download_gwd30_local_then_rsync.py tests/test_download_gwd30_local_then_rsync.py`
- `python -m pytest tests/test_download_gwd30_local_then_rsync.py -q`
- `python -m pytest tests/ -q`
