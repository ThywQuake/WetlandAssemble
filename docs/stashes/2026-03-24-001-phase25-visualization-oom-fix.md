# Phase 2.5 可视化 OOM 修复

**Date:** 2026-03-24
**Branch:** `feat/phase3-fine-grained-entropy-s2`
**Status:** 已修复 Phase 2.5 面板生成中的主要 OOM 根因，测试通过

---

## Key Changes

| File | Change |
|------|--------|
| `scripts/plot_comparison_panels.py` | 读取 `focus_areas.csv` 的 `target_time`，动态数据集只加载目标月份；每个 AOI 后主动回收内存 |
| `src/WA/visualization/comparison_panel.py` | 新增 `load_native_wetland_surface()`；GWD30 改走 1km 低内存显示路径；动态数据集按月裁剪 |
| `src/WA/loaders/gwd30.py` | `load()` 在给定 `time_range` 时只读取对应 band window，不再无条件打开全年 92 band |
| `tests/test_visualization/test_comparison_panel.py` | 新增动态数据集按 `target_time` 取月的回归测试 |
| `tests/test_loaders/test_gwd30.py` | 新增 GWD30 late-month band window 选择测试 |

## Root Cause

本次 OOM 主要来自两个实现偏差：

1. `plot_comparison_panels.py` 之前忽略了 `focus_areas.csv` 中的 `target_time`，导致 SWAMPS / GIEMS / WAD2M / TOPMODEL / GWD30 等动态数据集按**全时序**加载，而不是只取 focus area 对应月份。
2. GWD30 在 Phase 2.5 可视化里本应以 **~1km** 显示，但之前实际上走的是原始高分辨率加载路径；并且 loader 在给定 `time_range` 时仍会读取全年 band，再在内存里裁切月份。

## Implementation Notes

- 动态数据集现在统一构建目标月 `time_range`，避免在可视化阶段 materialize 全时序。
- GWD30 可视化现在复用 `load_rough_binary_surface()`，直接投影到约 1km 的 WGS84 display grid，避免 30m 原生面板导致的大内存峰值。
- `GWD30Loader.load()` 现在会依据 `_selected_band_window()` 只打开请求月份对应 band，提高一般时间窗读取效率，不只对 Phase 2.5 生效。
- 每个 AOI 绘图后会清空 `dataset_surfaces` 并执行 `gc.collect()`，降低长批次运行的 RSS 累积。

## Verification

- `uv run python -m pytest tests/` ✅ `157 passed`
- `uv run python -m pytest tests/test_visualization/test_comparison_panel.py tests/test_loaders/test_gwd30.py` ✅ `17 passed`
- `uv run python scripts/plot_comparison_panels.py --help` ✅
- `uv run ruff check .` ⚠️ 未通过，但失败点是仓库里已有的无关问题：
  - `scripts/hpc_probe_trends.py`
  - `tests/test_comparison/test_trend_agreement.py`
  - `tests/test_comparison/test_trends.py`

## Open Risks / TODOs

- 这次修复解决的是**可视化阶段**最明显的时序全量加载与 GWD30 高分辨率显示问题；真实 HPC 批量跑图仍建议先小样本验证 2–3 个 AOI 的峰值内存。
- `swamps: SKIP ('fw')` 现象是否完全消失，仍需在 HPC 实际数据上复核；本地回归已覆盖“按目标月加载”逻辑，但未覆盖你集群上的原始文件异构性。
- `ruff` 当前存在仓库既有问题，和本次 OOM 修复无关，未在此顺手处理。

## Suggested Next Step

先在 HPC 上挑 2 个历史最慢 AOI 重跑：

```bash
uv run python scripts/plot_comparison_panels.py \
  --phase2-root results/phase2/rough \
  --output-dir results/figures \
  --year 2016
```

重点观察：

- `gwd30` 是否从 `SKIP (Read failed...)` 变为正常输出或至少不再触发 OOM
- 单个 AOI 的耗时是否明显下降
- 第 7 个以后 AOI 是否还能稳定继续运行
