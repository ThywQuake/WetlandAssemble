# Phase 3.6 GWD30 Tile-Reduce Handoff

**Date:** 2026-03-31
**Branch:** `refactor/loader-reference-grid-alignment`
**Commit Range:** `unknown`
**Status:** Phase 3.6 已从 GWD30 全局 staged merge 改为 tile-reduce + stripe merge，本地验证通过；尚待同步到 HPC 复跑确认。

---

## Key Changes

| File | Change |
|------|--------|
| `src/WA/comparison/phase36.py` | Phase 3.6 改为只对 `g2017`/`glwd_v2` 写 unified fraction cache；GWD30 改为基于 reduced tile 生成 `valid_mask` 和 `dominant_class` |
| `src/WA/loaders/gwd30.py` | 新增 `transform_staged_time_fraction_tiles(...)`，支持对 staged `tile_*.nc` 做 tile-local 自定义变换，复用多进程 + lock + 原子 rename |
| `src/WA/loaders/gwd30.py` | 新增 `phase36_reduce_staged_time_fraction_tile(...)`，将单 tile 的 `(time, class, y, x)` 压缩为 `annual_unified_weighted_sum(8, y, x)` 与 `annual_coverage_sum(y, x)` |
| `tests/test_phase3_6_analysis.py` | 更新 Phase 3.6 测试为新的 GWD30 cache builder 口径 |
| `tests/test_loaders/test_gwd30.py` | 新增 staged tile transform API 的回归测试 |
| `docs/stashes/2026-03-31-020-phase36-gwd30-tile-reduce-plan.md` | 记录 tile-reduce 设计方案 |
| `docs/stashes/2026-03-31-021-phase36-gwd30-tile-reduce-implementation.md` | 记录 tile-reduce 实现细节与 HPC 口径 |

## Verification

- pytest: `python -m pytest tests/test_phase3_6_analysis.py tests/test_loaders/test_gwd30.py -q` → `38 passed`
- pytest: `python -m pytest tests/ -q` → `352 passed`
- ruff: `ruff check src/WA/comparison/phase36.py src/WA/loaders/gwd30.py tests/test_phase3_6_analysis.py tests/test_loaders/test_gwd30.py scripts/run_phase3_6_global_entropy.py` → clean
- HPC: 旧版在 `merge_staged_time_fraction_tiles()` 上因全局 `reindex` 触发 `numpy._core._exceptions._ArrayMemoryError`；新 tile-reduce 方案尚未复跑

## Open Risks / TODOs

- 还未在 HPC 上验证新 tile-reduce 路径的真实内存占用与运行时长
- 若 HPC 节点内存仍紧张，需要把 `--lat-chunk-size` 从 `512` 下调到 `256`
- `project_phase_status.md` 尚未更新 Phase 3.6 当前状态

## Next Steps

1. 本地同步代码到 HPC：`cd ~/Code/WA && bash .claude/skills/sync-hpc/sync_up.sh`
2. HPC 复跑：`python scripts/run_phase3_6_global_entropy.py --standardized-dir ~/Wetland_Assemble/data/standardized --output-dir results/phase3.6 --cache-dir results/cache/phase3_6 --year 2016 --lat-chunk-size 512`
3. 若仍有内存压力，改用 `--lat-chunk-size 256`
4. 若 HPC 新日志出现异常，继续基于 `tile-reduce` 路径调优
