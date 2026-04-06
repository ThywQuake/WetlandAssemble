# Phase 3.7 Regional Panels Entry

**Date:** 2026-04-01
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** 进入 Phase 3.7 regional work；新增基于 `priority_regions` 的区域批量出图入口，复用 Phase 3.7 的 sparse cache 与 3x2 disagreement layout。

---

## Key Changes

| File | Change |
|------|--------|
| `src/WA/visualization/phase37.py` | 新增 `subset_phase37_plot_dataset_to_bbox(...)`，支持按 region bbox 从 Phase 3.7 sparse plot dataset 裁剪子区域 |
| `scripts/plot_phase3_7_regional_panels.py` | 新增区域批量出图脚本；复用全局 sparse cache，按 `config/priority_regions.yaml` 批量输出每个 region 的 3x2 disagreement figure |
| `tests/test_phase3_7_regional_panels.py` | 新增测试，覆盖 descending-lat bbox 裁剪与 regional script 出图 |

## Verification

- `ruff check src/WA/visualization/phase37.py scripts/plot_phase3_7_regional_panels.py tests/test_phase3_7_regional_panels.py tests/test_phase3_7_plotting.py`
- `python -m pytest tests/`

## HPC Commands

1. 全局 sparse cache / 全局图：`python scripts/plot_phase3_7_metrics.py --input-dir results/phase3.6 --output-dir results/figures/phase3.7 --cache-dir results/cache/phase3_7 --year 2016 --sample-step 8 --source-lat-chunk-size 512 --dpi 300`
2. 区域图：`python scripts/plot_phase3_7_regional_panels.py --input-dir results/phase3.6 --output-dir results/figures/phase3.7_regions --cache-dir results/cache/phase3_7 --regions-file config/priority_regions.yaml --year 2016 --sample-step 8 --source-lat-chunk-size 512 --dpi 300`

## Notes

- 当前 regional figure 先复用 global 的 3x2 语义与 legend，不额外引入卫星底图，避免在设计未定时过早锁死版式。
- 若后续确认需要 MODIS/GEE 底图，可在这条 regional pipeline 上继续加第 1 面板替换或扩展布局。
