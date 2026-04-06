---
title: "Phase 1.5: 数据集标准化 — WGS84 500m netCDF"
type: feat
status: active
date: 2026-03-27
---

# Phase 1.5: 数据集标准化 — WGS84 500m netCDF

## Overview

8 个湿地数据集原生 CRS/分辨率/格式各异（30m GeoTIFF ~ 25km NetCDF），后续 Phase 2-5 的比较、趋势分析都需要在同一空间网格上进行。Phase 1.5 一次性把所有数据集投影到统一的 **WGS84 500m 网格**并存为**压缩 netCDF**，后续直接读取即可比较。

## Problem Statement / Motivation

当前每次比较都临时调用 `loader.load(reference_grid=...)` + `reproject_match()`，存在以下问题：
1. **重复计算**：每个 Phase / 每个脚本都要重新加载+投影，GWD30 30m 尤其慢
2. **不一致风险**：不同脚本构建的 `reference_grid` 分辨率不同（0.25°、500m、1km），结果不可直接比较
3. **下游复杂度**：Phase 3/4/5 的分析脚本都需要处理原生 → 统一网格的逻辑
4. **数据交换困难**：原始格式各异（GeoTIFF/NetCDF/多文件/单文件），无法用统一工具打开

## Proposed Solution

新建 `src/WA/standardize.py` 核心模块 + `scripts/standardize_datasets.py` HPC 脚本，一次性将所有数据集标准化为统一格式。

---

## 全局规格

| 参数 | 值 |
|------|-----|
| CRS | EPSG:4326 (WGS84) |
| 分辨率 | 500m ≈ 0.004491° (`500 / 111320`) |
| BBox | [-180, -35, 180, 35] |
| 时间范围 | **所有数据集保存全部可用年份** |
| 时间分辨率 | 保持原生 |
| 输出组织 | **每年一个文件**（静态数据集单文件） |
| 输出格式 | netCDF4, zlib 压缩 (complevel=4), chunked |
| 连续数据 | bilinear/average 后 **clip [0, 1]** |
| 分类数据 | **二值掩膜 + average → 各类占比百分比** |
| 占比变量命名 | `frac_{class_value}` |
| 非湿地类 (class 0) | **包含** |

---

## 各数据集标准化方案

### 1. G2017 — 静态分类 (~124m GeoTIFF)

- **原生分辨率**: ~0.00111° ≈ 124m (Data Profile: `Affine(0.0011139...)`)
- **变量**: `wetland` + `peatland`（丢弃 `wetland_nolake`）
- **方向**: 124m → 500m **降采样**
- **方法**: 对每个 class value C → 二值掩膜 `(data == C) → 1/0` → `Resampling.average` → 得到占比
- **wetland 类别** (11 个): 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100
  → 输出: `frac_0`, `frac_10`, `frac_20`, ..., `frac_100`
- **peatland 类别** (2 个): 0, 1
  → 输出: `peatland_frac_0`, `peatland_frac_1`
- **输出文件**: `g2017.nc` (无时间维)
- **输出维度**: `(lat: ~15586, lon: ~80089)` × 13 个变量

**注意**: 不能直接用 `loader.load(reference_grid=...)` — 现有 loader 用 nearest resampling，这里需要自定义的 binary-mask + average 流程。需在 `standardize.py` 中实现 `classification_to_fractions()` 函数。

---

### 2. GLWD v2 — 静态分类 (~464m GeoTIFF)

- **原生分辨率**: 15 arc-second ≈ 464m (Data Profile: `Affine(0.00416666...)`)
- **方向**: 464m → 500m，几乎无需重采样
- **方法**: 用 `area_by_class_ha` 变量 → bilinear 重采样到 500m → 归一化为百分比
  - 原因: WGS84 中不同纬度像元面积不同，用面积(ha)做 bilinear 后再归一化更严谨
- **类别** (34 个): 00-33
  → 输出: `frac_0`, `frac_1`, ..., `frac_33` (34 个变量)
- **输出文件**: `glwd_v2.nc` (无时间维)
- **输出维度**: `(lat: ~15586, lon: ~80089)` × 34 个变量

**注意**: GLWD loader 已提供 `area_by_class_ha(glwd_class, lat, lon)`。标准化时:
1. 对每个 class 的 ha 值做 bilinear 重采样到 500m 网格
2. 对每个像元，所有 class 的 ha 值求和 → total_ha
3. 每个 class 的 frac = ha / total_ha
4. nodata 区域（combined_classes == 255）→ 所有 frac 为 NaN

---

### 3. GWD30 — 时间序列分类 (30m GeoTIFF, 2013-2022)

