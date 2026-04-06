# 2026-03-28 010 Local Download Rsync Sync.sh Alignment

## Context
- User asked to align `scripts/download_gwd30_local_then_rsync.py` with the rsync invocation style used by `sync.sh`.
- `sync.sh` delegates to `.claude/skills/sync-hpc/scripts/sync_up.sh`, which runs:
  - `/Users/mac/.ssh/script/with_pkuhpc_auth.sh rsync -avz ...`

## Changes
- Added `DEFAULT_RSYNC_WRAPPER = "/Users/mac/.ssh/script/with_pkuhpc_auth.sh"`.
- Added CLI option `--rsync-wrapper`, defaulting to the same wrapper used by `sync.sh`.
- Updated rsync execution to use:
  - `with_pkuhpc_auth.sh rsync -avz --remove-source-files --exclude=*.part <staging>/ <remote>`
- Kept `--remove-source-files` because this workflow uploads staged batches and clears local copies after successful transfer.
- Did **not** add `--delete` from `sync.sh` because this script syncs partial data batches into the remote GWD30 root; `--delete` would risk removing remote files not present in the current local batch.
- Did **not** add `--exclude-from=.gitignore` because this script syncs staged TIFF data rather than the repository tree, so repo ignore patterns are not the correct filter surface.

## Validation
- `python -m py_compile scripts/download_gwd30_local_then_rsync.py tests/test_download_gwd30_local_then_rsync.py`
- `ruff check scripts/download_gwd30_local_then_rsync.py tests/test_download_gwd30_local_then_rsync.py`
- `python -m pytest tests/test_download_gwd30_local_then_rsync.py -q`
- `python -m pytest tests/ -q`
