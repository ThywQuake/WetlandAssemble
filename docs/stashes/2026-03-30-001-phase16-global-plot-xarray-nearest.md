# Phase 1.6: 全球湿地分布图 - xarray 最近邻降采样

**Date:** 2026-03-30
**Branch:** refactor/loader-reference-grid-alignment
**Status:** 绘图脚本完成，待 HPC 验证

---

## Key Changes

| File | Change |
|------|--------|
| `scripts/plot_global.py` | 新增全球分布图脚本，使用 xarray `interp(method='nearest')` 降采样 |
| `docs/plans/2026-03-29-001-phase16-coarse-scale-wetland-percentage.md` | 更新计划文档 |
| `docs/stashes/2026-03-29-001-phase16-coarse-scale-viz.md` | 更新 stash 文档 |

## 核心功能

- **基准年份**: 2016 年（自动查找最近可用年份）
- **降采样**: xarray 最近邻插值，避免内存爆炸
- **湿地类定义修正**:
  - G2017: `frac_20` 到 `frac_100` + `peatland_frac_1`（排除 frac_0 非湿地，frac_10 水体）
  - GLWD v2: `frac_8` 到 `frac_33`（排除 0-7 非湿地/水体）
- **SWAMPS 特殊处理**: 直接使用原始 `fw` 变量，不做时间聚合
- **地图纵横比**: `set_aspect('equal')` 确保 1°经纬度=1:1
- **标签**: 全英文（避免 HPC 字体警告）

## 验证

- ruff: clean
- pytest: 295 passed（coarse_scale 模块）
- HPC: 待运行

## Open Risks / TODOs

- HPC 运行可能遇到内存问题（wad2m 120GB 文件）
- 降采样因子计算可能需要调整

## Next Steps

1. HPC 运行验证：`uv run python scripts/plot_global.py`
2. 检查输出图片质量
3. 如有 OOM，添加分块加载逻辑
