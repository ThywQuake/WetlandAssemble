# Phase 3.7 Global 500m Handoff

**Date:** 2026-04-01
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** Phase 3.7 全局绘图已切换为 500m 原网格稀疏采样口径，不重投影；当前版式为 2列3行大图 + 底部三块 legend/colorbar，且已继续压缩子图上下间距、放大底部 legend。

---

## Key Changes

| File | Change |
|------|--------|
| `src/WA/visualization/phase37.py` | 新增/重写 Phase 3.7 全局绘图 helper，直接对 Phase 3.6 的 500m `lat/lon` 网格做 `sample_step` 稀疏采样，不做 0.25° 聚合、不重投影 |
| `src/WA/visualization/phase37.py` | 输出布局固定为 2列3行：`Entropy / Agreement Count / Majority Class` 对 `G2017 / GLWD v2 / GWD30`，底部附 `8类 legend + Entropy colorbar + Agreement Count legend` |
| `src/WA/visualization/phase37.py` | 继续收紧子图上下间距，并放大底部 legend / colorbar 字号与元素尺寸 |
| `scripts/plot_phase3_7_metrics.py` | CLI 参数改为 `--sample-step`，默认 `dpi=300`，输出/缓存文件名改为 `sampleN` 口径 |
| `tests/test_phase3_7_plotting.py` | 新增/更新测试，覆盖 `sample_step=1` 原值保留、`sample_step=2` 稀疏采样、不重投影缓存写出、CLI 出图 |
| `docs/stashes/2026-04-01-001-phase37-global-500m-sparse-plotting.md` | 记录 Phase 3.7 从 0.25° 展示重采样切换到 500m 稀疏采样的实现总结 |

## Verification

- `ruff check src/WA/visualization/phase37.py scripts/plot_phase3_7_metrics.py tests/test_phase3_7_plotting.py` → clean
- `python -m pytest tests/test_phase3_7_plotting.py -q` → `5 passed`
- `python -m pytest tests/ -q` → `357 passed`
- HPC: 尚未复跑 Phase 3.7 全局图；推荐先用 `sample_step=8`

## Open Risks / TODOs

- `sample_step=8` 仍可能生成较大的 PNG；若 HPC 出图慢或文件过大，可调到 `12` 或 `16`
- 当前有缓存提示和条带进度日志，但没有 tqdm 进度条，也没有并行绘图
- 局部绘图尚未开始，用户表示另有想法

## Next Steps

1. HPC 运行：`python scripts/plot_phase3_7_metrics.py --input-dir results/phase3.6 --output-dir results/figures/phase3.7 --cache-dir results/cache/phase3_7 --year 2016 --sample-step 8 --source-lat-chunk-size 512 --dpi 300`
2. 根据首版 PNG 结果继续微调全局图版式，优先考虑继续压地图区或重排底部 legend
3. 等用户明确局部绘图方案后再进入 Phase 3.7 的 regional work
