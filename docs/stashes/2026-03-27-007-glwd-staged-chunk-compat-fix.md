# GLWD staged chunk 兼容性修复

**Date:** 2026-03-27  
**Branch:** `refactor/loader-reference-grid-alignment`  
**Status:** 已修复 `glwd_v2` merge 阶段因复用旧格式 staged chunk 导致的 `combine_by_coords` 失败

## Root Cause

- 某些旧的 staged chunk 文件虽然还能打开，但不满足当前 merge 约定：缺少当前 reference grid 期望的空间维坐标（如 `lat/lon`）
- `skip_existing` 之前只校验“文件存在/可读”，不会识别这类“可读但结构不兼容”的旧 chunk
- 因此 merge 时 `xr.open_mfdataset(..., combine=\"by_coords\")` 无法从这些 chunk 推断拼接顺序，报：
  - `Could not find any dimension coordinates to use to order the Dataset objects for concatenation`

## Key Changes

| File | Change |
|------|--------|
| `src/WA/standardize.py` | 新增 `_is_valid_staged_chunk()`，校验 staged chunk 是否包含当前 reference grid 所需的空间维与维坐标 |
| `src/WA/standardize.py` | `skip_existing` 复用 staged chunk 时，遇到“可读但不兼容”的 chunk 会自动重建 |
| `src/WA/standardize.py` | `_merge_staged_chunks()` 现在会在 `combine_by_coords` 失败时额外定位这类不兼容 chunk，并给出更明确错误 |
| `tests/test_standardize.py` | 新增“缺少空间维坐标的旧 chunk 会自动重建”回归测试 |

## Verification

- `python -m pytest tests/` → `229 passed`
- `ruff check src/WA/standardize.py tests/test_standardize.py` → passed
- `python -m py_compile src/WA/standardize.py tests/test_standardize.py` → passed

## HPC Retry

同步代码后，直接重跑：

```bash
cd ~/repos/WA2
bash scripts/submit_standardize.sh glwd_v2
```

## Notes

- 这次不需要手动清空整个 `_staging/glwd_v2`
- 如果旧 staging 里真有不兼容 chunk，日志会提示它们 “unreadable or incompatible, rebuilding”
