# GWD30 分片链路与命令边界 — 对话摘要

**日期:** 2026-03-20  
**分支:** `feat/phase2-rough-binary-modis-truth`  
**状态:** GWD30 已支持单作业内并行 reduce 与多节点 shard/reduce；本轮最终按用户要求仅保留“应执行的命令”，不保留代用户提交的脚本

## Architecture decisions

- GWD30 rough load 现在有三层执行形态：
  - 单作业内串行低内存 tempfile 路径
  - 单作业内高吞吐 `parallel_direct_to_reference_grid`
  - 多节点友好的 shard partial/reduce 工作流
- 分片工作流拆为两阶段：
  1. `compute_rough_binary_partial()` 生成 shard partial `sum/count`
  2. `build_surface_from_partial()` / `reduce_gwd30_rough_shards.py` 归并为最终 `gwd30_surface.nc`
- `rough_probe` 与 `rough_batch` 都支持消费预计算的 `gwd30_surface.nc`，使 GWD30 可脱离主流程单独在 HPC 上跑完再回接。
- GWD30 worker 数不再假设固定 16 核；会自动从 HPC / shell 环境变量和本地 CPU 可见核数中解析。
- 用户明确要求：
  - 以后**不要代替用户写或提交 Slurm 提交脚本**；只给出应执行的命令。
  - 以后**新增依赖必须使用 `uv add`**，不要手动改 `pyproject.toml` / `uv.lock`。

## Modified files and key changes

- [src/WA/loaders/gwd30.py](/Users/mac/Code/WA/src/WA/loaders/gwd30.py)
  - 新增自动 worker 检测
  - 新增 shard 选择与 partial/reduce 能力
  - 保留串行 tempfile 路径，并新增单作业内并行 reduce 热路径
- [src/WA/rough_probe.py](/Users/mac/Code/WA/src/WA/rough_probe.py)
  - `RoughProbeOptions` 新增 `gwd30_workers` 与 `gwd30_surface_path`
  - 支持直接加载预计算 GWD30 surface
- [src/WA/rough_batch.py](/Users/mac/Code/WA/src/WA/rough_batch.py)
  - 新增 `gwd30_workers`
  - 新增 `gwd30_surface_root` 路径解析
- [scripts/run_gwd30_rough_shard.py](/Users/mac/Code/WA/scripts/run_gwd30_rough_shard.py)
  - 运行单 shard partial 任务
- [scripts/reduce_gwd30_rough_shards.py](/Users/mac/Code/WA/scripts/reduce_gwd30_rough_shards.py)
  - 归并 partial shard，产出 `gwd30_surface.nc`
- [tests/test_loaders/test_gwd30.py](/Users/mac/Code/WA/tests/test_loaders/test_gwd30.py)
  - 新增并行 reduce 与 shard partial/reduce 回归测试
- [tests/test_rough_probe.py](/Users/mac/Code/WA/tests/test_rough_probe.py)
  - 新增 precomputed GWD30 surface 回归测试
- [tests/test_rough_batch.py](/Users/mac/Code/WA/tests/test_rough_batch.py)
  - 新增 `gwd30_surface_root` 回归测试

## Verification status

- `uv run pytest tests/test_loaders/test_gwd30.py tests/test_rough_probe.py tests/test_rough_batch.py -q`: pass (`22 passed, 1 warning`)
- `uv run ruff check src/WA/loaders/gwd30.py src/WA/rough_probe.py src/WA/rough_batch.py scripts/run_gwd30_rough_shard.py scripts/reduce_gwd30_rough_shards.py tests/test_loaders/test_gwd30.py tests/test_rough_probe.py tests/test_rough_batch.py`: pass
- `uv run mypy src/WA/loaders/gwd30.py src/WA/rough_probe.py src/WA/rough_batch.py tests/test_loaders/test_gwd30.py tests/test_rough_probe.py tests/test_rough_batch.py`: pass

已知 warning:
- `numpy.ndarray size changed, may indicate binary incompatibility`
  仍来自现有 geospatial stack，与本轮功能无直接关系。

## Open risks, TODOs, rollback notes

- 目前已经有多节点友好的 shard/reduce 命令链，但**没有保留自动提交脚本**，因为用户要求由用户自己手动提交。
- 后续如果继续给 HPC 建议，只能提供：
  - job 脚本中应写入的 shell 片段
  - 具体的 `python scripts/...` 命令
  不能直接代写完整提交器并默认提交。
- 以后如果需要新增 Python 包，必须先用 `uv add <package>`；不要直接手改依赖文件。
