# g2017 staged chunk HDF error 修复

**Date:** 2026-03-27  
**Branch:** `refactor/loader-reference-grid-alignment`  
**Status:** 已修复 `standardize g2017` merge 阶段因复用损坏 staged chunk 导致的 NetCDF/HDF error

## Root Cause

- `skip_existing` 之前只按文件是否存在决定复用 staged chunk，不校验该 `.nc` 是否可读
- `_merge_staged_chunks()` 之前直接 `glob("chunk_*.nc")` 合并整个 `_staging` 目录
- 如果旧 run 留下截断/损坏 chunk，或 `_staging` 里残留脏 chunk，merge 就会在 `xr.open_mfdataset()` 时报 `NetCDF: HDF error`

## Key Changes

| File | Change |
|------|--------|
| `src/WA/standardize.py` | `_save_dataset()` 改成先写临时文件再 `os.replace()`，避免留下半写 netCDF |
| `src/WA/standardize.py` | 新增 staged chunk 可读性校验；`skip_existing` 复用前会自动检查坏 chunk 并重建 |
| `src/WA/standardize.py` | `_merge_staged_chunks()` 支持显式 chunk 清单，不再盲扫整个 `_staging` 目录 |
| `src/WA/standardize.py` | merge 遇到 HDF error 时会定位 unreadable chunk，并提示这是损坏 staging 文件 |
| `tests/test_standardize.py` | 新增“坏 chunk 自动重建”回归测试 |
| `tests/test_standardize.py` | 新增“merge 忽略 stray 脏 chunk”回归测试 |

## Verification

- `python -m pytest tests/` → `224 passed`
- `ruff check src/WA/standardize.py tests/test_standardize.py` → passed
- `python -m py_compile src/WA/standardize.py tests/test_standardize.py` → passed

## HPC Retry

同步代码后，直接重跑 `g2017` 即可；这次会复用好的 chunk，只重建坏的：

```bash
cd ~/repos/WA2
bash scripts/submit_standardize.sh g2017
```

## Notes

- 这次不需要粗暴删整个 `_staging/g2017`
- 如果日志里再次出现 unreadable chunk warning，说明旧 staging 确实有坏块，但现在会自动重建，不会在 merge 时才炸
