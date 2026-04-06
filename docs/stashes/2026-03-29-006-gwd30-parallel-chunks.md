# GWD30 并行化优化 - Chunk 级并行

## 性能瓶颈分析

原脚本的性能瓶颈：
- **Stage 阶段**: 已并行（ProcessPoolExecutor）✓
- **Tree-Reduce 阶段**: 已并行（ProcessPoolExecutor）✓
- **Chunk Merge 阶段**: **串行**处理 19154 个 chunks ← 瓶颈！

## 优化方案

### 并行化 Chunk Merge

```python
# 之前：串行处理
for chunk in chunks:  # 19154 次循环
    build_chunk(chunk)  # 串行

# 现在：并行处理
with ProcessPoolExecutor(max_workers=chunk_workers) as executor:
    futures = {executor.submit(build_chunk, chunk): chunk for chunk in chunks}
    for future in as_completed(futures):
        # 并行完成
```

## 使用方式

```bash
# 使用 8 个 worker 并行构建 chunks
python scripts/standardize_gwd30.py --year 2016 --chunk-workers 8

# 同时调整 tree-reduce 和 chunk 的 worker 数
python scripts/standardize_gwd30.py --year 2016 \
    --reduce-workers 4 \
    --chunk-workers 8

# 自动检测 CPU 核心数
python scripts/standardize_gwd30.py --year 2016 --chunk-workers 0
```

## 性能提升预估

| 配置 | Chunk Merge 时间 | 总时间 |
|------|-----------------|--------|
| 串行 (1 worker) | ~60 分钟 | ~90 分钟 |
| 4 workers | ~15 分钟 | ~45 分钟 |
| 8 workers | ~8 分钟 | ~38 分钟 |
| 16 workers | ~4 分钟 | ~34 分钟 |

**注意**: 超过一定 worker 数后，I/O 瓶颈会限制进一步提升。

## 内存考虑

每个 worker 需要：
- 加载 ~30 个 regional files 的元数据
- 每个 chunk 约 50-100 MB 内存

建议：
- 4 workers: 需要 ~2-4 GB 额外内存
- 8 workers: 需要 ~4-8 GB 额外内存
- 16 workers: 需要 ~8-16 GB 额外内存

## 新增参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--chunk-workers` | 4 | Chunk 并行 worker 数量 |
| `--reduce-workers` | 4 | Tree-reduce 并行 worker 数量 |

## 完整示例

```bash
# HPC 上，使用 32 核
python scripts/standardize_gwd30.py --year 2016 \
    --reduce-workers 8 \
    --chunk-workers 24 \
    --output-dir output/standardized

# 本地测试，使用 4 核
python scripts/standardize_gwd30.py --year 2016 \
    --reduce-workers 2 \
    --chunk-workers 2 \
    --output-dir output/test
```

## Validation
- `python -m py_compile scripts/standardize_gwd30.py` ✓
- `python -m pytest tests/ -q` - 262 passed ✓
