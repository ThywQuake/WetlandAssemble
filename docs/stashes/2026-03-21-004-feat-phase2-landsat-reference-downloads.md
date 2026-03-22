# Phase 2 Landsat 参考影像下载 — 摘要

**日期:** 2026-03-21  
**分支:** `feat/phase2-rough-binary-modis-truth`  
**状态:** 已新增独立的 Landsat 粗尺度参考影像下载链，可直接基于 `focus_areas.csv` 批量生成 Landsat RGB quicklook / chip

## Architecture decisions

- 用户希望在 MODIS 之外试 Landsat 参考影像，因此本轮不去替换 MODIS，而是新增**并行的 Landsat 下载链**。
- Landsat 方案独立于 MODIS：
  - 独立 downloader：`landsat_reference.py`
  - 独立 batch：`landsat_batch.py`
  - 独立 CLI：`run_phase2_landsat_downloads.py`
  - 独立输出目录：
    - `results/rough_truth_landsat/`
    - `results/quicklooks_landsat/`
- 时序策略：
  - 默认目标月份前后两个月融合
  - 多传感器合并：
    - Landsat 5 TM
    - Landsat 7 ETM+
    - Landsat 8 OLI
    - Landsat 9 OLI-2
- 云掩膜策略：
  - 使用 `QA_PIXEL` 去除 fill / dilated cloud / cirrus / cloud / cloud shadow / snow
  - 使用 `QA_RADSAT == 0` 去除辐射饱和像元

## Modified files and key changes

- `src/WA/validation/landsat_reference.py`
  - 新增 Landsat Collection 2 Level 2 多传感器融合下载
  - 新增 QA cloud mask
  - 新增 RGB band harmonization
- `src/WA/landsat_batch.py`
  - 新增 Phase 2 focus area 批量 Landsat 下载
  - 新增 `landsat_artifacts.json`
  - 新增 `landsat_download_manifest.json`
- `scripts/run_phase2_landsat_downloads.py`
  - 新增 Landsat CLI wrapper
- `src/WA/validation/__init__.py`
  - 导出 Landsat reference 接口
- `tests/test_validation/test_landsat_reference.py`
  - 新增 Landsat fusion window / 下载测试
- `tests/test_landsat_batch.py`
  - 新增 Landsat batch manifest 测试

## Verification status

- `uv run ruff check src/WA/validation/landsat_reference.py src/WA/landsat_batch.py scripts/run_phase2_landsat_downloads.py tests/test_validation/test_landsat_reference.py tests/test_landsat_batch.py src/WA/validation/__init__.py`: pass
- `uv run pytest tests/test_validation/test_landsat_reference.py tests/test_landsat_batch.py -q`: pass (`3 passed`)

补充说明：
- 本地 Python 3.13 + `tqdm` 环境仍有已知 `resource_tracker` 噪音，但测试结果本身通过。

## Open risks, TODOs, rollback notes

- Landsat 对 tropical 区域的“完全无云”仍无法保证，只是相对 MODIS 提供另一套光学参考。
- Landsat 7 在 2003 之后存在 SLC-off 条带；当前方案未专门剔除，只依赖多景 median 减弱影响。
- 若后续要进一步稳态化，可增加：
  - current-year 优先 + cross-year fallback 填洞
  - 单独记录每个 artifact 的参与传感器与 scene_count
