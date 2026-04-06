# 2026-03-29 GWD30 Manifest-Indexed Merge

## Context

GWD30 merge 阶段此前的主要问题不是数值计算，而是每个 chunk 都线性扫描全部 staged tile partials。既然 stage shard 已经把 `(path, bbox)` 写进 `stage_shard_*.json`，merge 应直接复用这些 bbox，而不是重新发现源 TIFF 或退回全量 tile 扫描。

## What changed

- `src/WA/standardize.py`
  - 新增 `_load_gwd30_staged_tiles_from_stage_shard_manifests()`，从 `_staging/gwd30_YYYY/stage_shard_*.json` 聚合并去重 staged tile+bbox 元数据。
  - `skip_existing` 场景下，`_standardize_gwd30()` 优先从 shard manifest 恢复 staged tiles，不再默认回到原始 tile 发现路径。
  - 在 chunk merge 前预热 loader 侧 staged-tile spatial index。
- `src/WA/loaders/gwd30.py`
  - 恢复并实际使用 staged-tile grid-hash spatial index。
  - 新增 `prepare_staged_tile_merge_index()` 与 `_candidate_staged_tiles_for_merge()`。
  - `merge_staged_time_fraction_tiles()` 不再对“无匹配 bbox 的 chunk” fallback 到全量 staged tiles，而是直接抛 `FileNotFoundError`，让 chunk 走正常 skip 路径。
- `scripts/standardize_gwd30.py`
  - `--skip-stage` 改为从 shard manifests 恢复真实 bbox，不再使用伪造 `(0,0,0,0)`。

## Validation

- `python -m pytest tests/test_loaders/test_gwd30.py tests/test_standardize.py -q`
- `ruff check src/WA/loaders/gwd30.py src/WA/standardize.py scripts/standardize_gwd30.py tests/test_loaders/test_gwd30.py tests/test_standardize.py`

## Residual risk

- 最终年度 pack 仍走 `_merge_staged_chunks()` + `xr.open_mfdataset(...)`；这一步还没有改成 streaming/region-write 模式。
- `stage_shard_*.json` 恢复路径当前主要在 `skip_existing` / `--skip-stage` 场景启用；如果以后需要显式“merge-only” CLI，建议再补独立脚本。
