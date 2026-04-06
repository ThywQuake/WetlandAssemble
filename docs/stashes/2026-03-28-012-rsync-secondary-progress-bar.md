# 2026-03-28 012 Rsync Secondary Progress Bar

## Context
- User asked whether the local download + rsync workflow could show a concurrent progress bar for rsync as well.
- The script already had a download progress bar via `tqdm`.
- Rsync was previously executed with `subprocess.run(..., capture_output=True)`, so transfer progress was invisible.

## Changes
- Updated `scripts/download_gwd30_local_then_rsync.py` so `rsync_staging_root()` now uses `subprocess.Popen(...)` and reads merged stdout/stderr incrementally.
- Added `--info=progress2` to the rsync command.
- Added `_parse_rsync_progress_bytes()` to parse rsync `progress2` byte counters such as:
  - `123,456  78% ...`
- Added a second `tqdm` bar for rsync:
  - download bar uses `position=0`
  - rsync bar uses `position=1` in overlap mode
  - serial rsync uses `position=0`
- Switched `_announce()` to `tqdm.write(...)` so log lines do not corrupt active progress bars.

## Notes
- The rsync progress bar tracks bytes for the current rsync invocation, not the entire run.
- Only one rsync progress bar is supported at a time because the overlap pipeline intentionally allows only one in-flight rsync.
- The parsed byte counter is capped to the known total bytes for the staged files in that rsync batch.

## Validation
- `python -m py_compile scripts/download_gwd30_local_then_rsync.py tests/test_download_gwd30_local_then_rsync.py`
- `ruff check scripts/download_gwd30_local_then_rsync.py tests/test_download_gwd30_local_then_rsync.py`
- `python -m pytest tests/test_download_gwd30_local_then_rsync.py -q`
- `python -m pytest tests/ -q`
