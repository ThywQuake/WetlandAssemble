---
title: "fix: Phase 1 Loader HPC Validation Findings"
type: fix
status: active
date: 2026-03-19
---

# Phase 1 Loader HPC 验证问题修复

## Overview

HPC probe 脚本 (`scripts/hpc_probe_loaders.py`) 在 job.10160611 中成功运行，8/8 数据集全部 `status=sampled`。但详细审查输出后，发现 3 个必须在进入 Phase 2 之前修复的数据质量问题和若干观察项。

前代项目 `/Users/mac/Code/Wetland_Assemble/src/` 的对照审查为每个问题提供了明确的修复方向。

## Problem Statement / Motivation

Phase 1 loader 在合成测试（synthetic fixtures）中全部通过，但真实 HPC 数据暴露了以下问题，如果不修复将直接影响 Phase 2 比较分析的正确性：

1. SWAMPS 的 `-9999` 填充值未被掩膜 → 下游分析会将 fill value 当作真实分数处理
2. GLWD `glwd_class` 坐标全部为 `2` → 34 个类别的 ID 完全错误，精细比较无法进行
3. G2017 三个 GeoTIFF 坐标不对齐 → merge 后产生近重复坐标和大量 NaN

## Proposed Solution

### Issue 1: SWAMPS fill value 未掩膜 [CRITICAL]

**Probe 证据:**

```
swamps → sample_summary → wetland_fraction:
  max: -9999.0
  mean: -9999.0
  min: -9999.0
  preview: [-9999.0, -9999.0, -9999.0, -9999.0, -9999.0]
```

**根因:** `src/WA/loaders/swamps.py:49` 使用 `xr.open_dataset(path)` 打开 NetCDF 文件，但 SWAMPS 的 NetCDF 文件中的 `fw` 变量使用 `-9999` 作为缺失值标记。xarray 的默认 `_FillValue` 解码未覆盖该值（文件可能使用非标准属性名，或 `_FillValue` 设置不一致）。

**前代项目对照:** 前代 `SWAMPSLoader` (`Wetland_Assemble/src/wetland_analysis/data/loaders/swamps.py`) 同样没有显式掩膜 -9999 — 它使用 `xr.open_mfdataset(files, combine='by_coords', chunks=...)` 并依赖 xarray 默认解码。这表明前代也可能存在同样的问题。当前 WA 项目的 `netcdf_generic.py` 对 GIEMS-MC 有显式掩膜（`mask_values: (-999, -998, -997)`），这是正确的防御性做法。

**修复方案:**

在 `swamps.py` 的 `load()` 方法中，rename 之后添加显式掩膜：

```python
# swamps.py — load() 内，rename 之后，concat 之前
import numpy as np

dataset["wetland_fraction"] = dataset["wetland_fraction"].where(
    dataset["wetland_fraction"] != -9999.0, np.nan
)
```

同时建议：在 HPC 上用 `ncdump -h` 确认 SWAMPS 的 `fw` 变量实际使用的 fill/missing 属性名称，以理解 xarray 为何未自动解码。

**测试更新:** `tests/test_loaders/test_swamps.py` 需要新增一个 fixture，其中 `fw` 包含 `-9999` 值，验证 load 后这些值变为 NaN，且合法值（0-1 范围）保留。

---

### Issue 2: GLWD glwd_class 坐标全部为 2 [HIGH]

**Probe 证据:**

```
glwd_v2 → dataset_summary → coords → glwd_class:
  preview: [2, 2, 2, 2, 2]
  shape: [34]
```

34 个类别的坐标值全部是 `2`，应该是 0-33。

**根因:** `src/WA/loaders/glwd.py:84` 调用 `parse_first_integer(path.stem)` 从文件名中提取类别 ID。`parse_first_integer` 使用正则 `r"(\d+)"` 提取**第一个**整数。

**前代项目确认了 HPC 真实文件名:**

