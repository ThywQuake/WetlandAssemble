# Phase 2 Landsat 审查清单合并 — 摘要

**日期:** 2026-03-21  
**分支:** `feat/phase2-rough-binary-modis-truth`  
**状态:** 已新增 review manifest 生成器，把 rough AOI、run summary、pairwise metrics、Landsat artifact 合并成可审查清单

## Architecture decisions

- 在 rough comparison 与 Landsat 参考影像都已生成后，下一步不是继续下载，而是把这些结果整理成 reviewer 可直接使用的清单。
- 当前 `pairwise_metrics.csv` 是 run 级别，不是 AOI 级别，因此 review manifest 采用：
  - **AOI 级主行**
  - 附带 **run 级 metrics 摘要**
  - 并保留原始 `metrics_path` / `comparison_grids_path` / `participant_surfaces_path`
- 生成结果分两层：
  - 每个 run 一份：
    - `landsat_review_manifest.csv`
    - `landsat_review_manifest.json`
  - 整个 `phase2_root` 一份总表：
    - `landsat_review_manifest.csv`
    - `landsat_review_manifest.json`

## Modified files and key changes

- `src/WA/landsat_review_manifest.py`
  - 新增 `LandsatReviewRow`
  - 新增 rough focus area / Landsat artifact / run summary / metrics 汇总合并逻辑
  - 新增 per-run 与 batch review manifest 写出
- `scripts/build_phase2_landsat_review_manifest.py`
  - 新增 CLI wrapper
- `tests/test_landsat_review_manifest.py`
  - 新增 review manifest 回归测试

## Verification status

- `uv run ruff check src/WA/landsat_review_manifest.py scripts/build_phase2_landsat_review_manifest.py tests/test_landsat_review_manifest.py`: pass
- `uv run pytest tests/test_landsat_review_manifest.py -q`: pass (`1 passed`)

## Open risks, TODOs, rollback notes

- 当前 manifest 中的 metrics 仍是 run 级摘要（`mean_iou` / `max_iou` / `mean_f1_score` / `min_kappa`），不是 AOI 级配对结果。
- 如果后续 reviewer 需要“每个 AOI 对应哪一组 dataset pair 最值得看”，需要再引入 AOI 层的 disagreement patch 统计或 patch-level metrics 提取。
