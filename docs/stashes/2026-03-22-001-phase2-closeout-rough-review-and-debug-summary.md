# Phase 2 收尾：粗尺度对比 + Landsat 审查表 + HPC 调试 — 摘要

**日期:** 2026-03-22  
**分支:** `feat/phase2-rough-binary-modis-truth`  
**状态:** Phase 2 rough comparison 与 Landsat review manifest / priority 已收尾；当前 `results/phase2/rough` 无 failed runs，可作为 Phase 2 交付基线

## Architecture decisions

- `GLWD v2` 的 `combined_classes` 目录并不只包含真正的 combined-class raster，还混有：
  - `GLWD_v2_0_area_ha_x10.tif`
  - `GLWD_v2_0_area_pct.tif`
  - `GLWD_v2_0_main_class_50pct.tif`
  - `GLWD_v2_0_main_class.tif`
- 因此 loader 不再允许按字典序或“任意 tif”猜测 combined raster；只允许：
  1. 优先 `main_class`
  2. 若目标 bbox 下 `main_class` 有效像元数为 0，则回退到 `main_class_50pct`
  3. 显式忽略 `area_ha` / `area_pct`
- `GLWD` loader 需要把调试证据直接写入 dataset attrs，以便 HPC 结果回传后无需重新猜：
  - `glwd_combined_raster`
  - `glwd_combined_valid_count`
  - `glwd_requested_bbox`
- `rough binary harmonization` 对 empty surface 的判定不能再只返回一个笼统错误；需要保留阶段语义：
  - `prepared_source`
  - `aligned_to_reference_grid`
  - `comparison_slice`
- `SWAMPS` / `TOPMODEL` / `WAD2M` / `GIEMS-MC` 在极小 AOI（如 Danau Sentarum）下经过 bbox 裁切后，可能只剩 `1x1` coarse source cell。此时直接用 `reproject_match()` 会把有效 source 对齐成全 `NaN`。
- 对 `1x1` 的 lat/lon source surface，不再走通用 `reproject_match()`；改为按 source cell center 与 comparison grid cell overlap 进行单点落格，并且只有在“足够接近”的 reference cell 上才允许最近邻回退，避免把远处 source 错误投影到 unrelated grid cell。
- `Phase 2` 的失败巡检不应靠手工 grep；新增独立脚本汇总：
  - run 状态
  - failed dataset 计数
  - source variable
  - 是否已进入 priority review

## Phase 2 具体完成内容

- 在统一 coarse comparison grid 上完成 **rough binary wetland comparison**：
  - 将可参与数据集统一到 `wetland / non_wetland` 语义
  - 生成 pairwise metrics、disagreement score、wetland vote fraction、participant count
  - 将每个 run 的核心产物落盘到 `results/phase2/rough/<region>/<YYYYMM>/`
- 建立并跑通 **priority region + dual-time workflow**：
  - 针对优先湿地区域批量运行 rough comparison
  - 覆盖 `2000-03` 与 `2019-07` 两个 Phase 2 基线时间窗口
  - 当前 `results/phase2/rough` 的 run 状态已全部收敛为 `completed_with_skips`
- 完成 **AOI 提取与审查入口构建**：
  - 从 disagreement surface 中提取 focus AOIs
  - 生成 `focus_areas.csv`
  - 让每个 rough run 都能直接进入 reviewer 工作流，而不是只停留在指标表
- 完成 **MODIS rough-truth 参考影像链路**：
  - 将 MODIS 下载从 rough probe 中解耦为独立批处理
  - 将 MODIS 参考影像升级为更严格 QA 去云 + 多时段融合 composite
  - 为粗尺度 AOI 提供可复查的 quicklook / chip 参考
- 完成 **并行的 Landsat rough-truth 参考影像链路**：
  - 新增独立的 Landsat RGB quicklook / chip 下载
  - 不替换 MODIS，而是作为并行的更细视觉参考
  - 为 reviewer 提供更适合人工判读的光学影像基线
- 完成 **review manifest + priority shortlist**：
  - 将 rough AOI、run summary、pairwise metrics、Landsat artifacts 合并为 `landsat_review_manifest`
  - 再基于默认规则（高 disagreement、足够 participant、影像可用）筛出 `landsat_review_priority`
  - 当前基线：
    - `results/phase2/rough/landsat_review_manifest.csv` 共 `38` 行
    - `results/phase2/rough/landsat_review_priority.csv` 共 `30` 行
- 完成 **HPC correctness hardening**，把会污染科学解释的关键问题修正到位：
  - `GWD30` 的 `tqdm` fallback 兼容问题
  - `GLWD v2` combined raster 误选问题
  - `1x1` coarse source 在超小 AOI 下被对齐成空的问题
  - empty-surface error 的阶段化诊断与 source-variable 保留


## Modified files and key changes

- `src/WA/loaders/glwd.py`
  - 新增 `_parse_glwd_class_id()`
  - 新增 `_combined_raster_priority()`
  - `combined_classes` 现在只从 `main_class` / `main_class_50pct` 族中选择
  - 选择结果与有效像元数写入 attrs：`glwd_combined_raster`、`glwd_combined_valid_count`
  - `area_by_class_ha` / `area_by_class_pct` 读取时也显式使用 bbox 裁切