前代 `GLWDLoader` (`Wetland_Assemble/src/wetland_analysis/data/loaders/glwd.py:70`) 使用**显式构造文件名**而非解析发现：

```python
# 前代 glwd.py:70 — 直接构造文件名
pattern = f"GLWD_v2_0_class_{cls_id:02d}_{'ha_x10' if category=='ha' else 'pct'}.tif"
```

这确认了 HPC 上的实际文件名格式为：
- `GLWD_v2_0_class_00_ha_x10.tif`
- `GLWD_v2_0_class_01_pct.tif`
- `GLWD_v2_0_class_33_pct.tif`
- 等等

因此 `parse_first_integer("GLWD_v2_0_class_00_ha_x10")` 返回 `2`（从 "v2"），而非真正的 class ID `00`。

**修复方案（已确定）：使用 `class_(\d+)` 正则提取**

既然前代代码确认了文件名格式，直接使用精确正则：

```python
# glwd.py — _stack_area_rasters() 内
import re

def _parse_glwd_class_id(stem: str) -> int:
    """Extract class ID from GLWD filename like 'GLWD_v2_0_class_00_ha_x10'."""
    match = re.search(r"class[_-]?(\d+)", stem, re.IGNORECASE)
    if match is None:
        raise ValueError(f"Cannot extract GLWD class ID from {stem!r}")
    return int(match.group(1))
```

替换 `glwd.py:84` 中的 `parse_first_integer(path.stem)` 为 `_parse_glwd_class_id(path.stem)`。

**测试更新:** `tests/test_loaders/test_glwd.py` 的 fixture 文件名应改为 `GLWD_v2_0_class_00_pct.tif`、`GLWD_v2_0_class_01_pct.tif` 格式，验证 class ID 正确提取为 0、1。

---

### Issue 3: G2017 坐标不对齐 [HIGH]

**Probe 证据:**

```
g2017 → dataset_summary → coords → lat:
  preview: [
    -4.999520737523561,
    -4.999520725402135,   ← 与上一行差 ~1.2e-8，近重复
    -4.998406744002409,
    -4.998406731880983,   ← 与上一行差 ~1.2e-8，近重复
    -4.997292750481257
  ]
  shape: [1798]

g2017 → sample_summary → variables:
  wetland: {non_null_count: 0, preview: [NaN, NaN, NaN, NaN]}
  wetland_nolake: {non_null_count: 0, preview: [NaN, NaN, NaN, NaN]}
  peatland: {non_null_count: 1, preview: [0.0, NaN, NaN, NaN]}
```

1°×1° bbox 按 0.05° 分辨率应该只有 ~20 个 lat 值，但实际产生了 1798 个。且 3 个变量中 2 个全部为 NaN。

**根因:** `src/WA/loaders/g2017.py:46` 使用 `xr.merge(rasters, join="outer", compat="override")` 合并三个 GeoTIFF。这三个文件分辨率不同或像元注册（pixel registration）有微小偏移：

- `TROP-SUBTROP_WetlandV3b_2016_CIFOR.tif` — 原始细分辨率
- `fwet05deg_nolake.tif` — 文件名暗示 0.05° 分辨率（比其他两个粗得多）
- `TROP-SUBTROP_PeatV21_2016_CIFOR.tif` — 原始细分辨率

`join="outer"` 取所有坐标的并集，不同网格的坐标不精确对齐，导致坐标维度膨胀、大量 NaN 和近重复坐标对。

**前代项目对照:** 前代 `GeoTIFFLoader` (`Wetland_Assemble/src/wetland_analysis/data/loaders/geotiff.py`) **只加载单个文件**（默认 `wetland`），从不在 loader 层面合并三个变量。跨变量对齐在下游由 `SpatioTemporalAligner` 通过 `reproject_match` 处理（`Wetland_Assemble/src/wetland_analysis/utils/alignment.py:94-114`）。

