# Phase 3.7 S2 Downloads

**Date:** 2026-04-01
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** 已为 Phase 3.7 hotspot manifest 接上 Sentinel-2 下载链路；旧 Phase 3 fine-grained probe 下载入口仍保持可用。

---

## Key Changes

| File | Change |
|------|--------|
| `src/WA/s2_batch.py` | 新增通用 manifest 驱动的 `download_s2_for_manifests(...)`，支持显式传入一个或多个 hotspot manifest；旧 `download_phase3_s2_batch(...)` 改为薄封装 |
| `src/WA/s2_batch.py` | 新增 `download_phase37_s2_batch(...)` 与 Phase 3.7 默认常量，默认 manifest 为 `results/phase3.7_hotspots/phase3_7_hotspots_2016.json`，默认时间为 `2016-07-01`，默认结果根目录为 `results/phase3.7_s2` |
| `src/WA/s2_batch.py` | 新增 Phase 3.7 artifact manifest 命名：`phase3_7_s2_artifacts_<year>_<yyyymmdd>.json`，避免不同时间下载互相覆盖 |
| `scripts/run_phase3_7_s2_downloads.py` | 新增 Phase 3.7 专用 CLI，支持 `--hotspots-manifest`、`--results-root`、`--target-time`、`--allow-interactive-auth`、`--no-skip` |
| `tests/test_s2_batch.py` | 新增回归测试，覆盖 Phase 3.7 manifest 解析、通用 batch API、Phase 3.7 artifact manifest 命名、旧 Phase 3 兼容、CLI 默认参数与 `--no-skip` |

## Outputs

- S2 quicklook / chip：
  - `results/phase3.7_s2/fine_truth/<region_slug>/<window_slug>/<hotspot_id>_s2_rgb.jpg`
  - `results/phase3.7_s2/fine_truth/<region_slug>/<window_slug>/<hotspot_id>_s2_chip.tif`
- Artifact manifest：
  - `results/phase3.7_hotspots/phase3_7_s2_artifacts_2016_20160701.json`

## Verification

- `ruff check src/WA/s2_batch.py scripts/run_phase3_7_s2_downloads.py tests/test_s2_batch.py`
- `python -m pytest tests/test_s2_batch.py tests/test_validation/test_s2_reference.py -q`

## HPC Command

默认下载：

`python scripts/run_phase3_7_s2_downloads.py --hotspots-manifest results/phase3.7_hotspots/phase3_7_hotspots_2016.json --results-root results/phase3.7_s2 --target-time 2016-07-01`

强制重下：

`python scripts/run_phase3_7_s2_downloads.py --hotspots-manifest results/phase3.7_hotspots/phase3_7_hotspots_2016.json --results-root results/phase3.7_s2 --target-time 2016-07-01 --no-skip`
