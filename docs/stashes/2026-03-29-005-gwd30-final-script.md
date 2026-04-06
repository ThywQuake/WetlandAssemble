# GWD30 一键式标准化脚本 - 最终版本

## 脚本：`scripts/standardize_gwd30.py`

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

### 执行流程

```
┌─────────────────────────────────────────────────────────────┐
│  python scripts/standardize_gwd30.py --year 2016            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Stage 阶段                                           │
│ 10260 个 TIFF → tile_partials/tile_*.nc                      │
│ 磁盘：+50 GB                                                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Tree-Reduce 阶段                                     │
│ 10260 tiles → ~30 regional_*.nc                             │
│ 磁盘：+5 GB (tile_*.nc 保留)                                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Chunk Merge 阶段                                     │
│ ~30 regional files → 19154 chunk_*.nc                       │
│ 磁盘：+10 GB (峰值 65 GB)                                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Final Merge 阶段                                     │
│ 19154 chunks → gwd30_2016.nc                                │
│ 磁盘：+8 GB, chunks 自动删除                                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 5: 完成 (文件保留)                                       │
│ 脚本输出提示，等待用户验证后手动清理：                        │
│   - tile_partials/ (10260 个 files)                          │
│   - regional/ (~30 个 files)                                  │
└─────────────────────────────────────────────────────────────┘
```

### 完成后的日志

```
2026-03-29 15:35:00 INFO     WA: GWD30 2016: complete -> output/standardized/gwd30_2016.nc
2026-03-29 15:35:00 INFO     WA: GWD30 2016: staged files preserved for verification:
2026-03-29 15:35:00 INFO     WA:   - tile_partials: 10260 tile_*.nc files in output/standardized/_staging/gwd30_2016/tile_partials
2026-03-29 15:35:00 INFO     WA:   - regional: 30 files in output/standardized/_staging/gwd30_2016/regional
2026-03-29 15:35:00 INFO     WA: To reclaim disk space, manually delete these directories after verification.
```

### 手动清理命令

```bash
# 验证输出文件正确后
rm -rf output/standardized/_staging/gwd30_2016/tile_partials
rm -rf output/standardized/_staging/gwd30_2016/regional

# 或者清理整个年份的 staging 目录
rm -rf output/standardized/_staging/gwd30_2016
```

### 关键特性

1. **一键式**: 单个命令完成全部流程
2. **数据安全**: 只在最终 output 成功后才提示清理
3. **用户控制**: staged 文件保留，用户验证后手动删除
4. **可恢复**: 添加 `--skip-existing` 可跳过已完成的阶段

### 文件清单

| 文件 | 用途 |
|------|------|
| `scripts/standardize_gwd30.py` | 一键式脚本 |
| `scripts/merge_gwd30_regions.py` | 分步式树形合并（可选） |
| `src/WA/utils/tree_reduce.py` | 通用树形合并工具 |

### Validation
- `python -m py_compile scripts/standardize_gwd30.py` ✓
- `python -m pytest tests/ -q` - 262 passed ✓
