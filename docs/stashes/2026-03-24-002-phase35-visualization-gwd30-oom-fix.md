# Phase 3.5 GWD30 OOM 修复

**Date:** 2026-03-24  
**Branch:** `feat/phase3-fine-grained-entropy-s2`  
**Status:** 已修复 `plot_phase3_panels.py` 在 HPC 上因 GWD30 全时序/高内存加载导致的 OOM 主因

## Root Cause

`Phase 3.5` 面板脚本此前对 `gwd30` 直接执行 `loader.load(bbox=bbox)`，会把 hotspot 范围内的多时相高分辨率数据整体载入，再做 temporal mode / 500m 聚合，导致单热点就可能触发 OOM。

## Key Changes

| File | Change |
|------|--------|
| `scripts/plot_phase3_panels.py` | 新增 `--gwd30-year` / `--gwd30-workers`；对 `gwd30` 改走低内存 coarse-grid 分类加载；每个 hotspot 后主动关闭 dataset 并 `gc.collect()` |
| `src/WA/loaders/gwd30.py` | 新增 `load_fine_classification_grid()`：按 tile 做 band-by-band 统计 → 30m temporal mode → coarse-grid class fractions / dominant class |
| `src/WA/visualization/panel.py` | `compute_vote_classification()` / `load_native_classification()` 支持直接消费预计算 `class_fractions`，避免对 `gwd30` 二次高内存重采样 |
| `tests/test_loaders/test_gwd30.py` | 新增低内存 fine-classification grid 回归测试 |
| `tests/test_visualization/test_panel.py` | 新增预计算 `class_fractions` 路径回归测试 |

## Verification

- `uv run python -m pytest tests/test_loaders/test_gwd30.py tests/test_visualization/test_panel.py` ✅ `23 passed`
- `uv run python -m pytest tests/` ✅ `160 passed`
- `uv run ruff check scripts/plot_phase3_panels.py src/WA/loaders/gwd30.py src/WA/visualization/panel.py tests/test_visualization/test_panel.py tests/test_loaders/test_gwd30.py` ✅
- `python scripts/plot_phase3_panels.py --help` ✅

## Remaining Notes

- 仓库级 `uv run ruff check .` 仍有既有无关问题，集中在：
  - `scripts/hpc_probe_trends.py`
  - `tests/test_comparison/test_trend_agreement.py`
  - `tests/test_comparison/test_trends.py`
- `plot_phase3_panels.py` 现在默认 `--gwd30-workers 1`，优先保守避免 OOM；若节点内存充足，可手动上调。

## Suggested HPC Retry

```bash
python scripts/plot_phase3_panels.py \
  --phase3-root results/phase3/fine/probe \
  --output-dir results/figures/phase3 \
  --gwd30-workers 1
```

如需显式锁定 GWD30 年份：

```bash
python scripts/plot_phase3_panels.py \
  --phase3-root results/phase3/fine/probe \
  --output-dir results/figures/phase3 \
  --gwd30-year 2016 \
  --gwd30-workers 1
```
