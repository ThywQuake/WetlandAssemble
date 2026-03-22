# GWD30 分片工作流与自动核数检测 — 摘要

**日期:** 2026-03-19
**分支:** `feat/phase2-rough-binary-modis-truth`
**状态:** 已支持 GWD30 shard partial/reduce 工作流；自动核数检测已增强；可将归并后的 surface 回接 rough pipeline

## Architecture decisions

- 在单作业内，GWD30 仍支持高吞吐 `parallel_direct_to_reference_grid`。
- 为了真正利用多节点资源，本轮新增了 **两阶段 shard/reduce 工作流**：
  1. 多个节点分别计算 GWD30 shard partial `sum/count`
  2. 单独 reduce 这些 partial，产出最终 `gwd30_surface.nc`
- rough pipeline 新增“消费预计算 GWD30 coarse surface”的能力，因此 GWD30 可以脱离主流程单独在多节点上完成，再回接到 Phase 2 比较。
- 自动核数检测不再假设固定 16 核：
  - `WA_GWD30_WORKERS`
  - `SLURM_CPUS_PER_TASK`
  - `SLURM_CPUS_ON_NODE`
  - `OMP_NUM_THREADS`
  - `PBS_NUM_PPN`
  - `NSLOTS`
  - `os.sched_getaffinity(0)`
  - `os.cpu_count()`
  按优先级依次回退。

## Modified files and key changes

- `src/WA/loaders/gwd30.py`
  - 新增 shard spec 校验与 tile 分片选择
  - 新增 `compute_rough_binary_partial()`
  - 新增 `build_surface_from_partial()`
  - 新增串行 shard reduce helper
  - 自动核数检测增强
- `src/WA/rough_probe.py`
  - `RoughProbeOptions` 新增 `gwd30_surface_path`
  - rough probe 可直接读取预计算 `gwd30_surface.nc`
- `src/WA/rough_batch.py`
  - batch 支持 `gwd30_surface_root`
  - 约定路径为 `{root}/{region_id}/{YYYYMM}/gwd30_surface.nc`
- `scripts/run_gwd30_rough_shard.py`
  - 运行单个 shard，输出 `gwd30_partial_XXX_of_YYY.nc`
- `scripts/reduce_gwd30_rough_shards.py`
  - reduce 多个 partial shard，输出 `gwd30_surface.nc`
- `tests/test_loaders/test_gwd30.py`
  - 新增 shard partial/reduce 回归测试
- `tests/test_rough_probe.py`
  - 新增 precomputed GWD30 surface 回归测试
- `tests/test_rough_batch.py`
  - 新增 `gwd30_surface_root` 路径解析回归测试

## Verification status

- `uv run pytest tests/test_loaders/test_gwd30.py tests/test_rough_probe.py tests/test_rough_batch.py -q`: pass (`22 passed, 1 warning`)
- `uv run ruff check src/WA/loaders/gwd30.py src/WA/rough_probe.py src/WA/rough_batch.py scripts/run_gwd30_rough_shard.py scripts/reduce_gwd30_rough_shards.py tests/test_loaders/test_gwd30.py tests/test_rough_probe.py tests/test_rough_batch.py`: pass
- `uv run mypy src/WA/loaders/gwd30.py src/WA/rough_probe.py src/WA/rough_batch.py tests/test_loaders/test_gwd30.py tests/test_rough_probe.py tests/test_rough_batch.py`: pass

已知 warning:
- `numpy.ndarray size changed, may indicate binary incompatibility`
  仍来自 geospatial stack，和本轮功能无直接关系。

## Open risks, TODOs, rollback notes

- 现在已经有“多节点友好”的文件级 shard/reduce 工作流，但还没有提供现成的 Slurm array 脚本模板；下一步建议补一个提交脚本。
- 如果 shard 数远大于 tile 数，会出现部分 shard 空跑；这是正常行为，但后续可以增加“按 year/tile count 动态建议 shard_count”的提示。
- 目前 reduce 产物默认写到 shard 目录下的 `gwd30_surface.nc`；如果后续要追踪多次实验，建议再引入 run id 或日期戳目录。
