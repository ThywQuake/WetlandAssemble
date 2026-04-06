# Phase 3.6 GWD30 tile-loader 修复

**Date:** 2026-03-31
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** 已修复 Phase 3.6 在 HPC 上错误地通过 `StandardizedDataLoader` 读取 `gwd30_2016.nc` 的问题；现在改为始终使用 GWD30 原生 tile-backed `load_time_fraction_grid(...)` 路径。

---

## HPC 报错分析

### 1. Code Bug

Phase 3.6 的 `load_phase36_inputs()` 原来写成：

- `g2017` → `StandardizedDataLoader`
- `glwd_v2` → `StandardizedDataLoader`
- `gwd30` → `StandardizedDataLoader`

这与项目后续对 GWD30 的架构决策不一致。

用户在 HPC 上的报错：

- `FileNotFoundError: No standardized files were found for gwd30`

根因不是数据缺失本身，而是 **Phase 3.6 忘了 GWD30 已经切换到 tile-backed on-demand 策略**。

### 2. Runtime / Config Issues

- 当前 HPC 配置本身没有问题。
- `config/datasets.yaml` 中 `gwd30` 已明确配置为 `loader_type: gwd30`，并指向原始 TIFF 目录。
- 真正的问题是 Phase 3.6 没有走这个 loader，而是误走了 standardized annual netCDF 路径。

### 3. Operational Improvements

- 后续凡是需要 GWD30 参与 500m 对齐分析，都应先确认是否使用 `reference_grid` 驱动的 tile-backed 路径。
- 不应再假设一定存在 `gwd30_YYYY.nc`。

## 本次修复

| File | Change |
|------|--------|
| `src/WA/comparison/phase36.py` | `load_phase36_inputs()` 改为：先加载 `g2017` / `glwd_v2` 标准化产品，再用 `g2017` 网格构造 reference grid，并调用 GWD30 原生 tile loader |
| `src/WA/comparison/phase36.py` | 新增 `_build_phase36_reference_grid()`、`_phase36_reference_grid_bbox()`、`_load_phase36_gwd30()` |
| `tests/test_phase3_6_analysis.py` | 新增 `test_load_phase36_inputs_uses_special_gwd30_loader()`，并把集成测试改成 mock GWD30 tile loader 口径 |

## 当前行为

Phase 3.6 现在的输入路径是：

- `g2017` → 标准化 `g2017.nc`
- `glwd_v2` → 标准化 `glwd_v2.nc`
- `gwd30` → 原生 `GWD30Loader.load_time_fraction_grid(...)`

也就是说：

- `GWD30` 不再依赖 `gwd30_2016.nc`
- 只要原始 GWD30 tiles 在 HPC 上存在，就能跑

## Verification

- `ruff check src/WA/comparison/phase36.py tests/test_phase3_6_analysis.py scripts/run_phase3_6_global_entropy.py` → clean
- `python -m pytest tests/test_phase3_6_analysis.py -q` → `14 passed`
- `python -m pytest tests/ -q` → `351 passed`

## HPC 重跑命令

```bash
cd ~/Wetland_Assemble/WA

python scripts/run_phase3_6_global_entropy.py \
  --standardized-dir ~/Wetland_Assemble/data/standardized \
  --output-dir results/phase3.6 \
  --cache-dir results/cache/phase3_6 \
  --year 2016 \
  --lat-chunk-size 512
```
