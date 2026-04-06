# Phase 3.7 Hotspot Panels

**Date:** 2026-04-01
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** 已新增 Phase 3.7 hotspot panel 绘图链路：从 hotspot manifest + S2 artifact manifest + Phase 3.6 全局 500m 结果批量输出单热点 panel。

---

## Key Changes

| File | Change |
|------|--------|
| `src/WA/visualization/phase37.py` | 新增 `build_phase37_hotspot_plot_dataset(...)`，直接从 Phase 3.6 全局结果裁单个 hotspot AOI；新增 `plot_phase37_hotspot_panel(...)`，按 `S2 RGB | Entropy | Majority Class / G2017 | GLWD v2 | GWD30` 的 2x3 布局出图 |
| `scripts/plot_phase3_7_hotspot_panels.py` | 新增批量脚本，读取 `phase3_7_hotspots_2016.json` 和 `phase3_7_s2_artifacts_2016_20160701.json`，按 hotspot 输出 PNG |
| `tests/test_phase3_7_hotspot_panels.py` | 新增测试，覆盖 AOI 裁剪、无 S2 占位、S2 artifact join、脚本批量出图 |

## Outputs

- PNG: `results/figures/phase3.7_hotspots/<hotspot_id>_panel.png`

## Verification

- `ruff check src/WA/visualization/phase37.py scripts/plot_phase3_7_hotspot_panels.py tests/test_phase3_7_hotspot_panels.py`
- `python -m pytest tests/test_phase3_7_hotspot_panels.py -q`

## HPC Command

`python scripts/plot_phase3_7_hotspot_panels.py --hotspots-manifest results/phase3.7_hotspots/phase3_7_hotspots_2016.json --s2-artifacts-manifest results/phase3.7_hotspots/phase3_7_s2_artifacts_2016_20160701.json --input-dir results/phase3.6 --output-dir results/figures/phase3.7_hotspots --year 2016 --dpi 300`
