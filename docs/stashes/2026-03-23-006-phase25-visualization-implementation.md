# Phase 2.5 Visualization Implementation

**Date:** 2026-03-23
**Branch:** feat/phase3-fine-grained-entropy-s2
**Status:** Phase 2.5 visualization module完成并合并

---

## Key Changes

| File | Change |
|------|--------|
| `src/WA/visualization/comparison_panel.py` | 核心绘图模块：GridSpec 3列布局，卫星/熵/平均湿地 + 各数据集原生分辨率面板 |
| `scripts/plot_comparison_panels.py` | CLI 脚本：读取 Phase 2 rough probe 输出（focus_areas.csv + comparison_grids.nc） |
| `tests/test_visualization/test_comparison_panel.py` | 6 个单元测试（布局、colormap、标签生成） |
| `pyproject.toml` | 添加 matplotlib>=3.9 依赖（viz 和 dev） |

## Verification

- pytest: 121 passed, 1 warning
- ruff: clean
- HPC: 未运行（需先完成 Phase 2 rough probe）

## Implementation Details

**可视化规格：**
- 第一行：卫星影像 | Shannon 熵（白→红）| 平均湿地%（白→蓝）
- 后续行：各数据集湿地% at 原生分辨率（GWD30 降采样至 1km）
- 仅最左列显示纬度标签，仅最底行显示经度标签
- 右侧两个共享 colorbar（熵 + 湿地%）

**数据流：**
1. 扫描 `results/phase2/rough/{region}/{YYYYMM}/focus_areas.csv`
2. 从 `comparison_grids.nc` 加载预计算的 disagreement_score 和 wetland_vote_fraction
3. 各数据集通过 loader 以原生分辨率加载（bbox 裁剪）
4. 生成 PNG 面板图至 `results/figures/`

**修正历程：**
- 初版 CLI 错误对接 Phase 3 manifest（fine_grained_probe.json）
- 用户指出应对接 Phase 2 rough probe 输出
- 重写 CLI：`--phase2-root` 参数，自动发现 focus_areas.csv，直接读取 comparison_grids.nc

## Commits

- `22f8358` feat(viz): add Phase 2.5 comparison panel visualization module
- `f0d036c` fix(viz): rewrite CLI to read Phase 2 rough probe output, not Phase 3
- `85e2c6c` chore: update deps and config for Phase 2.5 visualization merge

## Next Steps

1. 在 HPC 上完成 Phase 2 rough probe（生成 focus_areas.csv + comparison_grids.nc）
2. 运行可视化：
   ```bash
   uv run python scripts/plot_comparison_panels.py \
       --phase2-root results/phase2/rough \
       --output-dir results/figures \
       --year 2016
   ```
3. Phase 3 fine-grained probe + S2 下载（已有代表性站点支持）
