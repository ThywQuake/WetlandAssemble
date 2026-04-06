# 2026-03-29 GWD30 树形合并重构 - 职责分离

## 问题
之前将树形合并逻辑直接写在 `GWD30Loader` 中，违反了单一职责原则：
- `GWD30Loader` 的职责是加载/处理数据
- 树形合并是通用的归约操作，应该独立

## 方案

### 1. 创建通用树形合并工具 `src/WA/utils/tree_reduce.py`
- `tree_reduce()` - 通用树形归约函数
- `merge_gwd30_staged_tiles()` - GWD30 专用的合并函数

### 2. 创建专用合并脚本 `scripts/merge_gwd30_regions.py`
- 独立 CLI 工具，手动执行
- 支持 `--cleanup` 手动控制清理
- 支持 `--dry-run` 预览

### 3. 简化 `src/WA/loaders/gwd30.py`
- 移除 `_tree_reduce_staged_tiles()`
- 移除 `_merge_two_staged_tiles()`
- 移除 `_build_regional_index()`
- 移除 `_region_key_for_bbox()`
- `stage_time_fraction_tiles()` 只返回原始 tiles

### 4. 一键式脚本 `scripts/standardize_gwd30.py`
- Stage → Tree-Reduce → Final Merge 一体化
- 直接输出 `gwd30_YYYY.nc` 年尺度文件

## 使用方式

### 一键式（推荐）
```bash
# 单一年份
python scripts/standardize_gwd30.py --year 2016 --output-dir output/standardized

# 多年份
python scripts/standardize_gwd30.py --years 2016 2017 2018 --workers 8

# 自定义 bbox 和分辨率
python scripts/standardize_gwd30.py --year 2016 \
    --bbox -180 -35 180 35 \
    --resolution 500 \
    --output-dir output/standardized
```

### 分步式（高级用户）

#### Stage 阶段（生成 tiles）
```python
from WA.loaders import get_loader
from WA.standardize import build_reference_grid

reference_grid = build_reference_grid(bbox, resolution_m=500)
loader = get_loader("gwd30", config)

staged_tiles = loader.stage_time_fraction_tiles(
    bbox=bbox,
    reference_grid=reference_grid,
    year=2016,
    staging_dir=Path("output/standardized/_staging/gwd30_2016/tile_partials"),
)
# staged_tiles: 10260 个 tile_*.nc 文件
```

#### Merge 阶段（树形归约）
```bash
# 手动执行树形合并
python scripts/merge_gwd30_regions.py \
    --staging-dir output/standardized/_staging/gwd30_2016/tile_partials \
    --target-count 30 \
    --workers 8 \
    --cleanup  # 可选：合并成功后删除原始 tiles
```

#### 最终 Merge 阶段（生成 chunk）
```python
from WA.loaders import get_loader
from WA.standardize import build_reference_grid

# 读取 regional manifest
import json
with open(staging_dir / "regional_manifest.json") as f:
    manifest = json.load(f)
regional_tiles = [(Path(item["path"]), tuple(item["bbox"])) for item in manifest["regional_tiles"]]

# 合并 chunks
reference_grid = build_reference_grid(bbox, resolution_m=500)
loader = get_loader("gwd30", config)

chunk_dataset = loader.merge_staged_time_fraction_tiles(
    staged_tiles=regional_tiles,  # ~30 个 files
    reference_grid=reference_grid,
    bbox=chunk_bbox,
    year=2016,
)
```

## 优势

1. **职责分离**: Loader 只负责数据处理，合并逻辑独立
2. **一键式**: `standardize_gwd30.py` 自动完成全部流程
3. **分步式**: 高级用户可手动控制每个阶段
4. **可复用**: `tree_reduce()` 可用于其他数据集
5. **安全性**: 原始 tiles 只在用户确认 `--cleanup` 后删除

## Validation
- `python -m py_compile src/WA/utils/tree_reduce.py` ✓
- `python -m py_compile scripts/merge_gwd30_regions.py` ✓
- `python -m py_compile scripts/standardize_gwd30.py` ✓
- `python -m pytest tests/test_loaders/test_gwd30.py -q` - 21 passed ✓
- `python -m pytest tests/ -q` - 262 passed ✓
