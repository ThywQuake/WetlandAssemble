# Phase 1 Loader HPC 验证问题修复 — 实施摘要

**日期:** 2026-03-19
**分支:** `feat/phase1-loader-foundation`
**状态:** 代码修复完成，待 HPC 验证

## 修改文件

| 文件 | 变更 |
|------|------|
| `src/WA/loaders/swamps.py` | 添加 `-9999` → NaN 显式掩膜 |
| `src/WA/loaders/glwd.py` | 新增 `_parse_glwd_class_id()` 替代 `parse_first_integer`，用 `class_(\d+)` 正则 |
| `src/WA/loaders/g2017.py` | 以 `wetland` 为参考网格，`reproject_match` 对齐后 `join="inner"` 合并 |
| `tests/test_loaders/test_swamps.py` | 新增 `test_swamps_loader_masks_fill_values` |
| `tests/test_loaders/test_glwd.py` | 新增 `test_parse_glwd_class_id_extracts_correct_id`，fixture 文件名改为真实 GLWD 格式 |
| `tests/test_loaders/test_g2017.py` | 新增 `test_g2017_loader_aligns_mismatched_grids` |

## 关键决策

1. **SWAMPS:** 防御性掩膜 `-9999`，前代项目也未处理此问题
2. **GLWD:** 前代确认文件名为 `GLWD_v2_0_class_{id:02d}_{category}.tif`，精确正则替代通用 `parse_first_integer`
3. **G2017:** 前代只加载单文件回避了问题；WA 保留 loader 层合并设计但用 `reproject_match` 修复对齐

## 验证状态

- `pytest`: 28 passed
- `ruff`: all checks passed
- HPC probe: **待重新运行**

## 待办

1. sync 到 HPC 重新运行 `scripts/hpc_probe_loaders.py` 验证 swamps/glwd/g2017
2. probe 脚本改进（datetime 序列化、值域检查、坐标唯一性检查）— 优先级低
3. 进入 Phase 2（Rough Binary Comparison + MODIS Truth）

## 风险

- G2017 `reproject_match` 在大范围/高分辨率下可能较慢，Phase 2 全域比较时需关注
- SWAMPS 掩膜仅处理 `-9999`，若存在其他异常填充值需后续排查