- **原生分辨率**: 30m (UTM per tile)
- **方向**: 30m → 500m **降采样**（每个 500m 像元 ≈ 256 个源像元）
- **时间**: 4-day, 92 步/年, **保存全部 10 年**
- **方法**: 对每个时间步、每个 class → 二值掩膜 + `Resampling.average`
- **类别** (15 个): 0-14 (Non-wetland, River, Canal, Lake, ..., Shallow Marine Water)
  → 输出: `frac_0`, `frac_1`, ..., `frac_14` (15 个变量)
- **输出文件**: `gwd30_2013.nc`, `gwd30_2014.nc`, ..., `gwd30_2022.nc`
- **每个文件维度**: `(time: 92, lat: ~15586, lon: ~80089)` × 15 个变量

**注意**: 这是**计算量最大**的数据集。
- 不能直接用 `loader.load(reference_grid=...)` — 现有逻辑用 nearest/mode，这里需要 average
- 需要自定义 GWD30 标准化流程: 逐瓦片 → 对每个 band(时间步) → 对每个 class → binary mask → reproject(average) → 累积到目标网格
- 参考现有 `_load_to_reference_grid()` 和 `_reproject_tile_bands_to_grid()` 的逐瓦片架构
- tqdm 进度条必须覆盖所有循环
- 10 年 × 每年处理时间可能很长 → `--skip-existing` 支持断点续传

---

### 4. SWAMPS — 日分辨率连续 (25km NetCDF, 1992-2020)

- **原生分辨率**: 25km
- **方向**: 25km → 500m **上采样**
- **时间**: Daily, **保存全部 29 年**
- **方法**: `loader.load(bbox, time_range, reference_grid=grid_500m)` → bilinear → clip [0, 1]
- **输出变量**: `wetland_fraction`, `flag`
- **输出文件**: `swamps_1992.nc`, ..., `swamps_2020.nc`
- **每个文件维度**: `(time: ~365, lat: ~15586, lon: ~80089)` × 2 个变量

**注意**: 25km 上采样到 500m，每个源像元 → ~2500 个目标像元（相同值），zlib 压缩极其高效。

---

### 5. TOPMODEL — 月分辨率连续模拟 (0.25° NetCDF)

- **原生分辨率**: 0.25°
- **方向**: 0.25° → 500m **上采样**
- **时间**: Monthly, **保存全部发现的年份**
- **额外维度**: `config`, `forcing` — **全部保留**
- **方法**: `loader.load(bbox, time_range, reference_grid=grid_500m)` → bilinear → clip [0, 1]
- **输出变量**: `wetland_fraction(config, forcing, time, lat, lon)`
- **输出文件**: `topmodel_{year}.nc`
- **每个文件维度**: `(config: N, forcing: M, time: 12, lat: ~15586, lon: ~80089)`

---

### 6. WAD2M — 月分辨率连续 (0.25° NetCDF, 2000-2020)

- **原生分辨率**: 0.25°
- **方向**: 0.25° → 500m **上采样**
- **时间**: Monthly, **保存全部 21 年**
- **方法**: `loader.load(bbox, time_range, reference_grid=grid_500m)` → bilinear → clip [0, 1]
- **输出变量**: `wetland_fraction`
- **输出文件**: `wad2m_2000.nc`, ..., `wad2m_2020.nc`
- **每个文件维度**: `(time: 12, lat: ~15586, lon: ~80089)`

---

### 7. GIEMS-MC — 月分辨率连续 (0.25° NetCDF, 1993-2007)

- **原生分辨率**: 0.25°
- **方向**: 0.25° → 500m **上采样**
- **时间**: Monthly, **保存全部 15 年**
- **方法**: `loader.load(bbox, time_range, reference_grid=grid_500m)` → bilinear → clip [0, 1]
- **输出变量**: `wetland_fraction`
- **输出文件**: `giems_mc_1993.nc`, ..., `giems_mc_2007.nc`
- **每个文件维度**: `(time: 12, lat: ~15586, lon: ~80089)`

---

### 8. Berkeley-RWAWC — 月分辨率连续 (30m NetCDF, 2018-2025)

- **原生分辨率**: 30m
- **方向**: 30m → 500m **降采样**
- **时间**: Monthly, **保存全部年份 (2018-2025)**
- **方法**: `Resampling.average`（降采样为百分比）→ clip [0, 1]
- **输出变量**: `watermask`
- **输出文件**: `berkeley_rwawc_2018.nc`, ..., `berkeley_rwawc_2025.nc`
- **每个文件维度**: `(time: 12, lat: ~15586, lon: ~80089)`

**注意**: Berkeley 是连续数据但 30m 降采样，用 `average` 而非 `bilinear` 更准确地反映面积比例。

---

## 分类 vs 连续数据集处理总结

