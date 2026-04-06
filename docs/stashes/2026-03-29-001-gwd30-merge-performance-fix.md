# 2026-03-29 GWD30 Merge Performance Fix (Superseded)

**注意：此方案已被 `2026-03-29-002-gwd30-tree-reduce-merge.md` 的分治树形合并方案替代。**

## Context
- GWD30 merge 阶段卡死：19154 个 chunk 串行处理，每个 chunk 线性扫描全部 10259 个 staged tiles
- 海洋/无数据 chunk 瞬间完成（抛 FileNotFoundError），但有数据的 chunk 需要数分钟
- 估算总耗时：数小时到数十小时

## Root Cause
1. **无空间索引** - 每个 chunk 对全部 10259 tiles 做 `_bbox_intersects` 线性扫描 O(N)
2. **串行 merge** - `max_workers=1` 硬编码在 `_standardize_gwd30` 中
3. **重复元数据读取** - 每个 tile 都单独 `xr.open_dataset` + `.reindex()` + `np.asarray()`

## Changes (部分仍保留)

### `src/WA/standardize.py`
1. **启用 chunk 并行**: ✅ 保留
   - 将 `max_workers=1` 改为 `_chunk_parallel_worker_count(loader.dataset_id)`

### `src/WA/loaders/gwd30.py`
1. **空间索引**: ❌ 已移除（树形合并后只需处理 ~30 个文件，不再需要）
2. **索引缓存**: ❌ 已移除
3. **预读取坐标**: ✅ 保留

## 新方案：分治树形合并

见 `docs/stashes/2026-03-29-002-gwd30-tree-reduce-merge.md`

**核心改进：**
- Stage 完成后自动执行 log2(10259)≈14 轮并行合并
- 输出从 10259 个 tiles 减少到 ~30 个 regional blocks
- 清理原始 tiles 释放磁盘空间
- Merge 阶段从 O(10259) 降到 O(30)

## Validation
- `python -m pytest tests/ -q` - 262 passed ✓
