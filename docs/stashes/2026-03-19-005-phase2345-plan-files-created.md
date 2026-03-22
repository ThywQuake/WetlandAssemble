# Stash: Phase 2-5 独立计划文件创建

**日期**: 2026-03-19
**分支**: feat/phase2-rough-binary-modis-truth

## 完成内容

在 master plan (`docs/plans/2026-03-19-002-feat-phase2345-comparison-trends-manifests-plan.md`) 基础上，为每个 Phase 创建了独立的细化计划文件：

### 计划文件

| 文件 | Phase | 核心内容 |
|------|-------|---------|
| `003-feat-phase2-rough-binary-completion-plan.md` | Phase 2 | HPC 端到端验证；Export/Manifest 推迟到 Phase 5 |
| `004-feat-phase3-fine-grained-entropy-s2-plan.md` | Phase 3 | 4-class/8-class concordance mapping、Shannon Entropy (K-class)、Sentinel-2 参考影像下载 |
| `005-feat-phase4-trend-analysis-plan.md` | Phase 4 | Mann-Kendall + Sen's Slope 逐像素趋势、跨数据集一致性 (trend_agreement)、区域汇总 |
| `006-feat-phase5-manifests-export-docs-plan.md` | Phase 5 | ManifestRow 持久化 (parquet/CSV)、GEE Export.image.toDrive 回退、协议文档 |

### 关键设计决策

1. **Phase 2** 核心代码已完成 (harmonize, rough_binary, focus_areas, gee_client, modis_reference)，仅剩 HPC 验证
2. **Phase 3** 引入 classification concordance maps (来自 legacy `mappings.py`)，Shannon Entropy 从 binary 扩展到 K-class
3. **Phase 4** 使用 `xr.apply_ufunc` 向量化 MK+Sen's slope，支持 pymannkendall 预白化 fallback 到 scipy
4. **Phase 5** Manifest 连接所有 AOI 下载作业到 metrics/geometry/time window/terminal status

### 依赖关系

Phase 2 → Phase 3 → Phase 4 → Phase 5 (线性依赖链)

## 当前状态

- Phase 1: ✅ 完成 + HPC 验证通过
- Phase 2: 🟡 代码完成，待 HPC 端到端验证
- Phase 3-5: 📋 计划完成，待实现

## 未提交变更

- 4 个 Phase 计划文件 (docs/plans/)
- Phase 1 loader 修复 (swamps, glwd, g2017) — 来自之前的对话
