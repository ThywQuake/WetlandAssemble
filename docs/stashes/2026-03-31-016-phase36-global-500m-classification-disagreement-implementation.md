# Phase 3.6 全球 500m 分类分歧实现总结

**Date:** 2026-03-31
**Branch:** `refactor/loader-reference-grid-alignment`
**Commit Range:** `unknown`
**Status:** Phase 3.6 核心工作流已落地：严格以三数据集共同有效格点为域，生成全球 500m 分类分歧熵、majority class、agreement count 与三套主导类别输出。

---

## Key Changes

| File | Change |
|------|--------|
| `src/WA/comparison/phase36.py` | 新增/修复 Phase 3.6 主流程：统一 8 类聚合、strict joint-valid 掩膜、主导类判定、基于 3 票的归一化 Shannon entropy、分条带 NetCDF 写出、流式 summary 统计 |
| `src/WA/classification.py` | 复用 YAML 驱动的 `class_to_unified_id`、`source_class_ids_by_unified_id`、优先级顺序与统一类别名称，作为 Phase 3.6 的唯一映射来源 |
| `scripts/run_phase3_6_global_entropy.py` | 新增 Phase 3.6 CLI 入口，支持 `--standardized-dir`、`--output-dir`、`--year`、`--bbox`、`--lat-chunk-size`、`--dry-run` |
| `src/WA/comparison/__init__.py` | 导出 Phase 3.6 相关 API |
| `tests/test_phase3_6_analysis.py` | 覆盖 YAML 映射聚合、GWD30 年内时间平均、joint-valid 严格限制、priority tie-break、vote entropy 三种情形、文件写出与 dry-run |

## Architecture Decisions

1. **比较域严格受限于三者交集**：只有 `g2017`、`glwd_v2`、`gwd30` 都 valid 的格点才参与 entropy / majority / agreement 计算。
2. **统一类别体系只来自 `config/classification_mappings.yaml`**：不回退旧的硬编码 4 类/8 类映射。
3. **主指标是跨数据集主导类别分歧**：对三个数据集的 dominant class 做投票熵，归一化分母固定为 `log2(3)`，而不是 `log2(8)`。
4. **GWD30 采用目标年份内时间平均口径**：从标准化 `frac_*` 变量聚合到统一类别后，按年内时间维做平均，再参与 dominant class 判定。
5. **输出按纬向条带流式写出**：避免一次性把全球 500m 结果全部常驻内存。

## Verification

- `python -m pytest tests/test_phase3_6_analysis.py -q` → `12 passed`
- `python -m pytest tests/` → `349 passed`
- `ruff check src/WA/classification.py src/WA/comparison/phase36.py scripts/run_phase3_6_global_entropy.py tests/test_phase3_6_analysis.py` → `clean`
- `ruff check`（全仓）→ **失败，但为既有无关问题**；当前报错主要位于：
  - `scripts/hpc_probe_trends.py`
  - `scripts/merge_gwd30_regions.py`
  - `scripts/plot_coarse_scale.py`
  - `scripts/plot_global.py`
  - `scripts/plot_global_v2.py`
  - `scripts/stack_topmodel.py`
  - `scripts/stack_topmodel_simple.py`
  - `src/WA/modis_batch.py`
  - `src/WA/utils/tree_reduce.py`
  - `src/WA/visualization/coarse_scale.py`

## Open Risks / TODOs

- 目前 Phase 3.6 假设输入为已标准化的 500m `frac_*` 产品；若后续标准化变量命名变化，需要同步更新聚合逻辑。
- `majority_class` / `agreement_count` / `*_dominant_class` 在 NetCDF 中保留整型 sentinel；下游读取时应直接使用 joint-valid mask，而不是把 sentinel 当真实类别。
- 目前 summary 输出的是全局面积加权均值与近似分位数；若后续需要 hotspot/区域面板，可在此产物基础上继续做 Phase 3.6 可视化扩展。

## Rollback Notes

- 若需回退本阶段实现，优先回滚：`src/WA/comparison/phase36.py`、`scripts/run_phase3_6_global_entropy.py`、`src/WA/comparison/__init__.py`、`tests/test_phase3_6_analysis.py`。
- Phase 3.6 未改动 `config/classification_mappings.yaml`，因此映射配置不涉及本次回滚。

## Next Steps

1. 在真实标准化产物目录上运行 `scripts/run_phase3_6_global_entropy.py` 生成全球结果。
2. 基于输出的 `phase3_6_entropy_*.nc` 和 `phase3_6_unified_classes_*.nc` 再做区域分歧热点可视化。
3. 如需仓库全局 `ruff clean`，应单独处理本 stash 中列出的既有无关问题，避免与 Phase 3.6 混改。
