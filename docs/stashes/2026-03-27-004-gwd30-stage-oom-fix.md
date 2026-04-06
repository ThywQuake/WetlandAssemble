# GWD30 Stage OOM 修复

**Date:** 2026-03-27  
**Branch:** `refactor/loader-reference-grid-alignment`  
**Status:** 已修复 `standardize gwd30` 在 stage 阶段因进程间回传大数组导致的 OOM 主因

## Root Cause

- `stage_time_fraction_tiles()` 之前让每个 worker 先计算整块 `weighted/coverage` 大数组，再把结果回传主进程写 `.nc`
- 对 500m 粗网格下的全年 `GWD30` tile，这类返回值单 tile 就是数百 MB
- HPC 上把 `WA_STANDARDIZE_WORKERS=32` 直接映射到 32 个 stage worker 后，内存峰值和 IPC 缓冲都会失控，最终被 `oom_kill`

## Key Changes

| File | Change |
|------|--------|
| `src/WA/loaders/gwd30.py` | 新增 `_process_time_fraction_tile_to_stage_file()`，由 worker 直接写 staged partial `.nc`，只向主进程回传 `(stage_path, bbox)` 小元数据 |
| `src/WA/loaders/gwd30.py` | `stage_time_fraction_tiles()` 不再把 `weighted/coverage` 大数组从 worker 回传主进程 |
| `src/WA/loaders/gwd30.py` | 新增 `_resolve_stage_worker_count()`，将 GWD30 stage worker 数保守上限收紧到 `4`，避免按 CPU 数直接拉满导致 OOM |
| `tests/test_loaders/test_gwd30.py` | 新增 staged partial 直接写盘测试 |
| `tests/test_loaders/test_gwd30.py` | 新增 GWD30 stage worker cap 测试 |

## Verification

- `python -m pytest tests/test_loaders/test_gwd30.py -q` → `19 passed`
- `python -m pytest tests/` → `222 passed`
- `ruff check src/WA/loaders/gwd30.py tests/test_loaders/test_gwd30.py` → passed
- `python -m py_compile src/WA/loaders/gwd30.py tests/test_loaders/test_gwd30.py` → passed

## HPC Retry

先同步代码到 HPC，然后重跑单年验证：

```bash
cd ~/repos/WA2
bash scripts/submit_standardize.sh --years 2022 --no-skip-existing gwd30
```

## Notes

- 这次修复的是 stage OOM 主因，不是简单调大内存
- `plan` 阶段已有进度条；`stage` 阶段现在会更稳，但总体仍是重 I/O + 重重投影流程
- 如果后续还嫌慢，下一步应做的是 **按空间 shard 拆成多个 SLURM 子任务**，而不是再把单任务 worker 从 `4` 往上拧
