---
title: "feat: Phase 4.1 GWD30 Full-Period Stage Optimization"
type: feat
status: active
date: 2026-04-05
parent: docs/plans/2026-03-19-005-feat-phase4-trend-analysis-plan.md
---

# Phase 4.1 GWD30 全时段 Stage 优化

## Overview

当前 Phase 4 的区域时序路径已经确认一个真实瓶颈：`gwd30` 会按 `region_id × year` 临时建立 staged tile cache。这样即使底层算法已切到 staged-tile 路径，首次跑新区域时仍会重新经历一次 `raw tif -> stage tile_*.nc`，导致 HPC 输出出现：

- `stage plan prepared ... pending ... reused 0 staged tile(s)`
- 随后重新处理数百个原始 TIFF

经重新核对 stash 与用户提供的 HPC 实况，问题**不是**“HPC 上没有全时段 staged tiles”，而是：

1. HPC 上已经存在 `standardized/_staging/gwd30_YYYY/tile_partials/tile_*.nc`
2. 对应的 `stage_shard_00xx_of_0064.json` manifests 也已经存在
3. 但 Phase 4 regional / trend 路径**没有去读取这套既有 staged cache**

因此单开 `Phase 4.1` 仍然合理，但目标已经从“先建全时段 staged cache”修正为：

- **把 Phase 4 正确接到现有的 canonical staged cache**
- 必要时补 manifest 校验与路径抽象
- 避免再新建一套平行的 Phase4 专用 staged 目录

## 中文目标

1. 让 GWD30 Phase 4 路径直接复用 HPC 已有的 `standardized/_staging/gwd30_YYYY` staged cache。
2. 把 shard manifest restore 接到 regional 与 trend 两条路径。
3. 避免按 `region_id` 或 `bbox token` 再生成一套新的 Phase4 staged 目录。
4. 增加运行前校验：manifest 存在、tile 文件存在、year/bbox/grid 契约一致。
5. 所有 cache 命中/未命中都必须在日志中显式可见。

## English Summary

Phase 4.1 should not build a second GWD30 staging universe. The HPC environment already has canonical staged GWD30 tile partials plus `stage_shard_*.json` manifests under `standardized/_staging/gwd30_YYYY/`. The real task is to wire Phase 4 regional and trend workflows into that existing cache, validate manifests explicitly, and stop creating ad hoc Phase4-only staging roots.

## 范围

### In Scope

- 复用 HPC 已有 GWD30 `2013-2022` staged cache
- staged tile manifest 恢复、校验、筛选
- Phase 4 regional 改为复用 canonical stage cache
- Phase 4 trend / probe 路径改为复用同一 cache root
- 必要时补一个轻量校验/索引 CLI
- 明确的进度条与 cache hit/miss 日志

### Out of Scope

- 其他数据集的预处理架构变更
- 修改 `config/`
- 生成 `gwd30_YYYY.nc` standardized files 作为 Phase 4 主输入
- 改写 Berkeley / TOPMODEL / WAD2M / GIEMS-MC 的加载链
- 新增 GUI 或非 HPC 工作流

## 背景判断

### 现状问题

当前 Phase 4 regional 的 `gwd30` 路径：

1. 以区域 bbox + 区域 base mask 为 reference grid
2. 调 `stage_time_fraction_tiles(..., skip_existing=True)`
3. 如果当前区域目录没有现成 `tile_*.nc`，就会重新扫 raw TIFF 并重 stage

这会导致两个问题：

1. **缓存碎片化**
   同一年的同一批 raw tile，会按不同 `region_id` 重复产生 staged partials。
2. **无法稳定复用旧成果**
   即使 HPC 上已有 `standardized/_staging/gwd30_<year>/stage_shard_*.json` 与 `tile_partials/tile_*.nc`，Phase 4 也不会去读它们。

### 已确认的代码漏洞

