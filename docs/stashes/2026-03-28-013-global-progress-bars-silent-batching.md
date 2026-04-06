# 2026-03-28 013 Global Progress Bars Silent Batching

## Context
- User requested that progress bars should show overall run progress rather than restarting per batch.
- Batching should remain internal and quiet in the background.

## Changes
- Reworked `scripts/download_gwd30_local_then_rsync.py` so progress is now tracked globally:
  - `Download` bar: total pending files for the whole run
  - `Rsync` bar: total bytes planned for transfer across the whole run
- Removed per-batch `tqdm` download bars from `_download_batch()`.
- Kept batching logic for:
  - local disk control
  - overlap mode isolation
  - retry/recovery behavior
- Kept batch directories in overlap mode, but they are now internal implementation detail rather than user-facing progress units.

## Rsync Total Logic
- Known-size CSV tasks contribute their `expected_size_bytes` to the initial rsync total.
- Pre-existing staged files contribute their actual on-disk size.
- Legacy txt tasks with unknown target size reserve rsync total dynamically right before their batch is transferred.

## UX Result
- Frontend output now stays stable:
  - one cumulative `Download` bar
  - one cumulative `Rsync` bar
- Background batching no longer creates a new visible progress bar per batch.

## Validation
- `python -m py_compile scripts/download_gwd30_local_then_rsync.py tests/test_download_gwd30_local_then_rsync.py`
- `ruff check scripts/download_gwd30_local_then_rsync.py tests/test_download_gwd30_local_then_rsync.py`
- `python -m pytest tests/test_download_gwd30_local_then_rsync.py -q`
- `python -m pytest tests/ -q`
