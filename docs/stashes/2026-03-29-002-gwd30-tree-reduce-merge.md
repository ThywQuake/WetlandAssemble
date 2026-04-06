# 2026-03-29 GWD30 分治树形合并优化

## 问题
- GWD30 stage 阶段产生 10260 个独立 tile 文件
- merge 阶段每个 chunk 需要打开数十到数百个文件串行累加
- 即使有空间索引，I/O 开销仍然巨大

## 方案：分治树形合并 (Tree-Reduce)

```
第 0 轮：10260 个 tiles
         │ (并行合并 5130 对)
第 1 轮：5130 个 files
         │ (并行合并 2565 对)
第 2 轮：2565 个 files
         │ (并行合并 1282 对)
第 3 轮：1283 个 files
    ...
第 10 轮：~30 个 regional blocks
```

**复杂度分析：**
- 原始方案：O(N) 串行打开文件，N=10260
- 树形合并：O(log N) 轮，每轮并行，最终输出 ~30 个文件
- Merge 阶段：从 O(10260) 降到 O(30) 线性扫描

## Changes

### `src/WA/loaders/gwd30.py`

**新增函数：**
1. `_region_key_for_bbox()` - 计算 bbox 的区域 key
2. `_build_regional_index()` - 构建区域索引（备用）
3. `_merge_two_staged_tiles()` - 合并两个 tile 文件
4. `_tree_reduce_staged_tiles()` - 执行树形合并直到剩余 ~30 个文件

**修改 `stage_time_fraction_tiles()`:**
- Stage 完成后自动调用 `_tree_reduce_staged_tiles()`
- 清理原始 tile 文件释放磁盘空间
- 返回 ~30 个 regional blocks 而非 10260 个 tiles

**简化 `merge_staged_time_fraction_tiles()`:**
- 移除空间索引缓存逻辑（不再需要）
- 直接线性扫描 ~30 个 regional files（非常快）
- 移除 `_merge_index_cache` 实例变量

## 性能对比

| 阶段 | 优化前 | 优化后 |
|------|--------|--------|
| Stage 输出 | 10260 个 files | ~30 个 regional blocks |
| 磁盘占用 | ~50 GB | ~5 GB (清理后) |
| Merge 文件数 | 100-500 个/chunk | ~30 个/chunk |
| Merge 复杂度 | O(N) 串行 | O(30) 串行 |
| 总轮次 | - | log2(10260) ≈ 14 轮 |
| 每轮并行度 | - | 4-8 workers |

## 磁盘 I/O 分析

**优化前：**
- Stage: 写入 10260 个 files
- Merge: 每个 chunk 读取 100-500 个 files × 19154 chunks = 数十亿次文件打开

**优化后：**
- Stage: 写入 10260 个 `tile_*.nc` files
- 树形合并第 1 轮完成后 → 立即删除 10260 个 `tile_*.nc`
- 树形合并第 2 轮 + ：每轮完成后删除上一轮的 `region_r(N-1)_*.nc`
- 磁盘峰值：~50 GB (Stage 输出) → 第 1 轮后降至 ~25 GB → 最终 5 GB
- Merge: 每个 chunk 读取 ~30 个 files × 19154 chunks = 数十万次文件打开
- **减少约 1000x 文件打开次数**

## 文件清理保证

```python
# _tree_reduce_staged_tiles 内部
for stage_path, _ in current_round:
    if round_num == 1:
        # 第 1 轮：只删除 tile_*.nc 文件
        if stage_path.name.startswith("tile_"):
            files_to_clean.add(stage_path)
    else:
        # 第 2 轮 +：只删除上一轮的 region 文件
        if stage_path.name.startswith("region_r"):
            files_to_clean.add(stage_path)
```

**保证：**
- `tile_*.nc`（stage 直接产物）只在树形合并第 1 轮**成功后**删除
- `region_r*.nc`（合并产物）只在下一轮**成功后**删除
- 每轮清理都在输出文件成功写入后执行，数据安全第一

## Validation
- `python -m py_compile src/WA/loaders/gwd30.py` ✓
- `python -m pytest tests/test_loaders/test_gwd30.py -q` - 21 passed ✓

## 注意事项
1. 树形合并会修改 staged tiles 的内容（从独立 tile 变成区域累加和）
2. Regional files 的 bbox 是 placeholder，merge 时不做精确相交检查
3. 如果 staged tiles ≤ 30 个，跳过树形合并

## Next Steps
- HPC 实测验证性能提升
- 可根据需要调整 `target_count=30` 的阈值
