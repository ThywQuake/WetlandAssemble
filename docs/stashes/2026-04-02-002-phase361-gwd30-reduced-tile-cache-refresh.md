# Phase 3.6.1 GWD30 Reduced Tile Cache Refresh

**Date:** 2026-04-02
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** 已修复一个真实的 `stage -> cache` 链路问题：Phase 3.6 在 `prefer_cache=True` 时会静默复用旧 reduced tiles，即使对应 staged tile 已更新。

## Key Changes

| File | Change |
|------|--------|
| `src/WA/loaders/gwd30.py` | 为 transformed tile 增加 staged source 指纹（`source_stage_path` / `source_stage_size` / `source_stage_mtime_ns`），并在 `transform_staged_time_fraction_tiles(...)` 里只复用仍与当前 staged tile 一致的 reduced tile；不一致时自动删除并重建 |
| `tests/test_loaders/test_gwd30.py` | 新增回归测试，覆盖 staged tile 更新后 reduced tile 在 `skip_existing=True` 下必须刷新，而不是继续复用旧结果 |
| `CHANGELOG.md` | 记录这次 Phase 3.6 GWD30 reduced-tile cache 刷新修复 |

## Verification

- `ruff check src/WA/loaders/gwd30.py tests/test_loaders/test_gwd30.py` → passed
- `python -m pytest tests/test_loaders/test_gwd30.py -k "transform_staged_time_fraction_tiles" -q` → `2 passed`
- `python -m pytest tests/test_phase3_6_analysis.py -q` → `16 passed`
- `python -m pytest tests/` → `386 passed`

## Current Assessment

- 这说明 Phase 3.6.1 里观察到的 `raw/staged` 与 `reduced/final` 偏差，至少有一部分确实可能来自旧 reduced tile 被静默复用。
- 这次修复后，再重跑 Phase 3.6，才能继续判断是否还存在第二层数学/空间累计问题。

## Next Step

先在 HPC 重新跑一次 Phase 3.6 全局缓存重建，确认 hotspot 是否明显收敛；如果仍异常，再继续深挖 `_write_global_gwd30_phase36_caches(...)` 中的 stripe 累加与 `weighted_sum / coverage_sum`。
