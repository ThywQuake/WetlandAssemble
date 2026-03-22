# Phase 2 批量数据生成与 GWD30 OOM 硬化 — 摘要

**日期:** 2026-03-19
**分支:** `feat/phase2-rough-binary-modis-truth`
**状态:** Phase 2 非可视化批量数据生成已实现；`config` 中已加入优先区域配置；GWD30 在 rough 阶段改为低内存直达 coarse grid 路径并输出可视化 trace

## Architecture decisions

- Phase 2 现在正式支持“非可视化的数据生成模式”：先为多个重点热带流域/湿地区域批量生成粗尺度湿地比较数据文件，后续再做可视化。
- 关键区域配置被迁移到 `config/priority_regions.yaml`，符合“region 这类关键配置放 config”的项目决策。
- `src/WA/rough_batch.py` 作为新的批量执行层，复用现有 `probe_prepared_dataset()`、`compute_rough_binary_metrics()`、`select_focus_areas()`，避免重新发明另一套 Phase 2 逻辑。
- 批量数据生成默认运行两个窗口：
  - `2000-03-01`：最大历史参与交集窗口
  - `2019-07-01`：现代窗口，包含 `GWD30`
- 每个 `region/time` 输出目录都会同时写：
  - pairwise metrics CSV
  - comparison grids NetCDF
  - participant surfaces NetCDF
  - focus areas CSV
  - run summary JSON
- 批处理总目录还会写 `batch_manifest.json`，便于后续汇总和可视化驱动。
- 默认优先区域目录现在优先读取 `config/priority_regions.yaml`；若 HPC 上默认配置文件缺失，则仍回退到代码内建目录，避免因为漏同步配置导致整个批处理直接挂掉。
- `GWD30` 的旧 rough 路径存在明显的内存风险：在大流域窗口下会匹配大量 tile，并尝试把所有 tile 的高分辨率多 band 栅格一次性读入 + 合并为年度 mosaic，容易 OOM。
- 为降低 GWD30 内存峰值，新增 `load_rough_binary_surface()`：
  - 不再构建整块高分辨率年尺度 mosaic；
  - 只选择目标月份需要的 4-day band；
  - 按 tile 顺序逐块读取；
  - 每个 tile 直接映射到 binary fraction、月聚合、再对齐到 coarse reference grid；
  - 以增量方式累计到最终 coarse surface。
- 为方便确认 GWD30 加载过程是否合理，新增 trace 输出：
  - `gwd30_load_trace.json`
  - `gwd30_selected_tiles.geojson`
  这两个文件会记录每个年份选中的 tile、tile code、tile bbox、band 选择情况，可直接用于排查“哪里出错”。

## Modified files and key changes

- `config/priority_regions.yaml`
  新增 9 个优先热带流域/湿地区域的关键配置与 bbox。
- `src/WA/rough_batch.py`
  新增 Phase 2 批量数据生成模块：
  - priority region catalog loading
  - multi-region / multi-window batch execution
  - result file writing
  - batch manifest writing
  - GWD30 trace/GeoJSON export
- `scripts/run_phase2_rough_regions.py`
  新增生产 CLI 入口，支持在 HPC 上直接批量跑 9 区域 × 2 时间窗口。
- `src/WA/loaders/_shared.py`
  `open_multiband_raster()` 新增 `band_indexes`，支持只读目标月份所需 band。
- `src/WA/loaders/gwd30.py`
  新增 `load_rough_binary_surface()`：
  - 避免整年整区域年度 mosaic
  - 逐 tile 直达 coarse comparison grid
  - 记录 tile/band trace
  - 加入周期性 GC 与进度日志
- `src/WA/rough_probe.py`
  对 `gwd30` 优先走 `load_rough_binary_surface()` 低内存路径。
- `tests/test_rough_batch.py`
  新增区域目录加载、默认配置回退、批量输出写出、GWD30 trace 路径等测试。