这说明当前 WA 的"loader 层合并三个变量"设计是新引入的，前代刻意避免了这种做法。前代的 `debug_g2017_data.py` 脚本也专门调查 G2017 NaN/空白问题，说明 G2017 的多分辨率特性是已知的棘手点。

**修复方案（推荐策略 A）：以 `wetland` 为参考网格，`reproject_match` 对齐其他文件**

保留 loader 层合并的设计，但修复坐标对齐问题：

```python
# g2017.py — load() 方法
from rasterio.enums import Resampling

def load(self, bbox=None, time_range=None):
    files = self.config.get("files", {})
    # 以 wetland 作为参考网格
    ref_raster = open_single_band_raster(self.base_path / str(files["wetland"]), bbox=bbox)
    rasters = [ref_raster.rename("wetland").to_dataset()]

    for variable_name in ("wetland_nolake", "peatland"):
        raster = open_single_band_raster(self.base_path / str(files[variable_name]), bbox=bbox)
        # 对齐到参考网格：classification 用 nearest，fraction 用 nearest
        aligned = raster.rio.reproject_match(ref_raster, resampling=Resampling.nearest)
        rasters.append(aligned.rename(variable_name).to_dataset())

    dataset = xr.merge(rasters, join="inner")  # inner join 因为已经对齐了
    return self.finalize_dataset(dataset, bbox=bbox, time_range=time_range)
```

关键变更：
1. `ref_raster` 作为坐标基准
2. 其他两个文件通过 `reproject_match` 对齐到 `ref_raster` 的网格
3. 改用 `join="inner"`（对齐后坐标一致，inner 更安全）
4. 使用 `Resampling.nearest` 因为 G2017 是分类数据

**测试更新:** `tests/test_loaders/test_g2017.py` 需要创建具有微小偏移的合成 GeoTIFF fixture，验证 merge 后坐标一致、无 NaN 填充。

---

## 前代项目额外发现（对 Phase 2 有价值）

### Classification Mappings 已在前代中实现

前代 `Wetland_Assemble/src/wetland_analysis/data/mappings.py` 包含成熟的分类映射字典：

- **Coarse (4 classes):** Non-wetland, Permanent Water, Forested Wetland, Non-forested Wetland
- **Fine (8 classes):** Non-wetland, Open Water, Mangrove, Peatland, Forested Swamp, Marsh, Floodplain, Coastal Wetland

覆盖 GWD30、GLWD、G2017 三个分类数据集。这些映射可以直接迁移到 WA Phase 2 的 `comparison/harmonize.py`。

### Alignment Architecture 参考

前代的 `SpatioTemporalAligner` 使用数据集特定策略：
- `HighResGWD30Strategy`: 处理 UTM + 15m MGRS 偏移，使用 `Resampling.mode`
- `EASEGridStrategy`: 处理 SWAMPS EASE-Grid (EPSG:6933)，使用 `Resampling.bilinear`
- `DefaultStrategy`: 通用 `reproject_match`，categorical 用 mode，continuous 用 bilinear

所有对齐在下游执行，loader 返回原始 CRS 数据。当前 WA 的 loader 已经做了 WGS84 重投影（`_shared.py` 中的 `reproject_to_wgs84=True`），这与前代设计不同但可以接受。

---

## 观察项（非阻塞，建议记录）

### Obs 1: TOPMODEL 在 1980 年只发现 5/7 个 forcing

```
forcing: ["ERA5", "GLDAS-Noahv2.0", "MERRA-2", "MERRA-Land", "NCEP-DOE"]
shape: [5]
matched_groups: 30  (= 6 configs × 5 forcings)
```

缺少 ERA5-Land 和 GLDAS-Noahv2.1。这是**预期行为**——这两个 forcing 的数据起始年份晚于 1980。probe 脚本自动选择了最早可用时间窗口（1980-01），自然无法发现这两个 forcing。

