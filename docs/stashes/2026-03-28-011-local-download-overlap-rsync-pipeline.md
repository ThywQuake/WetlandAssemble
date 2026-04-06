# 2026-03-28 011 Local Download Overlap Rsync Pipeline

## Context
- User asked whether local download and rsync upload could overlap because rsync itself also takes noticeable time.
- Directly rsyncing a directory while download workers are still writing into it is unsafe because partially written files may be transferred.

## Changes
- Added `--overlap-rsync` to `scripts/download_gwd30_local_then_rsync.py`.
- When enabled, the script uses per-batch staging roots:
  - `.../local_rsync_buffer.batch_00001`
  - `.../local_rsync_buffer.batch_00002`
  - etc.
- Batch `N` downloads into its own isolated local buffer.
- After batch `N` download completes, its buffer is handed to a background rsync worker.
- The main thread immediately starts downloading batch `N+1` into a different buffer while batch `N` is syncing.
- The pipeline depth is intentionally bounded to one in-flight rsync plus one active download batch:
  - safer disk usage
  - simpler failure recovery
  - still overlaps the expensive network phases

## Recovery Behavior
- On startup, the script now scans both:
  - the legacy `staging_root`
  - any leftover `staging_root.batch_*` directories
- It removes stale `.part` files from all transfer roots.
- It rsyncs any pre-existing staged files before starting fresh downloads, so interrupted overlap runs resume cleanly.

## Validation
- `python -m py_compile scripts/download_gwd30_local_then_rsync.py tests/test_download_gwd30_local_then_rsync.py`
- `ruff check scripts/download_gwd30_local_then_rsync.py tests/test_download_gwd30_local_then_rsync.py`
- `python -m pytest tests/test_download_gwd30_local_then_rsync.py -q`
- `python -m pytest tests/ -q`