| 数据集 | 类型 | 原生分辨率 | 方向 | 方法 | 特殊逻辑 |
|--------|------|-----------|------|------|----------|
| G2017 | 分类 | ~124m | 降采样 | binary mask + average | 自定义 |
| GLWD v2 | 分类 | ~464m | 近似 1:1 | ha bilinear + 归一化 | 自定义 |
| GWD30 | 分类 | 30m | 降采样 | binary mask + average per timestep | 自定义 (逐瓦片) |
| SWAMPS | 连续 | 25km | 上采样 | bilinear + clip | 用 loader.load() |
| TOPMODEL | 连续 | 0.25° | 上采样 | bilinear + clip | 用 loader.load() |
| WAD2M | 连续 | 0.25° | 上采样 | bilinear + clip | 用 loader.load() |
| GIEMS-MC | 连续 | 0.25° | 上采样 | bilinear + clip | 用 loader.load() |
| Berkeley | 连续 | 30m | 降采样 | average + clip | 需改 resampling |

---

## 输出目录结构

```
output/standardized/
├── metadata.json
├── g2017.nc                     # 静态, 13 frac 变量
├── glwd_v2.nc                   # 静态, 34 frac 变量
├── gwd30_2013.nc                # 92 steps × 15 frac 变量
├── gwd30_2014.nc
├── ...
├── gwd30_2022.nc
├── swamps_1992.nc               # 365 steps × 2 变量
├── ...
├── swamps_2020.nc
├── topmodel_{year}.nc           # 12 steps × config × forcing
├── wad2m_2000.nc                # 12 steps × 1 变量
├── ...
├── wad2m_2020.nc
├── giems_mc_1993.nc             # 12 steps × 1 变量
├── ...
├── giems_mc_2007.nc
├── berkeley_rwawc_2018.nc       # 12 steps × 1 变量
├── ...
└── berkeley_rwawc_2025.nc
```

---

## Technical Approach

### Architecture

```
src/WA/
├── standardize.py              # 核心标准化逻辑
├── loaders/                    # 现有 loader 基础设施（不修改）
│   ├── base.py                 # DatasetLoader ABC
│   ├── _shared.py              # reproject_to_grid / reproject_dataset_to_grid
│   ├── g2017.py / glwd.py / ...
│   └── registry.py

scripts/
├── standardize_datasets.py     # HPC CLI 入口

tests/
├── test_standardize.py         # 单元测试
```

### 新增文件

#### 1. `src/WA/standardize.py`

**核心函数：**

```python
def build_reference_grid(bbox, resolution_m=500) -> xr.DataArray
    # 复用 create_comparison_grid(bbox, resolution_deg=resolution_m/111320)

def classification_to_fractions(
    data: xr.DataArray,
    reference_grid: xr.DataArray,
    class_values: list[int],
    prefix: str = "frac",
) -> xr.Dataset:
    """分类数据 → 各类占比百分比
    对每个 class value: binary mask → Resampling.average → frac variable
    """

def glwd_ha_to_fractions(
    ha_data: xr.DataArray,  # (glwd_class, lat, lon)
    reference_grid: xr.DataArray,
) -> xr.Dataset:
    """GLWD 特殊路径: ha bilinear → 归一化为百分比"""

def standardize_continuous(
    dataset: xr.Dataset,
    reference_grid: xr.DataArray,
    resampling: Resampling,
) -> xr.Dataset:
    """连续数据: reproject + clip [0, 1]"""

def standardize_dataset(loader, reference_grid, bbox, year, output_dir) -> list[Path]
    # 按年份循环, 每年一个文件

def standardize_all(config, dataset_ids, bbox, reference_grid, output_dir) -> dict
    # 遍历所有数据集 + 所有年份, 写 metadata.json
```

#### 2. `scripts/standardize_datasets.py`

```
python scripts/standardize_datasets.py \
    --resolution 500 \
    --bbox -180 -35 180 35 \
    --output-dir output/standardized/ \
    --datasets gwd30 swamps topmodel wad2m giems_mc g2017 glwd_v2 berkeley_rwawc \
    --skip-existing
```

CLI 参数:
- `--resolution` (default: 500m)
- `--bbox` (default: [-180, -35, 180, 35])
- `--output-dir` (default: `output/standardized/`)
- `--datasets` (默认全部 8 个，排除 LSTM)
- `--skip-existing` (跳过已存在的输出文件，支持断点续传)
- `--config` (datasets.yaml 路径)

注意: 不再有 `--year` 参数（所有年份自动处理）。

#### 3. `tests/test_standardize.py`

- `test_build_reference_grid` — 验证网格分辨率、CRS、维度
- `test_classification_to_fractions` — 小 mock 分类栅格 → 占比
- `test_glwd_ha_to_fractions` — ha → 归一化
- `test_continuous_clip` — bilinear 后 clip [0, 1]
- `test_standardize_dataset_per_year` — 每年文件输出