- `todos/006-complete-p1-build-phase2-rough-region-data-generation.md`
  新建并完成本轮 todo，记录工作与验证。

## Priority region configuration

默认区域配置现在位于：
- `config/priority_regions.yaml`

包含 9 个区域：
- `amazon_basin`
- `orinoco_basin_llanos`
- `pantanal_upper_paraguay`
- `ngiri_tumba_maindombe`
- `sudd`
- `okavango_delta`
- `mekong_delta`
- `mekong_flooded_forest`
- `danau_sentarum`

## Phase 2 batch command

当前建议在 HPC 上运行：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/run_phase2_rough_regions.py \
  --target-time 2000-03-01 \
  --target-time 2019-07-01 \
  --results-root results/phase2/rough
```

该命令默认读取：
- `config/priority_regions.yaml`

## job07 findings

来自 `temp/job07/job.10175563.out` 与 `temp/job07/job.10175563.err`：

- 批处理在 `2019-07` 窗口进入 `gwd30: load dataset` 后被 Slurm OOM kill。
- 关键日志：
  - `gwd30: discovery ... matched_tiles: 1139`
  - 随后进入 `gwd30: load dataset`
  - Slurm 报告：`Detected 1 oom_kill event`
- 这强烈表明旧的 GWD30 rough 加载方式“不科学”：在大流域下试图一次性读取并合并过多高分辨率 tile。

## Verification status

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_rough_batch.py tests/test_rough_probe.py tests/test_loader_probe.py tests/test_comparison/test_rough_binary.py tests/test_comparison/test_harmonize.py -q`: pass (`24 passed, 1 warning`)
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/WA/rough_batch.py scripts/run_phase2_rough_regions.py tests/test_rough_batch.py src/WA/rough_probe.py src/WA/loader_probe.py tests/test_rough_probe.py tests/test_loader_probe.py tests/test_comparison/test_rough_binary.py tests/test_comparison/test_harmonize.py`: pass
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_rough_batch.py tests/test_rough_probe.py tests/test_loaders/test_gwd30.py -q`: pass (`17 passed, 1 warning`)
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/WA/loaders/gwd30.py src/WA/loaders/_shared.py src/WA/rough_probe.py src/WA/rough_batch.py tests/test_rough_batch.py`: pass
- 默认 priority region config 验证：
  - `default_path = config/priority_regions.yaml`
  - `region_count = 9`

已知 warning:
- `numpy.ndarray size changed, may indicate binary incompatibility`
  仍是现有 geospatial stack warning，本轮未新增。

## Open risks, TODOs, rollback notes

- 新的 GWD30 直达 coarse grid 路径显著降低了 rough comparison 的内存风险，但尚未经过新的真实 HPC job 结果验证；需要下一轮 run 来确认是否彻底消除 OOM。
- `gwd30_selected_tiles.geojson` 与 `gwd30_load_trace.json` 已提供可视化排查基础，但还没有专门的可视化 notebook / plotting helper。
- 目前 trace 文件是在 `run_summary.json` 的 `output_files` 中登记；后续如果可视化工作开始，建议加一个统一索引清单，便于下游自动发现所有 trace 文件。
- `glwd_v2` 仍可能在部分 bbox 上产生 `failed_empty_harmonized_surface`；这是业务层/数据层问题，和本轮 GWD30 OOM 修复独立。

## Recommended next step

- 在 HPC 上重新运行 `scripts/run_phase2_rough_regions.py`，确认：
  1. 不再发生 GWD30 OOM；
  2. 每个 `region/time` 目录成功生成 `gwd30_load_trace.json` 与 `gwd30_selected_tiles.geojson`；
  3. 检查某个大流域（如 `amazon_basin/201907`）下 trace 文件中的 tile 数量与空间分布是否符合预期。
- 如果 HPC 仍有内存压力，下一步应继续从两处压缩：
  - 按 tile 批次分组写临时 coarse accumulation
  - 对 `G2017/GLWD` 大窗口读取引入更激进的 direct-to-reference-grid 路径