**建议:** 在后续 HPC 验证中，补充一次 2000 年以后的 probe，确认 7 个 forcing 全部可发现。

### Obs 2: GWD30 加载耗时 33 秒（2 tiles）

```
gwd30: elapsed_seconds: 33.016
  discovery: matched_tiles: 2
  discovery: 18448 candidate tile(s) scanned
```

小 bbox 只需要 2 个 tile，但发现阶段扫描了全部 18,448 个候选文件。加载阶段 2 个 UTM 30m tile → WGS84 重投影是主要耗时点。

**建议:** 这在当前阶段可接受，但进入 Phase 2 全域比较前需要考虑：
- tile 发现结果缓存持久化
- 对比较分析使用预计算的 VRT / COG 格式
- 限制首次比较范围到子区域

### Obs 3: Berkeley watermask 全零

```
watermask: {max: 0.0, mean: 0.0, min: 0.0}
```

2×2 tiny sample 在 Amazon probe 窗口中全部为 0（非水）。给定 Berkeley 是 30m 分辨率，且 probe 仅采样 2×2 像元，偶然落在非水区域是正常的。

**建议:** 不是 bug，但 HPC 验证时可以用 `--unsafe-full-spatial-scan` 或更大 bbox 验证非零数据存在。

### Obs 4: GIEMS-MC 时间坐标显示为 int64

```
time: {dtype: "datetime64[ns]", preview: [725846400000000000]}
```

preview 显示的是 nanosecond epoch 而非人可读时间戳。这是 probe 脚本的 JSON 序列化问题（`datetime64` 被序列化为 int），不是数据问题。

**建议:** probe 脚本的 `_summarize_coord` 在序列化 datetime64 时应该先转为 ISO string。

## Technical Considerations

### 修复优先级

| Issue | 严重程度 | 影响范围 | 修复复杂度 | 前代参考可用性 |
|-------|---------|---------|-----------|-------------|
| SWAMPS -9999 填充值 | CRITICAL | 所有使用 SWAMPS 的下游分析 | 低（添加一行掩膜） | 前代也未处理，需新增 |
| GLWD class ID 全为 2 | HIGH | Fine-grained 比较（Phase 3） | 低（前代确认了文件名格式） | 直接参考前代文件名模式 |
| G2017 坐标不对齐 | HIGH | G2017 所有变量的空间一致性 | 中（需 reproject_match） | 前代用单文件加载回避了问题 |

### 依赖关系

- Issue 1 (SWAMPS) 和 Issue 2 (GLWD) 可以独立并行修复，不依赖 HPC 确认
- Issue 3 (G2017) 可直接用 `reproject_match` 修复，无需额外 HPC 确认

### HPC 验证需求

修复后需要重新运行 probe 脚本验证：

```bash
python scripts/hpc_probe_loaders.py --dataset swamps
python scripts/hpc_probe_loaders.py --dataset glwd_v2
python scripts/hpc_probe_loaders.py --dataset g2017
```

验证标准：
- SWAMPS: `wetland_fraction` 值应在 [0, 1] 或 NaN
- GLWD: `glwd_class` preview 应显示递增的 0-33 范围整数
- G2017: `lat` shape 应合理（~20 for 1° bbox at 0.05°），且 `wetland` 变量应有非 NaN 值

## System-Wide Impact

- **SWAMPS fix:** 仅修改 `swamps.py`，不影响其他 loader。
- **GLWD fix:** 仅修改 `glwd.py`，新增 `_parse_glwd_class_id` 函数。`_shared.py` 中的 `parse_first_integer` 保留不变（其他 loader 可能仍在使用）。
- **G2017 fix:** 修改 `g2017.py`，引入 `reproject_match` + `Resampling.nearest`。rasterio 的 `Resampling` 需要新增 import。
- 所有修复不影响 `config/`（只读约束）。
- 所有修复需要更新对应的合成测试以覆盖真实场景。

