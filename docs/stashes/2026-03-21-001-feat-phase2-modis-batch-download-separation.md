# Phase 2 MODIS 批量下载与处理解耦 — 摘要

**日期:** 2026-03-21  
**分支:** `feat/phase2-rough-binary-modis-truth`  
**状态:** 已新增独立的 Phase 2 MODIS 批量下载脚本，可从 `focus_areas.csv` 扫描并下载，不再把下载流程绑在 rough probe 内

## Architecture decisions

- 当前 Phase 2 的 `focus_areas` 来自 rough comparison 结果，因此**严格意义上的 “先下载 MODIS 再做 rough comparison”** 在现有 AOI 设计下并不成立。
- 但可以把流程**明确拆成两个独立阶段**：
  1. `scripts/run_phase2_rough_regions.py` 只负责粗尺度比较并产出 `focus_areas.csv`
  2. `scripts/run_phase2_modis_downloads.py` 独立读取这些 `focus_areas.csv`，批量下载 MODIS quicklook/chip
- 新下载脚本不会重新跑 rough comparison，也不会依赖 `run_rough_probe(... --download-modis)`。
- 为避免不同 priority region 下同名 `aoi_id` 冲突，下载阶段会把物化后的 AOI id 加前缀：
  - `{region_id}__{original_aoi_id}`

## Modified files and key changes

- `src/WA/modis_batch.py`
  - 新增 Phase 2 focus area 扫描
  - 新增 `focus_areas.csv` 解析与 `bbox` 反序列化
  - 新增批量 MODIS 下载主流程
  - 新增每个 run 的 `modis_artifacts.json`
  - 新增总表 `modis_download_manifest.json`
- `scripts/run_phase2_modis_downloads.py`
  - 新增 CLI wrapper
- `tests/test_modis_batch.py`
  - 新增 CSV 解析测试
  - 新增批量 manifest 写出测试

## Workflow after this change

- 阶段 A：先跑 rough results
  - 产出 `results/phase2/rough/*/*/focus_areas.csv`
- 阶段 B：单独跑 MODIS 下载
  - 读取上述 CSV
  - 下载结果写入 `results/rough_truth/` 与 `results/quicklooks/`
  - 同时在每个 run 目录写 `modis_artifacts.json`

## Verification status

- `uv run ruff check src/WA/modis_batch.py scripts/run_phase2_modis_downloads.py tests/test_modis_batch.py`: pass
- `uv run pytest tests/test_modis_batch.py -q`: pass (`2 passed`)

## Open risks, TODOs, rollback notes

- 这次完成的是“**处理和下载解耦**”，不是“固定 AOI catalog 的下载优先流水线”。
- 如果后续真的需要“下载先于 rough comparison”，需要新增：
  - 独立于 rough disagreement 的 AOI catalog
  - 或者固定 region grid / predefined sample windows
- 当前脚本默认读取 `results/phase2/rough/*/*/focus_areas.csv`；如果后续 Phase 2 输出路径变更，需要同步调整 `--phase2-root`。
