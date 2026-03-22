# Job04 Rough Probe Bug 修复与 GWD30 性能分析 — 摘要

**日期:** 2026-03-19
**分支:** `feat/phase2-rough-binary-modis-truth`
**状态:** `job04` 崩溃已修复；GWD30 性能瓶颈已定位并给出资源建议

## Architecture decisions

- `rough_binary` comparison 层不再依赖参与 surface 上残留的标量 `time` 坐标；stack 前会清理非空间标量坐标，避免 `xr.concat()` 因不同数据集的 source time 冲突而崩溃。
- `select_comparison_slice()` 在保留 `comparison_source_time` 审计信息的同时，去掉返回 surface 上的辅助标量坐标，保证 comparison surfaces 是“只含空间维度”的稳定输入。
- `harmonize_binary_dataset()` 现在不仅检查映射后的 source surface 是否为空，也检查 **对齐到 reference grid 后** 的结果是否为空；像 `glwd_v2` 这种“映射前不空、重投影后全空”的情况会被显式视为失败，而不是继续记成 `participating`。
- `rough_probe` 对于动态数据集，如果目标月份根本不在 temporal coverage 内，会在 discovery 前直接返回 `skipped_time_window`，避免像 `job04` 那样先做昂贵的 GWD30 tile discovery 再跳过。
- GWD30 当前的核心性能瓶颈不在算力不足，而在单节点串行 I/O：
  - tile discovery 按年 glob + bbox filter；
  - tile-code 预筛失败时退化到逐 tif 读 bounds；
  - month-level probe 仍会读取整年 92 个 4-day bands。
- HPC 资源建议基于当前实现：优先增加单节点 CPU 与内存，不建议直接加多节点；在未做按 year/AOI 分布式拆分前，多节点收益很低。

## Modified files and key changes

- `src/WA/comparison/harmonize.py`
  - 对齐后增加 `_ensure_non_empty_binary_surface()` 检查
  - `select_comparison_slice()` 现在会去掉残留辅助标量坐标
  - 新增 `_drop_auxiliary_coords()`
- `src/WA/comparison/rough_binary.py`
  - stack 前新增 `_prepare_surface_for_stack()`，清理非空间标量坐标
- `src/WA/rough_probe.py`
  - `skipped_time_window` 提前到 discovery 之前判定，避免无意义的昂贵 discovery
- `tests/test_comparison/test_harmonize.py`
  - 新增 slice 后不保留 `time` 标量坐标的回归测试
  - 新增“对齐后空 GLWD surface 必须失败”的回归测试
- `tests/test_comparison/test_rough_binary.py`
  - 新增“不同 source time 的 scalar `time` coords 不再导致 `xr.concat()` 崩溃”的回归测试
- `tests/test_rough_probe.py`
  - 新增“空 harmonized surface 记为 failed”的回归测试
  - 新增“out-of-range dynamic dataset 在 discovery 前直接 skipped”的回归测试

## job04 findings

来自 `temp/job04/job.10172762.err` 与 `temp/job04/job.10172762.out` 的关键结论：

- `compute_rough_binary_metrics()` 在 `xr.concat()` 阶段报错：
  - `MergeError: conflicting values for variable 'time' on objects to be combined`
- `glwd_v2` 在 probe 输出中已出现：
  - `harmonized non_null=0 wetland_cells=0`
  - 但仍被记为 `participating`
- `gwd30` 在 `target_time=2000-03-01` 下最终是 `skipped_time_window`，但在旧逻辑里仍然先做了整套 discovery；其中 2016 年 fallback 到 raster-bounds scan，单年耗时约 17 分钟，是最明显的无效开销。

## Verification status

- `uv run pytest tests/test_comparison/test_harmonize.py tests/test_comparison/test_rough_binary.py tests/test_rough_probe.py -q`: pass (`15 passed`)
- `uv run ruff check src/WA/rough_probe.py src/WA/comparison/harmonize.py src/WA/comparison/rough_binary.py tests/test_rough_probe.py tests/test_comparison/test_harmonize.py tests/test_comparison/test_rough_binary.py`: pass

## GWD30 HPC resource recommendation

**基于当前实现：**

- rough probe 常规运行：`1 node / 8 CPU / 16 GB RAM`
- 若目标月份位于 2013–2022 且会真实加载 GWD30：`1 node / 8–16 CPU / 32 GB RAM`
- 若要批量 AOI / 多年份诊断，并容忍 fallback 年份：`1 node / 16–32 CPU / 64 GB RAM`

**结论：** 当前版本不建议直接加多节点；主要瓶颈是单节点文件扫描与 GeoTIFF I/O，不是可自动扩展的分布式计算。

## Open risks, TODOs, rollback notes

- `GWD30` 的真正读取提速还没做完；当前只是去掉了“明知会 skip 仍先 discovery”的无效开销。
- 最大剩余优化项是：
  1. 按 `time_range` 只读取目标月需要的 4-day bands，而不是整年 92 bands；
  2. 将 raster-bounds fallback 并行化，并考虑把 filename → bounds/tile_code 建成本地索引缓存。
- `GWD30` 某些年份（如 `job04` 中的 2016）tile-code prefilter 仍可能失效，导致 fallback 到极慢的 bounds scan；这仍是后续硬化重点。
- 如果后续真正要利用多节点，需先重构为“按 year / AOI 分任务”的并行执行模型；否则单纯申请更多节点不会显著加速当前 loader。

## Recommended next step

- 优先实现 GWD30 的 **month-level band subsetting**，让 rough probe 在单月场景下不再读取整年 92 bands；这是最有希望获得 5–10x 量级提速的优化。