1. **Regional 路径完全没接 standardized staging root**

   [phase4_regional.py](/Users/mac/Code/WA/src/WA/comparison/phase4_regional.py) 当前把 `gwd30_cache_dir` 当成自己的临时 root，用：

   - [phase4_regional.py:845](/Users/mac/Code/WA/src/WA/comparison/phase4_regional.py#L845)
   - [phase4_regional.py:848](/Users/mac/Code/WA/src/WA/comparison/phase4_regional.py#L848)

   生成 `<gwd30_cache_dir>/<region_id>/gwd30_<year>/tile_partials`

   这与 HPC 既有目录：

   - `.../standardized/_staging/gwd30_<year>/stage_shard_*.json`
   - `.../standardized/_staging/gwd30_<year>/tile_partials/tile_*.nc`

   完全不是一套路径约定。

2. **Trend 路径也没接 standardized staging root**

   [trends.py](/Users/mac/Code/WA/src/WA/comparison/trends.py) 当前使用：

   - [trends.py:200](/Users/mac/Code/WA/src/WA/comparison/trends.py#L200)
   - [trends.py:208](/Users/mac/Code/WA/src/WA/comparison/trends.py#L208)

   生成 `<cache_dir>/<bbox_grid_token>/gwd30_<year>/tile_partials`

   这仍然绕开了现有 `standardized/_staging/gwd30_<year>`。

3. **已有 restore helper 没被 Phase 4 使用**

   现成的 shard-manifest 恢复 helper 在：

   - [standardize.py:598](/Users/mac/Code/WA/src/WA/standardize.py#L598)

   Phase 3.6 已经正确接入：

   - [phase36.py:468](/Users/mac/Code/WA/src/WA/comparison/phase36.py#L468)

   但 Phase 4 regional / trend 还在自己调用 `stage_time_fraction_tiles(...)`，没有先 restore 既有 manifests。

### 关键设计判断

`gwd30` 的 canonical stage cache 已经存在于 HPC standardized staging root。Phase 4 该绑定到：

- **固定 reference grid**
- **固定 full-domain bbox**
- **固定 cache version**

而不是绑定到：

- 单个 region
- 单次 probe
- 单个 plotting run

## 设计方案

## 1. Canonical Stage Root

统一目录应直接采用现有 HPC staging root，例如：

```text
/lustre/home/2200013429/Wetland_Assemble/data/standardized/
  _staging/
    gwd30_2013/
      stage_shard_0000_of_0064.json
      ...
      tile_partials/
    gwd30_2014/
      ...
    ...
    gwd30_2022/
      ...
```

如果后续需要本地镜像索引，也应是**附加索引层**，不是再复制一套 `tile_partials/`。

## 2. Canonical Reference Grid

canonical stage grid 的历史产物已经绑定在现有 standardized staging root 上；Phase 4 应遵守这套契约，而不是另起炉灶。

## 3. Manifest / Restore

现有 shard manifests 已经能恢复 `(stage_path, bbox)`。Phase4.1 首先应复用它们，并补足必要校验：

- `year`
- `bbox`
- `resolution_m`
- `shard_count`
- tile 文件存在性

调用方能力应是：

1. 直接从 manifest 恢复 `list[(stage_path, bbox)]`
2. 按 bbox 筛选 candidate staged tiles
3. 在 manifest 缺失时明确报错，而不是直接回到 raw TIFF 扫描

## 4. Phase 4 Regional Integration

`src/WA/comparison/phase4_regional.py` 调整为：

1. 优先从 `standardized/_staging/gwd30_<year>/stage_shard_*.json` 恢复 staged tiles
2. 用 region bbox 从 manifest 中筛选候选 tiles
3. 直接读取这些 staged partial 计算区域 monthly `wetland_area / valid_area / wetland_percentage`
4. 如果该年 manifest 缺失，再显式报错或在允许模式下回退

默认模式建议是：

- **分析脚本不偷偷重建 raw -> stage**
- 如果 canonical stage cache 缺年，直接提示用户检查 `standardized/_staging/gwd30_<year>`

这样可以把“预处理”和“分析”职责分开。

## 5. Trend Path Integration

`src/WA/comparison/trends.py` 现在已有 staged-tile 路径，但 cache root 与 regional 路径不同。Phase 4.1 应统一它们：

- `regional` 与 `trend` 都先从现有 standardized staging root restore staged tiles
- trend 侧不再维护另一套按 `bbox/reference_grid token` 切分的 tile partial 目录
- 如需保留 bbox 级 merged cache，可作为 staged cache 之上的第二层缓存，而不是重复 stage

## 6. HPC Validation / Index CLI

新增脚本，例如：

- `scripts/check_phase41_gwd30_stage_cache.py`

职责：

1. 检查 `standardized/_staging/gwd30_<year>/stage_shard_*.json`
2. 汇总 manifest 中引用的 `tile_*.nc` 是否齐全
3. 输出每年 staged tile 数、manifest 数、缺失 tile 数
4. 为 Phase4 regional / trend 生成可选索引摘要

建议参数：

```text
--years 2013 2014 ... 2022
--standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized
--skip / --no-skip
--progress / --no-progress
```

## 计划文件清单

### 新增

| 文件 | 说明 |
|------|------|
| `scripts/check_phase41_gwd30_stage_cache.py` | 检查 standardized staging root 是否完整可复用 |
| `tests/test_phase4_1_gwd30_stage.py` | Phase4.1 集成测试 |

### 修改

| 文件 | 说明 |
|------|------|
| `src/WA/loaders/gwd30.py` | staged manifest 写入/恢复、bbox 筛选 helper |
| `src/WA/comparison/phase4_regional.py` | 改为读取 canonical Phase4.1 staged cache |
| `src/WA/comparison/trends.py` | 改为复用 canonical Phase4.1 staged cache |
| `tests/test_loaders/test_gwd30.py` | manifest / restore / cache reuse 回归测试 |
| `tests/test_comparison/test_phase4_regional.py` | regional 路径改用 prestaged tiles 的测试 |
| `tests/test_comparison/test_trends.py` | trend 路径复用 Phase4.1 stage cache 的测试 |

## 执行任务

### Task 4.1.1: Loader 侧 staged manifest 能力

- 复用现有 `_load_gwd30_staged_tiles_from_stage_shard_manifests(...)`
- 提供更明确的公开 helper：
  - `load_gwd30_staged_tiles_from_standardized_dir(...)`
  - `filter_staged_time_fraction_tiles_by_bbox(...)`
- 日志要求：
  - `manifest hit`
  - `manifest miss`
  - `standardized staging root hit`
  - `raw fallback blocked`

### Task 4.1.2: Standardized staging 校验 CLI

- 新建 `scripts/check_phase41_gwd30_stage_cache.py`
- 默认检查完整年份 `2013-2022`
- 每年输出：
  - manifest count
  - staged tile count
  - missing tile count
  - duplicated tile count

### Task 4.1.3: Regional workflow 接 canonical cache

- 去掉 `region_id/year` 级的 GWD30 stage root 作为主缓存
- 改为：
  - standardized staging root
  - region-level统计 cache
- 如果 standardized manifests 缺失，明确报错，不静默重建全域 cache

### Task 4.1.4: Trend workflow 接 canonical cache

- `hpc_probe_trends.py` / `trends.py` 改为读 Phase4.1 root
- 如仍需 bbox 级 merged cache，只保留在 staged cache 之上的第二层

### Task 4.1.5: 日志与进度条

- validation CLI：year-level summary
- consumer CLI：明确打印
  - `using standardized staged cache`
  - `candidate tile count`
  - `no raw staging performed`

## 成功标准

1. 校验 CLI 能确认 `standardized/_staging/gwd30_2013..2022` manifests 与 `tile_partials` 可用。
2. 之后运行 Phase 4 regional 时，不再出现“重新扫 raw TIFF 后 `reused 0 staged tile(s)`”这种冷启动行为。
3. 2013 年区域 run 的 HPC 日志中，应能看到“直接从 standardized manifests 恢复 staged tiles”。
4. regional / trend 都不会再创建新的 Phase4 专用 `tile_partials/` 根目录。
5. 全量测试通过：`python -m pytest tests/`。

## 风险

1. **manifest 过期**
   如果 raw 数据或 stage 逻辑变更，manifest / staged tiles 需要版本化失效。
2. **跨路径兼容**
   regional 与 trend 共享 root 后，cache key 设计必须稳定，否则容易再次分叉。
3. **历史 manifest 契约不足**
   现有 restore helper 还没有严格校验 `bbox / resolution_m / shard_count` 一致性。

## 验证

### 代码级

- `ruff check src/WA/loaders/gwd30.py src/WA/comparison/phase4_regional.py src/WA/comparison/trends.py scripts/prestage_phase41_gwd30.py tests/test_loaders/test_gwd30.py tests/test_comparison/test_phase4_regional.py tests/test_comparison/test_trends.py`
- `python -m pytest tests/test_loaders/test_gwd30.py tests/test_comparison/test_phase4_regional.py tests/test_comparison/test_trends.py -q`
- `python -m pytest tests/`

### HPC 级

先检查现有 standardized staging root：

```bash
python scripts/check_phase41_gwd30_stage_cache.py \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized
```

再跑一个区域 smoke test，确认不再触发 raw stage：

```bash
python scripts/run_phase4_regional.py \
  --region amazon \
  --dataset-id gwd30 \
  --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
  --output-root results/phase4 \
  --figures-root results/figures/phase4 \
  --no-skip
```

## Next Step

先实现 `Task 4.1.1 + Task 4.1.3`，因为现成 manifests 已经在 HPC 上存在，当前最高优先级不是重做 prestage，而是把 Phase 4 regional 接到 standardized staging root。