- `src/WA/comparison/harmonize.py`
  - `EmptyBinarySurfaceError` 改为携带 `dataset_id`、`source_variable`、`stage`
  - `_ensure_non_empty_binary_surface()` 现在区分 `prepared_source` / `aligned_to_reference_grid` / `comparison_slice`
  - `create_comparison_grid()` 写入 `comparison_resolution_deg`
  - 新增 `1x1` source 的专门对齐路径，修复 Danau Sentarum 这类超小 bbox 下动态数据集 empty surface
- `src/WA/rough_probe.py`
  - `failed_empty_harmonized_surface` 现在保留真实 `comparison_source_variable`
  - 这样 HPC 回传的 `run_summary.json` 可以直接说明失败发生在哪个变量
- `scripts/inspect_phase2_rough_failures.py`
  - 新增 Phase 2 结果巡检 CLI
  - 汇总 failed/skipped datasets
  - 可标记哪些 run 已进入 priority review
  - 能从旧错误文本中回推 `source variable`
- `tests/test_loaders/test_glwd.py`
  - 新增 `main_class` / `main_class_50pct` / `area_*` 的选择回归测试
  - 覆盖 bbox 主图为空时回退到 `main_class_50pct`
  - 覆盖 combined 目录中混有 `area_ha` / `area_pct` 时必须忽略
- `tests/test_comparison/test_harmonize.py`
  - 新增 empty-surface 阶段断言
  - 新增 `1x1` fraction source 对齐测试
  - 覆盖 `1x1` reference grid 下 `TOPMODEL` 这类 monthly fraction surface 不再被对齐成空
- `tests/test_rough_probe.py`
  - 更新 empty-surface 诊断断言
  - 覆盖 fraction source 保留 `comparison_source_variable`
- `tests/test_inspect_phase2_rough_failures_script.py`
  - 新增巡检脚本测试

## Verification status

- 代码验证：
  - `uv run ruff check src/WA/loaders/glwd.py tests/test_loaders/test_glwd.py`: pass
  - `uv run pytest tests/test_loaders/test_glwd.py -q`: pass (`6 passed`)
  - `uv run ruff check src/WA/comparison/harmonize.py tests/test_comparison/test_harmonize.py tests/test_rough_probe.py`: pass
  - `uv run pytest tests/test_comparison/test_harmonize.py tests/test_rough_probe.py -q`: pass (`18 passed, 1 warning`)
  - `uv run ruff check scripts/inspect_phase2_rough_failures.py`: pass
  - `uv run pytest tests/test_inspect_phase2_rough_failures_script.py -q`: pass (`2 passed`)
- HPC / synced result verification：
  - `results/phase2_diag/glwd_only/mekong_delta/201907/run_summary.json`
    - `glwd_v2.status = participating`
    - `glwd_combined_raster = .../GLWD_v2_0_main_class.tif`
    - `harmonized_summary.non_null_count = 75`
  - `results/phase2_diag/glwd_only/ngiri_tumba_maindombe/201907/run_summary.json`
    - `glwd_v2.status = participating`
    - `glwd_combined_raster = .../GLWD_v2_0_main_class.tif`
    - `harmonized_summary.non_null_count = 360`
  - `results/phase2/rough/danau_sentarum/201907/run_summary.json`
    - `status = completed_with_skips`
    - `swamps` / `topmodel` / `wad2m` 从 empty surface 恢复为 `participating`
    - `metrics_row_count = 15`
  - `results/phase2/rough/danau_sentarum/200003/run_summary.json`
    - `status = completed_with_skips`
    - `giems_mc` / `swamps` / `topmodel` / `wad2m` 恢复为 `participating`
    - `metrics_row_count = 15`
  - `uv run python scripts/inspect_phase2_rough_failures.py --phase2-root results/phase2/rough`: pass
    - `dataset_failure_counts: none`
    - `failed_runs: none`
- 审查表验证：
  - `results/phase2/rough/landsat_review_manifest.csv`
    - `rows = 38`
    - 全部 `run_status = completed_with_skips`
  - `results/phase2/rough/landsat_review_priority.csv`
    - `rows = 30`
    - 全部 `run_status = completed_with_skips`
    - `mekong_delta` 已重新进入 priority list

## Open risks, TODOs, rollback notes

- `danau_sentarum` 虽然已恢复参与 rough comparison，但在 `landsat_review_manifest.csv` 中仍是：
  - `participant_count = 2`
  - `image_status` 为空
  因此不会进入当前默认 priority 规则；这属于审查策略问题，不再是 rough comparison 正确性问题。
- `mekong_flooded_forest_200003` 在 manifest 中 `mean_iou = 0.0`，说明虽然 run 已健康完成，但 dataset 间一致性极低；这是科学结果，不是当前工程 bug。
- `phase2_diag/glwd_only/batch_manifest.json` 只反映最后一次单次诊断运行；不应把它当作完整诊断历史索引。
- `Phase 3` 仍未开始。当前建议直接把 `results/phase2/rough` 与最新 `landsat_review_manifest.csv` / `landsat_review_priority.csv` 视为 Phase 2 收尾基线，然后进入：
  - `docs/plans/2026-03-19-004-feat-phase3-fine-grained-entropy-s2-plan.md`
