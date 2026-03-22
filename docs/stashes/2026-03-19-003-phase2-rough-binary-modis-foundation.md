# Phase 2 Rough Binary + MODIS Foundation — 摘要

**日期:** 2026-03-19
**分支:** `feat/phase2-rough-binary-modis-truth`
**状态:** Phase 2 第一批代码完成并通过本地验证

## Architecture decisions

- Phase 2 先实现“可运行的最小闭环”：
  - 二值湿地 harmonization
  - 粗尺度 pairwise comparison
  - disagreement-based focus AOI selection
  - GEE MODIS reference 下载包装层
- `berkeley_rwawc` 不参与 rough binary wetland comparison；继续作为辅助 open-water context。
- G2017 粗尺度优先使用 `wetland_nolake`，避免把 open-water class 重新引回 vegetated wetland binary 结果。
- TOPMODEL 在比较前先对 `config` 和 `forcing` 维做均值折叠，得到一个 dataset-level wetland fraction surface。
- MODIS 下载层显式输出终态：
  - `downloaded`
  - `cached`
  - `unsupported_time_window`
  - `gee_auth_failed`
  - `empty_collection`
  - `download_failed`
  - `download_limit_exceeded`

## Modified files and key changes

- `src/WA/comparison/__init__.py`
  导出 Phase 2 comparison API。
- `src/WA/comparison/harmonize.py`
  新增二值化、月尺度聚合、共享网格重投影、comparison time slice 选择。
- `src/WA/comparison/rough_binary.py`
  新增 pairwise binary metrics、vote fraction、disagreement score。
- `src/WA/comparison/focus_areas.py`
  新增 rough AOI 分层选取与去重。
- `src/WA/validation/__init__.py`
  导出 validation API。
- `src/WA/validation/gee_client.py`
  新增 Earth Engine 懒加载、初始化、可选交互认证包装。
- `src/WA/validation/modis_reference.py`
  新增 MODIS 8-day window 解析、确定性输出路径、同步 quicklook/chip 下载。
- `tests/test_comparison/*`
  新增 harmonize / rough_binary / focus_areas 单元测试。
- `tests/test_validation/*`
  新增 fake GEE 驱动的 gee_client / modis_reference 测试与一条合成端到端流水线测试。
- `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md`
  勾选已完成的 Phase 2 条目。
- `todos/003-complete-p1-build-phase2-rough-binary-modis-truth.md`
  完成并归档本轮 todo。

## Verification status

- `uv run pytest -q`: pass (`39 passed, 1 warning`)
- `uv run ruff check .`: pass
- `uv run mypy src tests`: pass

已知 warning:
- `numpy.ndarray size changed, may indicate binary incompatibility`
  仍出现在 `tests/test_loaders/test_berkeley.py`，但不影响当前通过状态。

## Open risks, TODOs, rollback notes

- `rough_binary` 目前只完成了 Phase 2 需要的 binary workflow；`fine_grained.py`、`hotspots.py`、`trends.py`、`trend_agreement.py` 仍未开始。
- MODIS 下载当前是同步 small-chip 优先策略；更大的 AOI 只做了 `download_limit_exceeded` 终态识别，还没有真正的 `Export.image.*` fallback。
- `manifests.py` 和统一 manifest 持久化尚未实现，当前状态对象仍在内存里返回。
- Phase 3 开始前，需要决定：
  - fine-grained class harmonization 是否完全迁移前代 coarse/fine mapping
  - hotspot clustering 的最小面积和最小间距参数
  - 是否把 AOI selector 参数暴露成 CLI/notebook entrypoint