---

## 关键复用

| 现有代码 | 路径 | 用途 |
|---------|------|------|
| `create_comparison_grid()` | `src/WA/comparison/harmonize.py:118` | 构建 500m 参考网格 |
| `open_single_band_raster()` | `src/WA/loaders/_shared.py:75` | 读取 GeoTIFF |
| `open_multiband_raster()` | `src/WA/loaders/_shared.py:107` | 读取多波段 GeoTIFF |
| `reproject_to_grid()` | `src/WA/loaders/_shared.py:21` | DataArray 重投影 |
| `reproject_dataset_to_grid()` | `src/WA/loaders/_shared.py:48` | Dataset 重投影 |
| `loader.load(reference_grid=...)` | 各 loader | 连续数据集加载+对齐 |
| `_load_to_reference_grid()` | `src/WA/loaders/gwd30.py:618` | GWD30 逐瓦片架构参考 |
| `_reproject_tile_bands_to_grid()` | `src/WA/loaders/gwd30.py` | GWD30 瓦片重投影参考 |
| `get_loader()` / `AppConfig` | `src/WA/loaders/registry.py`, `src/WA/config.py` | loader 实例化 |

---

## 实施步骤

1. **Step 1**: `src/WA/standardize.py` — `build_reference_grid` + `classification_to_fractions` + `glwd_ha_to_fractions` + `standardize_continuous` + `standardize_dataset` + `standardize_all`
2. **Step 2**: `scripts/standardize_datasets.py` — CLI, 进度条, skip-existing, metadata.json
3. **Step 3**: `tests/test_standardize.py` — 单元测试
4. **Step 4**: 验证

## 验证

```bash
# 本地测试
python -m pytest tests/test_standardize.py -v

# HPC 快速验证（先跑小数据集）
python scripts/standardize_datasets.py --datasets topmodel --output-dir output/standardized/
python scripts/standardize_datasets.py --datasets g2017 --output-dir output/standardized/

# HPC 全量
python scripts/standardize_datasets.py --output-dir output/standardized/ --skip-existing

# 验证输出
python -c "import xarray as xr; print(xr.open_dataset('output/standardized/g2017.nc'))"
```

---

## System-Wide Impact

- **Interaction Graph**: `standardize_all()` → `get_loader()` → `loader.load(reference_grid=grid_500m)` / 自定义分类流程 → 返回对齐的 `xr.Dataset` → `to_netcdf()` 写盘。后续 Phase 2-5 可直接 `xr.open_dataset()` 读取。
- **Error Propagation**: 单个数据集失败 → 捕获 `Exception` → 记录到 metadata.json `status: "error"` → 继续处理其他数据集。
- **State Lifecycle**: 输出目录部分写入失败 → metadata.json 记录哪些成功/失败 → `--skip-existing` 支持断点续传。
- **API Surface**: 新增模块，不修改任何现有 API。

## Risk Analysis

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| GWD30 处理耗时过长（10年 × 92步 × 15类 × 数千瓦片） | 高 | 中 | `--skip-existing` 断点续传；`--datasets` 可单独跑 |
| 全域 500m 输出文件过大 | 中 | 低 | zlib 压缩 + 上采样数据压缩效率高 |
| 全域 reference_grid 内存占用 (~80k×16k) | 低 | 低 | 仅 float32 ≈ 5GB，HPC 充足 |

---

# 中文版摘要

## 概述

Phase 1.5 将 8 个原生格式各异的湿地数据集统一标准化为 WGS84 投影、500m 分辨率的压缩 netCDF 文件，存放于 `output/standardized/` 目录。**所有数据集保存全部可用年份**，每年一个文件（静态数据集单文件）。

## 核心设计决策

1. **分类数据**: 不用 nearest resampling，而是 **二值掩膜 + average → 各类占比百分比**
2. **GLWD**: 用 ha 面积变量 bilinear 重采样后归一化（考虑 WGS84 纬度像元面积差异）
3. **变量格式**: 每个类别单独一个 `frac_{class_value}` 变量（不用 class 维度）
4. **包含 class 0**（非湿地类）
5. **连续数据**: bilinear/average + clip [0, 1]
6. **Berkeley**: 用 `average`（降采样更准确反映面积比例）
7. **时间**: 所有数据集保存全部年份，不限于 2016

## 新增文件

1. `src/WA/standardize.py` — 核心模块
2. `scripts/standardize_datasets.py` — HPC CLI
3. `tests/test_standardize.py` — 单元测试

## 实施顺序

Step 1（核心模块）→ Step 2（CLI）→ Step 3（测试）→ Step 4（验证）
