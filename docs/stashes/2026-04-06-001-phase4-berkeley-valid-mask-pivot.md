# 2026-04-06-001 Phase4 Berkeley Valid Mask Pivot

## 结论

- `Phase3.6 joint_valid_mask` 不再适合作为 Phase4 区域趋势统计的共享 mask。
- 新策略改为：
  1. 区域划到哪就只算哪，不再强制先构建 `gwd30 full_tropics` 全域缓存
  2. Phase4 的共享 mask 改为 **Berkeley-RWAWC 在该区域、该时间窗下的有效数据范围**
  3. `gwd30` 直接从 `standardized/_staging/gwd30_<year>/stage_shard_*.json` 恢复 staged tiles，按 region bbox 直接聚合

## 关键改动

- [scripts/run_phase4_regional.py](/Users/mac/Code/WA/scripts/run_phase4_regional.py)
  - 不再加载 `Phase3.6 joint_valid_mask`
  - 每个 region 开始前先构建或加载 Berkeley valid mask
  - `gwd30` 不再预构建 `full_tropics tile cache`
- [src/WA/comparison/phase4_regional.py](/Users/mac/Code/WA/src/WA/comparison/phase4_regional.py)
  - 新增 `phase4_berkeley_valid_mask_cache_path(...)`
  - 新增 `build_or_load_phase4_berkeley_valid_mask(...)`
  - 新增 `build_phase4_gwd30_monthly_series_from_staged_tiles(...)`
  - `compute_phase4_region_dataset_table(...)` 的 `gwd30` 分支改为直接 region-level staged aggregation

## Berkeley mask 语义

- 这里的 Berkeley mask 不是 `watermask` 数值本身，而是 **Berkeley 在该区域该时间窗内是否有有效观测值**。
- 实现上使用：`monthly.notnull().any(dim="time")`
- 这样分母是 Berkeley 的有效空间范围，而不是 `g2017` 那种“千疮百孔”的联合域。

## 验证

- `ruff check src/WA/comparison/phase4_regional.py scripts/run_phase4_regional.py tests/test_comparison/test_phase4_regional.py`
  - 通过
- `python -m compileall src/WA/comparison/phase4_regional.py scripts/run_phase4_regional.py tests/test_comparison/test_phase4_regional.py`
  - 通过
- `python -m pytest tests/test_comparison/test_phase4_regional.py tests/test_comparison/test_trends.py tests/test_submit_phase4_gwd30_tropical_shards.py -q`
  - `32 passed`

## 风险

- 旧的 `submit_phase4_gwd30_tropical_shards.sh` / tropical cache 链路仍保留在仓库里，但当前 Phase4 区域结果已经不依赖这条链路。
- Berkeley valid mask 当前是区域级 2D 静态 mask（时间窗内 `any valid`），不是逐月变化的动态 mask。

## 新的 HPC 运行建议

直接跑区域表，不再先跑全热带 reducer：

```bash
python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --berkeley-raw-path /lustre/home/2200013429/Wetland_Assemble/data/Berkeley_RWAWC \
  --output-root results/phase4 \
  --no-skip
```

如果要多数据集一起跑：

```bash
python scripts/run_phase4_regional.py \
  --dataset-id gwd30 \
  --dataset-id giems_mc \
  --dataset-id topmodel \
  --dataset-id swamps \
  --dataset-id wad2m \
  --dataset-id berkeley_rwawc \
  --region amazon \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --berkeley-raw-path /lustre/home/2200013429/Wetland_Assemble/data/Berkeley_RWAWC \
  --output-root results/phase4 \
  --no-skip
```
