# GWD30 并行归并加速 — 摘要

**日期:** 2026-03-19
**分支:** `feat/phase2-rough-binary-modis-truth`
**状态:** GWD30 rough load 新增高吞吐并行归并路径；本地验证通过

## Architecture decisions

- 参考前代 `Wetland_Assemble` 的经验，本轮把 GWD30 的“最高效率”路径定为：
  - 先按 ROI / tile 过滤；
  - 每个 tile 单独读取、聚合、重投影到 coarse grid；
  - 由主进程做 sum/count 归并；
  - 避免构造完整高分辨率 mosaic。
- 与上一轮的“逐 tile 临时文件 + 最终镶嵌”相比，本轮新增了一条更快的热路径：
  - `parallel_direct_to_reference_grid`
  - worker 直接返回 coarse partial `sum/count`
  - 主进程原地 reduce
  - 不再走每 tile 落盘，减少磁盘 I/O
- 串行低内存临时文件路径仍保留，作为保守 fallback。
- 并行 worker 数支持：
  - 显式参数 `--gwd30-workers`
  - 环境变量 `WA_GWD30_WORKERS`
  - HPC 环境变量 `SLURM_CPUS_PER_TASK`
- 加载进度继续用 `tqdm` 展示；并行路径进度条为 `GWD30 {year} parallel`。

## Modified files and key changes

- `src/WA/loaders/gwd30.py`
  - 新增 worker count 解析
  - 新增 top-level tile projection / partial reduce helper
  - `load_rough_binary_surface()` 支持并行 sum/count reduce
  - trace 新增 `worker_count` 与并行策略信息
- `src/WA/rough_probe.py`
  - `RoughProbeOptions` 新增 `gwd30_workers`
  - rough probe CLI 新增 `--gwd30-workers`
  - 调用 GWD30 rough loader 时透传 worker 数
- `src/WA/rough_batch.py`
  - batch CLI 新增 `--gwd30-workers`
  - Phase 2 batch options 支持把 worker 配置下传到 rough probe
- `tests/test_loaders/test_gwd30.py`
  - 新增并行 reduce 路径回归测试
  - 保留串行 tempfile 路径测试

## Verification status

- `uv run pytest tests/test_loaders/test_gwd30.py tests/test_rough_probe.py tests/test_rough_batch.py -q`: pass (`19 passed, 1 warning`)
- `uv run ruff check src/WA/loaders/gwd30.py src/WA/rough_probe.py src/WA/rough_batch.py tests/test_loaders/test_gwd30.py`: pass
- `uv run mypy src/WA/loaders/gwd30.py src/WA/rough_probe.py src/WA/rough_batch.py tests/test_loaders/test_gwd30.py`: pass

已知 warning:
- `numpy.ndarray size changed, may indicate binary incompatibility`
  仍来自现有 geospatial stack，和本轮并行化无直接关系。

## Open risks, TODOs, rollback notes

- 当前“并行”是单 Python 作业内的多 worker map-reduce；要真正吃满 16 个 HPC 节点，仍需要更外层的调度层（例如 Slurm array / Dask scheduler）。
- 如果并行 worker 数过大，峰值内存会近似变成“单 tile 峰值 × worker_count”；建议在 HPC 上用 `--gwd30-workers 16` 先实测，再视 I/O 与内存表现调优。
- 如果 shared filesystem I/O 成为瓶颈，可以进一步把粒度从“按 tile”提升为“按 tile-shard partial reducer”，让每个 worker 输出一份 partial sum/count 再做第二阶段归并。
