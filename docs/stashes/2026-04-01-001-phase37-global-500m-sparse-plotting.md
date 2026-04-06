# Phase 3.7 Global 500m Sparse Plotting

**Date:** 2026-04-01
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** Phase 3.7 全局图已从 `0.25°` 展示重采样口径改为 `500m` 原网格稀疏采样口径，不重投影，默认 `dpi=300`。

---

## Key Changes

| File | Change |
|------|--------|
| `src/WA/visualization/phase37.py` | 重写 Phase 3.7 全球绘图 helper：直接从 Phase 3.6 的 500m 输出做 `isel(step=...)` 稀疏采样；支持写入稀疏采样缓存；保持 2列3行大图 + 底部三块 legend/colorbar 布局 |
| `scripts/plot_phase3_7_metrics.py` | CLI 参数从 `resolution_deg` 改为 `sample_step`；默认 `dpi=300`；输出/缓存命名改为 `sampleN` 口径 |
| `tests/test_phase3_7_plotting.py` | 新增/更新测试，覆盖 `sample_step=1` 保持原值、`sample_step=2` 稀疏采样、不重投影缓存写出、CLI 出图 |

## Verification

- `ruff check src/WA/visualization/phase37.py scripts/plot_phase3_7_metrics.py tests/test_phase3_7_plotting.py` → clean
- `python -m pytest tests/test_phase3_7_plotting.py -q` → `5 passed`
- `python -m pytest tests/ -q` → `357 passed`

## Open Risks / TODOs

- `sample_step` 太小会让全局图变大、绘图变慢；推荐先从 `8` 或 `12` 起步
- 当前 still uses lat/lon axes directly；若后续想进一步优化观感，可再微调 panel aspect / title spacing / legend layout
- 目前只做了全局图；局部绘图尚未开始

## Next Steps

1. HPC 运行全局图：`python scripts/plot_phase3_7_metrics.py --input-dir results/phase3.6 --output-dir results/figures/phase3.7 --cache-dir results/cache/phase3_7 --year 2016 --sample-step 8 --source-lat-chunk-size 512 --dpi 300`
2. 若出图过慢或文件太大，调大 `--sample-step`
3. 根据首版 PNG 结果再微调配色、标题和底部 legend 布局
