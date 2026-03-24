# Phase 3.5 分类可视化面板实现

**Date:** 2026-03-23
**Branch:** feat/phase3-fine-grained-entropy-s2
**Status:** Phase 3.5 完成，2×3 分类面板模块已实现并合并

---

## Key Changes

| File | Change |
|------|--------|
| `src/WA/visualization/panel.py` | 新增：2×3 分类面板绘图模块（投票分类、原生分类加载、class-fraction 聚合） |
| `scripts/plot_phase3_panels.py` | 新增：CLI 脚本，批量生成 hotspot 面板 PNG |
| `tests/test_visualization/test_panel.py` | 新增：10 个测试（colormap / mapping / vote / plot） |
| `docs/plans/2026-03-23-feat-phase35-classification-visualization-plan.md` | 新增：Phase 3.5 计划文档 |
| `pyproject.toml` | 添加 matplotlib>=3.9 依赖 + mypy 忽略 |

## 实现要点

- **布局**：固定 2×3 网格
  - 上排：S2 RGB | Shannon 熵（白→红）| 投票分类
  - 下排：GLWD (~1km) | G2017 (0.05°) | GWD30 (500m)
- **投票逻辑**：在 ~500m 网格聚合三数据集的 4class fractions，逐类求和后 argmax
- **样式**：仅左列标纬度、仅底行标经度、右侧统一熵 colorbar、底部分类 legend patches
- **Worktree 流程**：创建 `feat/phase35-comparison-visualization` 分支 → 实现 → merge 到主分支

## Verification

- pytest: 125/125 passed（新增 10 个可视化测试）
- ruff: clean
- HPC: 未测试（本地实现）

## Open Risks / TODOs

- S2 quicklook 发现逻辑依赖 `results/fine_truth/{region}/{window}/*_s2_rgb.jpg` 路径
- GWD30 at 500m 对 1° bbox 需处理 ~4000×4000 原生像元（内存可控 ~64MB per class）
- 分类颜色为建议值，可能需根据出版需求调整

## Next Steps

1. 在 HPC 上运行 `plot_phase3_panels.py` 批量生成 Phase 3 hotspot 面板
2. 或继续 Phase 4：趋势分析（Mann-Kendall + Sen's slope）
