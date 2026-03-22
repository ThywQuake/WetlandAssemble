# Rough Probe HPC Result Integrity Fix — 摘要

**日期:** 2026-03-19
**分支:** `feat/phase2-rough-binary-modis-truth`
**状态:** correctness/reporting 修复完成，待 HPC 复跑验证

## Architecture decisions

- `select_comparison_slice()` 保留 month-start target month 语义，但新增
  month-aware fallback，兼容像 WAD2M 这类月中时间坐标。
- comparison 层新增 `EmptyBinarySurfaceError`，用于显式拒绝“loader 成功但
  harmonized surface 全空”的情况。
- `GLWDLoader` 不再盲目取 combined_classes 目录里的第一个 tif；在给定 bbox
  时，改为选择有效像元最多的候选文件。
- `rough_probe` 的总体状态语义修正为：
  - `completed`
  - `completed_with_skips`
  - `completed_with_failures`
  - `failed`
- 对 `valid_cell_count == 0` 的 pairwise rows 增加 warning 摘要，避免静默退化。

## Modified files and key changes

- `src/WA/comparison/harmonize.py`
  - 新增 month-aware comparison slice fallback
  - 新增 `comparison_source_time`
  - 新增 `EmptyBinarySurfaceError`
  - GLWD binary mapping 后的空 surface 显式失败
- `src/WA/comparison/__init__.py`
  导出 `EmptyBinarySurfaceError`
- `src/WA/loaders/glwd.py`
  - combined raster 改为 bbox-aware 选择
  - 显式掩膜 `255` nodata
- `src/WA/rough_probe.py`
  - 增强 overall status 逻辑
  - 新增 warning summary
  - 对 empty harmonized surface 给出显式失败状态
- `tests/test_comparison/test_harmonize.py`
  新增 WAD2M-style month-aware slice 测试和 GLWD 空 surface 测试
- `tests/test_loaders/test_glwd.py`
  新增 GLWD valid combined raster 选择测试
- `tests/test_rough_probe.py`
  新增 `completed_with_failures` 状态语义测试
- `todos/005-complete-p1-fix-rough-probe-hpc-result-integrity.md`
  完成本轮 todo

## Verification status

- `uv run pytest -q`: pass (`47 passed, 1 warning`)
- `uv run ruff check .`: pass
- `uv run mypy src tests`: pass

已知 warning:
- `numpy.ndarray size changed, may indicate binary incompatibility`
  仍来自现有 Berkeley loader 测试，与本轮修复无直接关系。

## Open risks, TODOs, rollback notes

- 还没有复跑 HPC 上的 `temp/job.03` 等真实 rough probe，因此以下点需要实际复验：
  - `wad2m` 是否已从 failed 变为 participating
  - `glwd_v2` 是否已产生非空 harmonized surface
  - `overall_status` 是否从裸 `completed` 变为更准确状态
- `GWD30` 的 2016 年超慢 fallback 还未处理；该项仍在后续性能硬化范围内。
- 如果 GLWD 目录中存在多个都带有效值的 combined raster，当前“valid pixel count 最大”
  策略虽然稳健，但仍建议在 HPC 上记录真实文件名并进一步确认数据语义。
