# GIEMS_MC / TOPMODEL open-once 标准化修复

**Date:** 2026-03-27  
**Branch:** `refactor/loader-reference-grid-alignment`  
**Status:** 已修复 `giems_mc` / `topmodel` 标准化时每个 chunk 反复打开源数据导致的超慢路径

## Root Cause

- 连续数据标准化原先走通用 per-chunk 路径：每个空间 chunk 都重新 `loader.load(bbox=chunk_bbox, time_range=year)` 一次
- `GIEMS_MC` 因此会对同一个大 NetCDF 单文件反复 `open_dataset`
- `TOPMODEL` 更糟：每个 chunk 都重新 discover 年文件、重新打开全部 config/forcing 组合，并重新拼接 time/config/forcing 维

## Key Changes

| File | Change |
|------|--------|
| `src/WA/loaders/netcdf_generic.py` | 新增 `open_time_series()`，支持对 GIEMS/WAD2M 这类单文件 NetCDF 懒加载打开一个时间窗口 |
| `src/WA/loaders/topmodel.py` | 新增 `open_time_series()`，一次性懒加载打开一个年份的全部 config/forcing TOPMODEL 文件并挂上统一 close 回调 |
| `src/WA/standardize.py` | `_standardize_continuous_yearly()` 现在优先走 loader 的 `open_time_series()`，实现“每年只打开一次源数据，再按 chunk 复用” |
| `tests/test_loaders/test_netcdf_generic.py` | 新增 `GIEMS_MC open_time_series()` 回归测试 |
| `tests/test_loaders/test_topmodel.py` | 新增 `TOPMODEL open_time_series()` 回归测试 |
| `tests/test_standardize.py` | 新增连续数据标准化优先使用 `open_time_series()` 而非 per-chunk `load()` 的回归测试 |

## Verification

- `python -m pytest tests/` → `228 passed`
- `ruff check src/WA/loaders/netcdf_generic.py src/WA/loaders/topmodel.py src/WA/standardize.py tests/test_loaders/test_netcdf_generic.py tests/test_loaders/test_topmodel.py tests/test_standardize.py` → passed
- `python -m py_compile src/WA/loaders/netcdf_generic.py src/WA/loaders/topmodel.py src/WA/standardize.py tests/test_loaders/test_netcdf_generic.py tests/test_loaders/test_topmodel.py tests/test_standardize.py` → passed

## HPC Retry

先同步代码，然后优先单年验证：

```bash
cd ~/repos/WA2
bash scripts/submit_standardize.sh --years 1993 --no-skip-existing giems_mc
bash scripts/submit_standardize.sh --years 2020 --no-skip-existing topmodel
```

## Notes

- 这次修的是最主要的重复 I/O / 重复文件发现问题
- `TOPMODEL` 现在不会再每个 chunk 重复 discover + reopen 全部文件，但由于仍保留 `config × forcing × time` 全维输出，单年产物和计算量依旧很重
- 如果 `TOPMODEL` 还是过慢，下一步应该改产品规格（例如 500m 只输出 ensemble mean / std），而不是再继续堆同一路径优化
