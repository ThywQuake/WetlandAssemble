# 2026-03-28 001 GWD30 Sharded SLURM Stage/Merge

## Context

`GWD30` remained the dominant HPC bottleneck even after the earlier in-node OOM fix.
The expensive part is still the per-source-tile coarse staging step. One yearly job
was leaving too much cluster parallelism unused.

## What changed

### Loader-side sharding and atomic staging

- `GWD30Loader.stage_time_fraction_tiles(...)` now accepts
  `shard_index` / `shard_count` and deterministically assigns one subset of source
  tiles to one shard.
- Tile staging now uses a lock file plus temp-file write + `os.replace(...)` so
  concurrent shard jobs can safely share one `_staging/gwd30_<year>/tile_partials`
  directory.
- If another process already claimed a tile stage path, the loser skips it instead
  of racing the same output file.

### New dedicated shard runner

- Added `scripts/run_gwd30_stage_shard.py`
- Purpose: build the reference grid, stage one deterministic shard of GWD30 tile
  partials, and write a small JSON manifest for that shard.

### New dedicated HPC submit script

- Added `scripts/submit_gwd30_sharded.sh`
- Purpose: for each selected year
  1. submit one SLURM array job for `tile_partials`
  2. submit one dependent merge job that reuses the staged partials and runs the
     normal `standardize_datasets.py --datasets gwd30 --years <year>`

This keeps the special handling fully isolated to `GWD30`; no other dataset submit
path changed.

## Files

- `src/WA/loaders/gwd30.py`
- `scripts/run_gwd30_stage_shard.py`
- `scripts/submit_gwd30_sharded.sh`
- `tests/test_loaders/test_gwd30.py`
- `tests/test_submit_gwd30_sharded.py`

## Validation

- `python -m py_compile src/WA/loaders/gwd30.py scripts/run_gwd30_stage_shard.py tests/test_loaders/test_gwd30.py tests/test_submit_gwd30_sharded.py`
- `bash -n scripts/submit_gwd30_sharded.sh`
- `ruff check src/WA/loaders/gwd30.py scripts/run_gwd30_stage_shard.py tests/test_loaders/test_gwd30.py tests/test_submit_gwd30_sharded.py`
- `python -m pytest tests/test_loaders/test_gwd30.py tests/test_submit_gwd30_sharded.py tests/test_submit_standardize.py -q`
- `python -m pytest tests/ -q`

## Intended HPC usage

Example:

```bash
cd ~/repos/WA2
bash scripts/submit_gwd30_sharded.sh --years 2022
```

Useful knobs:

- `--stage-shards N`
- `--stage-cpus N`
- `--stage-time MINUTES`
- `--merge-cpus N`
- `--merge-time MINUTES`
- `--bbox W S E N`
- `--no-skip-existing`

## Notes

- The dependent merge job still uses the existing yearly standardization path, so it
  remains compatible with the current output/staging contract.
- Stage manifests are written under `_staging/gwd30_<year>/` for debugging and audit,
  but correctness depends on the staged `.nc` files, not the manifest JSON.
