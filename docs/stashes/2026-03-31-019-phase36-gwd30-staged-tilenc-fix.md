# Phase 3.6 GWD30 staged tileNC loader 修正

**Date:** 2026-03-31
**Status:** 已修正 Phase 3.6 对 GWD30 的读取层级：不再走原始 TIFF `load_time_fraction_grid(...)`，改为从 `standardized_dir/_staging/gwd30_<year>/stage_shard_*.json` 恢复 `tile_*.nc`，再调用 `merge_staged_time_fraction_tiles(...)`。

## 问题

- 之前的修复虽然绕开了 `StandardizedDataLoader`，但仍然读到了更底层的原始 TIFF。
- 这与当前项目约定不一致：Phase 3.6 应复用已经 stage 完成的 GWD30 coarse partial netCDF，而不是重新扫描 raw tiles。

## 本次修改

| File | Change |
|------|--------|
| `src/WA/comparison/phase36.py` | `load_phase36_inputs()` 传入 `standardized_dir` 到 GWD30 专用加载路径 |
| `src/WA/comparison/phase36.py` | `_load_phase36_gwd30()` 改为调用 `merge_staged_time_fraction_tiles(...)` |
| `src/WA/comparison/phase36.py` | 新增 `_load_phase36_gwd30_staged_tiles()`，从 `_staging/gwd30_<year>/stage_shard_*.json` 恢复 staged tile metadata |
| `tests/test_phase3_6_analysis.py` | 回归测试改为验证 Phase 3.6 走 staged-tile merge，而不是直接 mock 顶层 GWD30 helper |

## 当前预期目录

Phase 3.6 在 `--standardized-dir ~/Wetland_Assemble/data/standardized` 下会查找：

- `~/Wetland_Assemble/data/standardized/_staging/gwd30_2016/stage_shard_*.json`
- 这些 manifest 引用的 `tile_partials/tile_*.nc`

如果 manifest 缺失，当前会直接报错，而不是悄悄回退到 raw TIFF。

## Verification

- `ruff check src/WA/comparison/phase36.py tests/test_phase3_6_analysis.py scripts/run_phase3_6_global_entropy.py`
- `python -m pytest tests/test_phase3_6_analysis.py -q`
- `python -m pytest tests/ -q`

## HPC 提示

若 HPC 上仍报 GWD30 输入错误，先检查：

```bash
ls ~/Wetland_Assemble/data/standardized/_staging/gwd30_2016
ls ~/Wetland_Assemble/data/standardized/_staging/gwd30_2016/tile_partials | head
```

至少应能看到：

- `stage_shard_*.json`
- `tile_partials/tile_*.nc`
