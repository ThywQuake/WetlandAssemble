# GWD30 标准化脚本流程详解

## 一键式脚本：`scripts/standardize_gwd30.py`

### 命令行用法

```bash
# 单一年份
python scripts/standardize_gwd30.py --year 2016 --output-dir output/standardized

# 多年份
python scripts/standardize_gwd30.py --years 2016 2017 2018 --workers 8

# 自定义 bbox 和分辨率
python scripts/standardize_gwd30.py --year 2016 \
    --bbox -180 -35 180 35 \
    --resolution 500 \
    --output-dir output/standardized \
    --reduce-workers 4
```

### 完整执行流程

```
输入：GWD30 源 TIFF 文件 (MGRS 分片，30m 分辨率)
│
├─ Step 1: Stage 阶段
│  ├─ 读取每个源 TIFF
│  ├─ 重投影到参考网格 (500m)
│  ├─ 计算 weighted 和 coverage
│  └─ 输出：staging_dir/tile_partials/tile_*.nc × 10260 个
│
├─ Step 2: Tree-Reduce 阶段
│  ├─ 第 1 轮：10260 tiles → 5130 regional_r01_*.nc
│  ├─ 第 2 轮：5130 → 2565 regional_r02_*.nc
│  ├─ 第 3 轮：2565 → 1283 regional_r03_*.nc
│  ├─ ... (每轮约减半)
│  └─ 第 10 轮：→ ~30 regional_r10_*.nc
│     └─ 保存：staging_dir/regional/manifest.json
│
├─ Step 3: Chunk Merge 阶段
│  ├─ 将参考网格划分为 256×256 的 chunks
│  ├─ 每个 chunk 合并 ~30 个 regional files
│  ├─ 计算最终分数：fractions = weighted_sum / coverage_sum
│  └─ 输出：staging_dir/chunks/chunk_*.nc × ~19154 个
│
├─ Step 4: Final Merge 阶段
│  ├─ 合并所有 chunks 到单一 netCDF
│  ├─ 输出：output_dir/gwd30_2016.nc
│  └─ 删除所有 chunk 文件
│
└─ Step 5: 完成（文件保留）
   ├─ tile_partials/tile_*.nc × 10260 个 ← 保留
   ├─ regional/*.nc × ~30 个 ← 保留
   ├─ chunks/*.nc (已在 Step 4 删除)
   └─ 最终：output_dir/gwd30_2016.nc + staged files

**注意**: 脚本不会自动删除 staged 文件，用户验证输出后手动清理
```

### 日志输出示例

```
2026-03-29 14:00:00 INFO     WA.standardize: Building reference grid: resolution=500m, bbox=(-180, -35, 180, 35)
2026-03-29 14:00:02 INFO     WA.standardize: Reference grid: 15585 lat × 80151 lon
2026-03-29 14:00:02 INFO     WA: GWD30 2016: standardizing gwd30_2016.nc
2026-03-29 14:00:02 INFO     WA.loaders.gwd30: GWD30 2016: discovering source tiles for bbox=(-180, -35, 180, 35)
2026-03-29 14:00:30 INFO     WA.loaders.gwd30: GWD30 2016: 10260 source tile(s) matched after filtering
2026-03-29 14:00:30 INFO     WA.progress: GWD30 2016 stage [--------------------] 0/10260 tile (0%)
... (stage 进度条) ...
2026-03-29 14:10:00 INFO     WA: GWD30 2016: staged 10260 tiles
2026-03-29 14:10:00 INFO     WA: GWD30 2016: tree-reduce 10260 tiles -> ~30 regional files
2026-03-29 14:10:00 INFO     WA.utils.tree_reduce: Tree-reduce round 1: merging 5130 pairs -> 5130 files (target: 30)
... (tree-reduce 进度条) ...
2026-03-29 14:30:00 INFO     WA: GWD30 2016: tree-reduce complete, 30 regional files
2026-03-29 14:30:00 INFO     WA: GWD30 2016: building 19154 chunks
2026-03-29 14:30:00 INFO     WA.progress: gwd30 2016 merge [--------------------] 0/19154 chunk (0%)
... (chunk merge 进度条) ...
2026-03-29 15:30:00 INFO     WA: GWD30 2016: staged 19154 chunks, merging to final output
2026-03-29 15:30:00 INFO     WA: Merging 19154 chunks into gwd30_2016.nc
... (final merge) ...
2026-03-29 15:35:00 INFO     WA: GWD30 2016: cleaning up staged files...
2026-03-29 15:35:30 INFO     WA: GWD30 2016: deleted 29444 staged files
2026-03-29 15:35:30 INFO     WA: GWD30 2016: complete -> output/standardized/gwd30_2016.nc
```

### 磁盘空间变化

| 阶段 | 文件类型 | 数量 | 总大小 | 累计占用 |
|------|---------|------|--------|---------|
| Stage 完成 | tile_*.nc | 10260 | ~50 GB | 50 GB |
| Tree-Reduce 完成 | regional_*.nc | ~30 | ~5 GB | 55 GB |
| Chunk Merge 完成 | chunk_*.nc | ~19154 | ~10 GB | 65 GB (峰值) |
| Final Merge 完成 | gwd30_2016.nc | 1 | ~8 GB | 8 GB |
| Cleanup 完成 | - | - | - | 8 GB |

### 关键保证

1. **数据安全第一**: 只在最终 output 文件成功写入后才删除 staged 文件
2. **原子性**: 如果任何阶段失败，所有 staged 文件保留，可从中断点恢复
3. **可恢复**: 添加 `--skip-existing` 可跳过已完成的阶段

### 分步执行（高级）

如果需要在 merge 后手动检查 staged 文件，使用分步脚本：

```bash
# Step 1: Stage (Python API)
python -c "
from WA.loaders import get_loader
from WA.standardize import build_reference_grid, load_dataset_config

reference_grid = build_reference_grid((-180, -35, 180, 35), resolution_m=500)
loader = get_loader('gwd30', load_dataset_config('config/datasets.yaml')['datasets']['gwd30'])
tiles = loader.stage_time_fraction_tiles(
    bbox=(-180, -35, 180, 35),
    reference_grid=reference_grid,
    year=2016,
    staging_dir=Path('output/standardized/_staging/gwd30_2016/tile_partials'),
)
print(f'Staged {len(tiles)} tiles')
"

# Step 2: Tree-Reduce (手动检查后再执行)
python scripts/merge_gwd30_regions.py \
    --staging-dir output/standardized/_staging/gwd30_2016/tile_partials \
    --workers 8

# 检查 regional files 是否正确
ls -lh output/standardized/_staging/gwd30_2016/regional/

# Step 3: 最终 merge (需要额外脚本或 Python API)
```

### 清理行为对比

| 选项 | tile_*.nc | regional_*.nc | chunk_*.nc | 最终 output |
|------|-----------|---------------|------------|------------|
| `standardize_gwd30.py` (默认) | **保留** | **保留** | 自动删除 | 保留 |
| `merge_gwd30_regions.py` (无 --cleanup) | 保留 | 保留 | N/A | N/A |
| `merge_gwd30_regions.py --cleanup` | 删除 | 保留 | N/A | N/A |

### 手动清理命令

```bash
# 验证输出文件正确后，手动清理 staged 文件
rm -rf output/standardized/_staging/gwd30_2016/tile_partials
rm -rf output/standardized/_staging/gwd30_2016/regional
rm -rf output/standardized/_staging/gwd30_2016/chunks

# 或者清理整个 staging 目录
rm -rf output/standardized/_staging/gwd30_2016
```