## Acceptance Criteria

- [ ] `swamps.py`: `-9999` 值被掩膜为 NaN，`wetland_fraction` 值范围为 [0, 1] 或 NaN
- [ ] `glwd.py`: `glwd_class` 坐标正确反映实际类别 ID（0-33 范围），使用 `class_(\d+)` 正则
- [ ] `g2017.py`: 三个变量通过 `reproject_match` 对齐到 `wetland` 网格，坐标一致，无全 NaN 变量
- [ ] 所有现有测试继续通过
- [ ] 新增测试覆盖上述三个修复场景
- [ ] `uv run pytest -q` / `uv run ruff check .` / `uv run mypy src tests` 全部通过
- [ ] HPC probe 重新运行确认修复效果
- [ ] probe 脚本改进：datetime64 序列化为 ISO string

## 补充建议：Probe 脚本改进

基于本次审查，probe 脚本可以做以下增强（优先级低于数据修复）：

1. **datetime 序列化:** coord preview 中 datetime64 应转为 ISO 8601 字符串
2. **值域检查:** 对 fraction 类变量自动检查值域是否在 [0, 1]，超出范围时发出警告
3. **坐标唯一性检查:** 检测近重复坐标（`np.diff(coord) < eps`）
4. **类别坐标检查:** 对分类数据集检测坐标值是否唯一

## Sources & References

### 当前项目
- HPC probe 输出: `temp/job.10160611.out.txt`
- Probe 脚本: `scripts/hpc_probe_loaders.py`
- SWAMPS loader: `src/WA/loaders/swamps.py:49`
- GLWD loader: `src/WA/loaders/glwd.py:84`
- G2017 loader: `src/WA/loaders/g2017.py:46`
- 参考实现（显式掩膜）: `src/WA/loaders/netcdf_generic.py:70-73`
- 规范计划: `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md`

### 前代项目 (`/Users/mac/Code/Wetland_Assemble/`)
- SWAMPS loader: `src/wetland_analysis/data/loaders/swamps.py` — 同样未显式掩膜 -9999
- GLWD loader: `src/wetland_analysis/data/loaders/glwd.py:70` — 确认文件名格式 `GLWD_v2_0_class_{id:02d}_{category}.tif`
- GeoTIFF loader: `src/wetland_analysis/data/loaders/geotiff.py` — 只加载单个文件，不合并
- Alignment: `src/wetland_analysis/utils/alignment.py` — `SpatioTemporalAligner` 使用 `reproject_match`
- Geospatial: `src/wetland_analysis/utils/geospatial.py` — `align_to_reference()` / `create_reference_grid()`
- Mappings: `src/wetland_analysis/data/mappings.py` — 成熟的 coarse/fine 分类映射（对 Phase 2 有价值）
- G2017 debug: `scripts/debug_g2017_data.py` — 专门调查 G2017 NaN/空白问题

---

# 英文摘要 (English Summary)

HPC probe job.10160611 ran all 8 loaders successfully but revealed 3 data quality issues:

1. **SWAMPS -9999 fill values not masked** (CRITICAL) — downstream analysis would treat fill values as real fractions. Legacy loader also lacked masking. Fix: add explicit `.where(val != -9999, NaN)`.
2. **GLWD class coordinate all `2`** (HIGH) — `parse_first_integer` extracts version number "2" from filename prefix `GLWD_v2_0_...` instead of class ID. Legacy code confirmed filename format is `GLWD_v2_0_class_{id:02d}_{category}.tif`. Fix: use `class_(\d+)` regex.
3. **G2017 coordinate misalignment** (HIGH) — three GeoTIFFs with different resolutions/registrations merged via `join="outer"` produce 1798 near-duplicate lat values and mostly NaN data. Legacy code loads only one file at a time, avoiding the issue. Fix: use `reproject_match` to align to reference grid before merging.

All three must be fixed before Phase 2 comparison work begins.
