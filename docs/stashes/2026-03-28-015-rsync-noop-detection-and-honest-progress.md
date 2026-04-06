# 2026-03-28 015 Rsync Noop Detection And Honest Progress

## Context
- User observed that the rsync progress bar jumped to the full planned byte total even when no visible transfer happened and source TIFF files remained in `staging_root`.
- This made it impossible to distinguish a real transfer from a zero-transfer/no-op rsync invocation.

## Root Cause
- `scripts/download_gwd30_local_then_rsync.py` previously treated:
  - `planned_bytes` for the current rsync batch
  - `actual transferred bytes`
  as equivalent on any `returncode == 0`.
- So if rsync exited successfully but transferred nothing, the progress bar still filled to the planned total.

## Changes
- `rsync_staging_root()` now computes:
  - planned source file count / bytes before rsync
  - remaining source file count / bytes after rsync
- Actual transfer is derived from what disappeared from the source directory:
  - `actual_transferred_files = planned_count - remaining_count`
  - `actual_transferred_bytes = planned_bytes - remaining_bytes`
- The rsync progress bar is no longer force-filled to the planned total just because rsync returned `0`.
- If rsync exits `0` but transfers `0` files, the script now logs:
  - `rsync exited 0 but transferred 0 files ... source files remain locally`

## Effect
- A successful-but-noop rsync now stays visually near zero instead of pretending success.
- Summary counters now reflect what actually left the local staging directory.

## Validation
- `python -m py_compile scripts/download_gwd30_local_then_rsync.py tests/test_download_gwd30_local_then_rsync.py`
- `ruff check scripts/download_gwd30_local_then_rsync.py tests/test_download_gwd30_local_then_rsync.py`
- `python -m pytest tests/test_download_gwd30_local_then_rsync.py -q`
- `python -m pytest tests/ -q`
