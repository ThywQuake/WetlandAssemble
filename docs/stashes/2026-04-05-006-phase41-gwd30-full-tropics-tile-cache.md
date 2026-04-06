# 2026-04-05-006 Phase4.1 GWD30 全热带 Tile Cache

## 背景

- 用户明确要求本阶段只处理数据，不处理绘图。
- `gwd30` 不应再按 `region_id` 作为主缓存层级，因为需要同时支持全热带和多个子区域。
- 现有 HPC 已经有可复用的 staged manifests:
  `/lustre/home/2200013429/Wetland_Assemble/data/standardized/_staging/gwd30_<year>/stage_shard_*.json`
- 当前更合理的链路是：
  `restore staged tile partials -> build full-tropics tile-month cache -> derive regional tables`

## 本次改动

- `src/WA/comparison/phase4_regional.py`
  - 新增 `build_or_load_phase4_gwd30_tropical_tile_cache(...)`
  - 新增 `build_phase4_gwd30_monthly_series_from_tropical_tile_cache(...)`
  - 新增 `phase4_gwd30_tropical_tile_cache_path(...)`
  - `compute_phase4_region_dataset_table(...)` 现在支持直接消费预构建的 `gwd30_tropical_tile_cache`
  - `gwd30` 主链改为：
    - 从 `standardized/_staging/gwd30_<year>/stage_shard_*.json` 恢复 `tile_*.nc`
    - 对 `pan_trop_subtrop` 计算按月 tile 统计
    - 写入 `results/phase4/cache/gwd30/full_tropics/tile_monthly_<year>.csv`
    - 各子区域仅按 tile bbox 相交关系从这层缓存聚合
  - 不再逐区域直接扫描 staged tiles 作为主缓存策略
- `scripts/run_phase4_regional.py`
  - 如果请求了 `gwd30`，先一次性预构建或加载 `full_tropics tile cache`
  - 后续每个区域都复用这层共享缓存
- `tests/test_comparison/test_phase4_regional.py`
  - 新增 `full_tropics tile cache` 落盘测试
  - 新增从 tropical tile cache 提取区域月序列的测试
- `CHANGELOG.md`
  - 更新为“Phase 4 当前为 data-only”
  - 记录 `gwd30 full_tropics tile cache` 设计

## 关键设计决定

- 保留 standardized staging root 作为唯一 GWD30 staged source of truth。
- 本阶段不做 plotting。
- 本阶段不做 `gwd30` 大范围 merge。
- `gwd30` 区域统计的主缓存层级提升为 `full_tropics`，`region_id` 只作为派生表层级。
- 子区域提取使用 tile bbox 相交聚合，接受少量边界近似误差，以换取更高吞吐和更低内存占用。

## 验证

- `python -m compileall src/WA/comparison/phase4_regional.py scripts/run_phase4_regional.py tests/test_comparison/test_phase4_regional.py`
  - 通过
- `ruff check src/WA/comparison/phase4_regional.py scripts/run_phase4_regional.py tests/test_comparison/test_phase4_regional.py`
  - 通过
- `python -m pytest tests/test_comparison/test_phase4_regional.py -q`
  - `9 passed`

## 未做

- 没有跑 `python -m pytest tests/`，因为用户明确要求不要跑全量测试。
- 没有改 plotting phase。
- `trends.py` 的像素级 merge 路线未在本次继续收敛，因为本阶段聚焦区域数据缓存。
