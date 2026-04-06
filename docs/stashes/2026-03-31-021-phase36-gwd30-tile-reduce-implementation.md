# Phase 3.6 GWD30 tile-reduce 实现总结

**Date:** 2026-03-31
**Status:** 已将 Phase 3.6 的 GWD30 路径从“全局 staged tile merge 到 `(time,class,lat,lon)`”改为“tile-local 时间压缩与 8 类映射，再做全局条带聚合”，避免了 xarray 在全局 `reindex` 上申请 TB 级布尔掩膜。

## 本次修改

| File | Change |
|------|--------|
| `src/WA/loaders/gwd30.py` | 新增 `transform_staged_time_fraction_tiles(...)`，支持对 `tile_*.nc` 做自定义 tile-local transform，并沿用原有多进程 + lock + 原子 rename 机制 |
| `src/WA/loaders/gwd30.py` | 新增 `phase36_reduce_staged_time_fraction_tile(...)`，把单 tile 的 `weighted(time,class,y,x)` / `coverage(time,y,x)` 压缩为 `annual_unified_weighted_sum(8,y,x)` 与 `annual_coverage_sum(y,x)` |
| `src/WA/comparison/phase36.py` | 主流程改为仅对 `g2017` / `glwd_v2` 生成全局 unified fraction cache；GWD30 改为生成 `01_gwd30_valid_mask.nc` 与 `01_gwd30_dominant_class.nc` |
| `src/WA/comparison/phase36.py` | joint-valid stage 改为读取 `gwd30_valid_mask`，dominant stage 改为读取 `gwd30_dominant_class`，不再依赖 `01_gwd30_unified_fraction.nc` |
| `src/WA/comparison/phase36.py` | `--no-write-cache` 不再走旧的 direct path，而是使用临时 staged workspace 复用新流程 |
| `tests/test_loaders/test_gwd30.py` | 新增 staged tile transform API 回归测试 |
| `tests/test_phase3_6_analysis.py` | 更新 Phase 3.6 测试口径，改为 mock 新的 GWD30 cache builder |

## 新的 GWD30 cache 结构

在 `results/cache/phase3_6/...` 下，GWD30 相关产物现在是：

- `01_gwd30_phase36_annual_unified_v1/tile_*.nc`
- `01_gwd30_valid_mask.nc`
- `01_gwd30_dominant_class.nc`

不再生成：

- `01_gwd30_unified_fraction.nc`

## 并发与原子写

`transform_staged_time_fraction_tiles(...)` 复用了原有 staged tile 的并发设计：

- 多进程 `ProcessPoolExecutor`
- 单 tile 输出独立 `.lock`
- stale lock 回收
- 临时文件写完后 `os.replace()` 原子提交
- 并行失败后自动 fallback 到串行

因此适合 HPC 上共享文件系统的断点续跑场景。

## 运行逻辑

1. `g2017` / `glwd_v2`：保持原 unified fraction 全局 cache
2. `gwd30`：
   - 从 `_staging/gwd30_<year>/stage_shard_*.json` 恢复 `tile_*.nc`
   - 对每个 tile 做 Phase 3.6 reducer
   - 对 reduced tile 按纬向条带累加
   - 直接写出 `valid_mask` 和 `dominant_class`
3. `joint_valid` / `dominant` / `metrics`：继续按全局条带流式执行

## Verification

- `ruff check src/WA/comparison/phase36.py src/WA/loaders/gwd30.py tests/test_phase3_6_analysis.py tests/test_loaders/test_gwd30.py scripts/run_phase3_6_global_entropy.py`
- `python -m pytest tests/test_phase3_6_analysis.py tests/test_loaders/test_gwd30.py -q` → `38 passed`
- `python -m pytest tests/ -q` → `352 passed`

## HPC 运行命令

```bash
python scripts/run_phase3_6_global_entropy.py \
  --standardized-dir ~/Wetland_Assemble/data/standardized \
  --output-dir results/phase3.6 \
  --cache-dir results/cache/phase3_6 \
  --year 2016 \
  --lat-chunk-size 512
```

## 说明

- 若内存仍紧张，可继续把 `--lat-chunk-size` 下调到 `256`。
- 现在最重的 GWD30 tile 级数据在 transform 后已去掉 `time` 维，并从 15 类压到 8 类。
