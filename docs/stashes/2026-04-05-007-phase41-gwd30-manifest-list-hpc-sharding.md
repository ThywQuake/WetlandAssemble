# 2026-04-05-007 Phase4.1 GWD30 Manifest-List HPC 并行

## 背景

- 当前 `gwd30 full_tropics tile cache` 已经从 `region-first` 改成了共享主缓存。
- 但单机串行构建 `tile_monthly_<year>.csv` 仍然偏慢，主要瓶颈是逐个打开 `tile_*.nc`。
- 用户明确建议参考之前 `GWD30 sharded SLURM stage/merge` 的方案，把 `stage_shard_*.json` 再向前利用起来：
  每个 `shard_list` 分配一个 HPC 任务。

## 本次改动

- `src/WA/comparison/phase4_regional.py`
  - 新增 `list_phase4_gwd30_stage_shard_manifests(...)`
  - 新增 `load_phase4_gwd30_staged_tiles_from_manifest_paths(...)`
  - 新增 `build_phase4_gwd30_tropical_tile_cache_for_staged_tiles(...)`
  - 这样 Phase4 的核心 tile 统计逻辑可以被独立 shard 脚本直接复用，不需要复制代码
- 新增 `scripts/build_phase4_gwd30_shard_lists.py`
  - 从 `standardized/_staging/gwd30_<year>/stage_shard_*.json` 生成若干 `manifest_list_*.txt`
  - 默认按 round-robin 分配到 `task_count` 个 list 中
- 新增 `scripts/run_phase4_gwd30_tropical_shard.py`
  - 读取一个 `manifest_list_*.txt`
  - 恢复该 list 覆盖的 staged `tile_*.nc`
  - 计算这一批 tile 的 tropical monthly partial cache
  - 输出到 `results/phase4/cache/gwd30/full_tropics/gwd30_<year>/partials/manifest_list_*.csv`
- 新增 `scripts/reduce_phase4_gwd30_tropical_shards.py`
  - 合并 `partials/*.csv`
  - 去重后写出最终年度缓存：
    `results/phase4/cache/gwd30/full_tropics/tile_monthly_<year>.csv`
- 新增 `scripts/submit_phase4_gwd30_tropical_shards.sh`
  - 沿用旧的 `array task + dependent reduce job` 风格
  - 每个 manifest list 对应一个 SLURM array task
  - 全部 task 完成后自动提交 reduce job

## 当前 HPC 工作流

先构建并行缓存：

```bash
bash scripts/submit_phase4_gwd30_tropical_shards.sh \
  --years 2013,2014,2015,2016,2017,2018,2019,2020 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --phase36-cache-dir results/cache/phase3_6 \
  --task-lists 16 \
  --task-cpus 4 \
  --reduce-cpus 4 \
  --no-skip
```

等 `tile_monthly_<year>.csv` 都准备好之后，再跑区域表：

```bash
python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --phase36-cache-dir results/cache/phase3_6 \
  --output-root results/phase4
```

第二步默认会直接复用 `results/phase4/cache/gwd30/full_tropics/tile_monthly_<year>.csv`，不再串行重建。

## 验证

- `python -m compileall src/WA/comparison/phase4_regional.py scripts/build_phase4_gwd30_shard_lists.py scripts/run_phase4_gwd30_tropical_shard.py scripts/reduce_phase4_gwd30_tropical_shards.py tests/test_comparison/test_phase4_regional.py tests/test_submit_phase4_gwd30_tropical_shards.py`
  - 通过
- `bash -n scripts/submit_phase4_gwd30_tropical_shards.sh`
  - 通过
- `ruff check src/WA/comparison/phase4_regional.py scripts/build_phase4_gwd30_shard_lists.py scripts/run_phase4_gwd30_tropical_shard.py scripts/reduce_phase4_gwd30_tropical_shards.py tests/test_comparison/test_phase4_regional.py tests/test_submit_phase4_gwd30_tropical_shards.py`
  - 通过
- `python -m pytest tests/test_comparison/test_phase4_regional.py tests/test_submit_phase4_gwd30_tropical_shards.py -q`
  - `11 passed`

## 注意

- 这次仍然没有跑 `python -m pytest tests/`，因为用户明确要求不要跑全量测试。
- 这次只处理数据缓存链，不处理绘图阶段。
