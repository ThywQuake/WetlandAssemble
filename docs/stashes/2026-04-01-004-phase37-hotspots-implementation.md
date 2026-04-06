# Phase 3.7 Hotspots Implementation

**Date:** 2026-04-01
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** 已新增 Phase 3.7 hotspot 主链路：先复用 Phase 3.7 sparse cache 做 coarse AOI 候选，再回原始 Phase 3.6 500m 结果做精修，输出 JSON manifest、CSV summary 和 region-level debug PNG。

---

## Key Changes

| File | Change |
|------|--------|
| `src/WA/phase37_hotspots.py` | 新增 Phase 3.7 hotspot 核心逻辑：priority region 读取、面积加权 quota 分配、coarse sparse-cache AOI 打分、500m 精修、非湿地过滤、去重、AOI 生成、manifest/CSV/debug PNG 写出 |
| `scripts/find_phase3_7_hotspots.py` | 新增 Phase 3.7 hotspot 入口脚本，默认读取 `results/phase3.6/phase3_6_entropy_global_500m_2016.nc`、`phase3_6_unified_classes_global_500m_2016.nc`，并复用 `results/cache/phase3_7` 的 sparse cache |
| `tests/test_phase3_7_hotspots.py` | 新增测试，覆盖 quota 分配、局部阈值、非湿地过滤、近邻去重、AOI 边界裁剪、空 region shortfall、脚本输出 |

## Selection Rules

- 每个 `priority_region` 独立计算 coarse AOI score 的 `95th percentile` 阈值
- 只在 `joint_valid_mask > 0` 且 `majority_class != 0` 的像元中找 hotspot
- coarse 候选来自 Phase 3.7 sparse cache，默认 `sample_step=8`
- coarse 阶段直接对固定 `0.5° x 0.5°` 窗口计算 `mean_entropy`
- 每区先保留一批 coarse 候选，再回原始 500m 数据对同一 AOI 精修 `mean_entropy / max_entropy / cell_count`
- 最终排序：`mean_entropy desc` → `max_entropy desc` → `cell_count desc`
- 同一区域内热点中心距离 `< 0.5°` 时去重
- 总预算：默认 `20`，按 region bbox 面积用 Hamilton / largest-remainder 分配，并保证每区至少 `1`

## Outputs

- JSON: `results/phase3.7_hotspots/phase3_7_hotspots_2016.json`
- Hotspot CSV: `results/phase3.7_hotspots/phase3_7_hotspots_2016.csv`
- Region CSV: `results/phase3.7_hotspots/phase3_7_hotspot_regions_2016.csv`
- Debug PNG: `results/phase3.7_hotspots/debug/<region_id>.png`
- Coarse cache: `results/cache/phase3_7/phase3_7_global_plot_cache_global_500m_2016_sample8.nc`

## Verification

- `ruff check src/WA/phase37_hotspots.py scripts/find_phase3_7_hotspots.py tests/test_phase3_7_hotspots.py`
- `python -m pytest tests/test_phase3_7_hotspots.py -q`

## HPC Command

`python scripts/find_phase3_7_hotspots.py --input-dir results/phase3.6 --output-dir results/phase3.7_hotspots --cache-dir results/cache/phase3_7 --regions-file config/priority_regions.yaml --year 2016 --total-hotspot-budget 20 --threshold-percentile 95 --min-cluster-cells 16 --aoi-size-deg 0.5 --min-distance-deg 0.5 --candidate-sample-step 8`
