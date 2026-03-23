# Fix: HPC Probe GWD30 OOM

**Date:** 2026-03-23
**Branch:** feat/phase3-fine-grained-entropy-s2
**Status:** 110/110 tests passing, ruff clean, 未提交

---

## 问题

`hpc_probe_fine_grained.py` 在 HPC 上连续两次 OOM：

1. **第一次 OOM:** `get_loader()` 调用签名错误（缺少 `dataset_config` 参数），修复后 GWD30 尝试加载 10 年全量数据 → OOM
2. **第二次 OOM:** 限制为单年（2019）后仍有 393 tiles × 92 temporal bands × 30m 分辨率，`loader.load()` 一次性加载全部 tile → OOM

## 修复

### Bug 修复
- `get_loader(ds_id)` → `get_loader(ds_id, ds_config)` — 补齐 `dataset_config` 参数
- `loader(ds_config)` → `loader.load(bbox=bounds)` — loader 是实例，需调用 `.load()` 方法

### 内存优化：流式逐 tile 处理
将 GWD30 从 `loader.load()` 全量加载改为 `_load_gwd30_streamed()` 流式处理：

1. **逐 tile 加载** — 峰值内存 = 1 tile × 92 bands（而非 393 tiles × 92 bands）
2. **立即 temporal mode** — 向量化 bincount（classes 0-14），92 bands → 1 band
3. **立即粗网格重采样** — `reproject_match(grid, Resampling.mode)` 将 30m 降到 0.25°
4. **累积到结果数组** — 释放 tile 内存，`gc.collect()`

峰值内存降低约 **400 倍**：O(393 × 92 bands × 30m) → O(1 × 92 bands × 30m)

### 与 harmonize 流水线的兼容性
- `_load_gwd30_streamed` 输出无 `time` 维 → `_prepare_fine_source` 跳过 `_temporal_mode`
- 数据已在 comparison grid 分辨率 → `_align_2d_surface` 的 reproject 为 no-op
- 流水线下游无需任何改动

## 修改文件

| 文件 | 变更 |
|------|------|
| `scripts/hpc_probe_fine_grained.py` | 重写 GWD30 加载为流式逐 tile 处理 |

## 验证

- 本地 `uv run pytest`: 110/110 passed
- HPC: 待提交验证

## 已知风险

1. **`reproject_match` 从 30m 到 0.25° 的 mode 重采样** — 极大尺度变化下 `Resampling.mode` 可能不完美，但对分类数据已是最佳选择
2. **单年代表性** — 只用 2019 年，不做跨年 temporal mode；对 probe 诊断足够
