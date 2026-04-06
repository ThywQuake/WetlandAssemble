# 2026-04-05-009 Phase4.1 GWD30 Pixel-Reduce Then Mask-Merge

## 结论

- 之前的 OOM 根因有两层：
  1. shard task 错误地提前加载了 `Phase 3.6 global_500m joint_valid_mask`
  2. reducer 直接从原始 staged `weighted(time,class,y,x)` 读取并行计算，`16` worker 时内存仍然过高
- 本次修正后的链路是：
  1. shard task 从 `stage_shard_*.json` 恢复 staged tiles
  2. 对每个 tile 做**无 mask 的像素尺度 reduce**，把 `weighted(time,class,y,x)` 压成 `wetland_weighted(time,y,x)` + `coverage(time,y,x)`
  3. 写入 shard 私有 `reduced_tiles/<manifest_list_stem>/tile_*.nc`
  4. reduce job 再读取这些 reduced tiles，按 tile 子窗加载 `Phase 3.6 mask`，最后生成 `tile_monthly_<year>.csv`

## 关键改动

- [src/WA/comparison/phase4_regional.py](/Users/mac/Code/WA/src/WA/comparison/phase4_regional.py)
  - 新增 `phase4_reduce_staged_time_fraction_tile(...)`
  - 新增 `build_phase4_gwd30_reduced_tile_index_for_staged_tiles(...)`
  - 新增 `build_phase4_gwd30_tropical_monthly_tile_from_reduced_file(...)`
  - reducer 现在从 reduced tile 而不是原始 staged tile 计算月尺度统计
- [scripts/run_phase4_gwd30_tropical_shard.py](/Users/mac/Code/WA/scripts/run_phase4_gwd30_tropical_shard.py)
  - 改为生成 shard 私有 reduced tile `.nc`
  - partial CSV 现在记录 `reduced_path + bbox`
  - 新增 `--worker-count`
- [scripts/reduce_phase4_gwd30_tropical_shards.py](/Users/mac/Code/WA/scripts/reduce_phase4_gwd30_tropical_shards.py)
  - 改为读取 reduced tile partials
  - 只消费当前 `manifest_lists_summary.json` 对应的 partial CSV，不再全目录 glob 历史残留
  - 若 summary 中声明的 partial 缺失，直接报错，避免残缺 merge
- [scripts/build_phase4_gwd30_shard_lists.py](/Users/mac/Code/WA/scripts/build_phase4_gwd30_shard_lists.py)
  - 生成新 list 前先清理旧 `manifest_list_*.txt`
- [scripts/submit_phase4_gwd30_tropical_shards.sh](/Users/mac/Code/WA/scripts/submit_phase4_gwd30_tropical_shards.sh)
  - shard task 会把 `TASK_CPUS` 传给 `--worker-count`
  - mask 仍只在 reduce job 使用

## 验证

- `python -m compileall src/WA/comparison/phase4_regional.py scripts/build_phase4_gwd30_shard_lists.py scripts/run_phase4_gwd30_tropical_shard.py scripts/reduce_phase4_gwd30_tropical_shards.py tests/test_comparison/test_phase4_regional.py tests/test_submit_phase4_gwd30_tropical_shards.py`
  - 通过
- `ruff check src/WA/comparison/phase4_regional.py scripts/build_phase4_gwd30_shard_lists.py scripts/run_phase4_gwd30_tropical_shard.py scripts/reduce_phase4_gwd30_tropical_shards.py tests/test_comparison/test_phase4_regional.py tests/test_submit_phase4_gwd30_tropical_shards.py`
  - 通过
- `bash -n scripts/submit_phase4_gwd30_tropical_shards.sh`
  - 通过
- `python -m pytest tests/test_comparison/test_phase4_regional.py tests/test_submit_phase4_gwd30_tropical_shards.py -q`
  - `15 passed`

## 风险

- reducer 仍然会按 tile 打开 reduced netCDF；如果 `--worker-count` 设得过大，I/O 和内存仍可能升高，但比直接读原始 staged tile 的 4D class cube 轻得多。
- 当前最终 `tile_monthly_<year>.csv` 仍是 tile-level 标量缓存，不是 full-grid monthly raster；这符合 Phase4 区域聚合需求。

## HPC 建议命令

建议先用更多 task list、较小 task worker 数，把重活放在 reduce：

```bash
bash scripts/submit_phase4_gwd30_tropical_shards.sh \
  --years 2020 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --phase36-cache-dir results/cache/phase3_6 \
  --task-lists 64 \
  --task-cpus 1 \
  --reduce-cpus 16 \
  --reduce-partition C064M0256G \
  --no-skip
```

如果要直接跑区域表：

```bash
python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --phase36-cache-dir results/cache/phase3_6 \
  --output-root results/phase4
```
