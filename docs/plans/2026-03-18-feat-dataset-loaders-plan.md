---
title: "feat: Dataset Loaders for 8 Wetland Geospatial Datasets"
type: feat
status: active
date: 2026-03-18
---

# Dataset Loaders for 8 Wetland Geospatial Datasets

## Overview

Build a modular, config-driven loader framework for 8 wetland geospatial datasets stored on PKU HPC cluster. Each loader reads raw data (NetCDF/GeoTIFF), handles format-specific complexity, and converts to a common xarray-based format for downstream cross-dataset comparison and analysis.

This is Phase 1 of the Wetland Assemble (WA) project — the foundation for all subsequent analysis work.

## Problem Statement / Motivation

The project needs to compare and evaluate 8 wetland datasets across tropical/subtropical regions. These datasets vary dramatically in:
- **Format**: NetCDF (5 datasets), GeoTIFF (3 datasets)
- **Temporal resolution**: static, monthly, daily, annual, 4-day interval
- **Spatial resolution**: 30m to 25km
- **CRS**: EPSG:4326, UTM zones, EASE grid
- **Variable semantics**: binary masks, fractions, multi-class integers

Without a unified loading layer, every analysis script would need to re-implement format parsing, flag handling, CRS alignment, and temporal reconstruction — leading to fragile, duplicated code.

## Proposed Solution

### Architecture: Abstract Base Class + Registry Pattern

```
src/WA/
  __init__.py
  config.py                # YAML config loader
  loaders/
    __init__.py            # Re-exports get_loader()
    base.py                # DatasetLoader ABC
    registry.py            # loader_type -> class mapping
    berkeley.py            # Berkeley-RWAWC (multi-file monthly NetCDF)
    netcdf_generic.py      # GIEMS-MC, WAD2M (single-file NetCDF)
    swamps.py              # SWAMPS (nested daily NetCDF, sensor shift)
    topmodel.py            # TOPMODEL (ensemble NetCDF)
    g2017.py               # G2017 (static multi-file GeoTIFF)
    glwd.py                # GLWD v2 (multi-class GeoTIFF)
    gwd30.py               # GWD30 (18k+ tiled GeoTIFF mosaic)
```

### Base Class Contract

```python
# src/WA/loaders/base.py
from abc import ABC, abstractmethod
import xarray as xr
from dataclasses import dataclass

@dataclass
class DatasetMetadata:
    name: str
    temporal_range: tuple[str, str] | None
    spatial_extent: tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat
    resolution: str
    crs: str
    is_static: bool
    has_classification: bool

class DatasetLoader(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.name = config["name"]

    @abstractmethod
    def load(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        time_range: tuple[str, str] | None = None,
    ) -> xr.Dataset:
        """Load data lazily (dask-backed). Subset by bbox/time_range."""
        ...

    @abstractmethod
    def metadata(self) -> DatasetMetadata:
        """Return dataset metadata without loading data."""
        ...
```

### Config-Driven Instantiation

```python
# Usage
from WA.config import load_config
from WA.loaders import get_loader

config = load_config("config/datasets.yaml")
loader = get_loader(config["datasets"]["berkeley_rwawc"])
ds = loader.load(bbox=(-73, -5, -44, 5), time_range=("2019-01", "2020-12"))
```

### Registry Pattern

```python
# src/WA/loaders/registry.py
LOADER_REGISTRY: dict[str, type[DatasetLoader]] = {}

def register_loader(name: str):
    def decorator(cls):
        LOADER_REGISTRY[name] = cls
        return cls
    return decorator

def get_loader(dataset_config: dict) -> DatasetLoader:
    loader_type = dataset_config["loader_type"]
    if loader_type not in LOADER_REGISTRY:
        raise ValueError(f"Unknown loader_type: {loader_type}")
    return LOADER_REGISTRY[loader_type](dataset_config)
```

## Technical Considerations

### Per-Dataset Loader Complexity

| Dataset | Loader | Key Challenge | Complexity |
|---------|--------|---------------|-----------|
| Berkeley-RWAWC | `berkeley.py` | Time coord is placeholder (-2147483647); must parse from filename | Medium |
| GIEMS-MC | `netcdf_generic.py` | Flag values (-999/-998/-997) must be masked to NaN | Low |
| WAD2M | `netcdf_generic.py` | Variable named `Fw` (capital F); single file | Low |
| SWAMPS | `swamps.py` | Sensor shift at year 2000 changes filename pattern; EASE grid; thousands of files | High |
| TOPMODEL | `topmodel.py` | Ensemble: 6 configs x 7 forcings; time coord is month index (1-12) not datetime | High |
| G2017 | `g2017.py` | 3 separate TIF files; tropical-only coverage | Low |
| GLWD v2 | `glwd.py` | 34 classes; 3 subdirectories; scale factor 0.1 for ha data | Medium |
| GWD30 | `gwd30.py` | 18,000+ UTM tiles/year; mosaic via `gdalbuildvrt`; 92 bands (4-day interval) | Very High |

### Lazy Loading Strategy

- **Always lazy (dask-backed)**: GWD30, SWAMPS, Berkeley-RWAWC (multi-file or very large)
- **Lazy by default, small enough to `.compute()`**: GIEMS-MC (3GB), WAD2M (2GB), TOPMODEL (~50MB/file)
- **Eager is fine**: G2017 (3 files), GLWD v2 (static classification)

### Key Implementation Notes

**Berkeley-RWAWC**: Use `xr.open_mfdataset()` with `preprocess` to parse YYYY-MM from filename and override the broken time coordinate.

**SWAMPS**: Pre-2000 files are `SWAMPS.FW.F11.ERS.YYYYMMDD.nc` (bi-monthly); post-2000 are `SWAMPS.FW.F13.QUIKSCAT.YYYYMMDD.nc` (daily). Loader must handle both patterns using `sensor_shift_year` from config.

**TOPMODEL**: Config YAML says 4 configs but HPC folder listing shows 6. Loader should discover configs dynamically from directory structure rather than hardcoding.

**GWD30**: Use `gdalbuildvrt` to create virtual mosaic. Only load tiles intersecting the requested `bbox`. Each tile has 92 bands representing 4-day intervals within a year.

**Generic NetCDF**: GIEMS-MC and WAD2M share `loader_type: "netcdf"` in config. The generic loader should handle per-dataset variable mapping and flag masking via config fields.

### Dependencies (for `pyproject.toml`)

```toml
dependencies = [
    "xarray>=2024.9",
    "netCDF4>=1.7",
    "rasterio>=1.4",
    "rioxarray>=0.17",
    "dask[distributed]>=2024.8",
    "pyproj>=3.7",
    "numpy>=2.0",
    "pandas>=2.2",
    "pyyaml>=6",
]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.6", "mypy>=1.11"]
```

### Testing Strategy

All tests use synthetic fixtures (tiny NetCDF/GeoTIFF files mimicking real structure). No real data locally.

```
tests/
  conftest.py                # Shared fixtures
  test_config.py             # YAML loading
  test_loaders/
    conftest.py              # Per-dataset synthetic fixtures
    test_base.py             # ABC contract validation
    test_berkeley.py         # Time parsing from filename
    test_netcdf_generic.py   # Flag masking, variable renaming
    test_swamps.py           # Sensor shift, dual filename patterns
    test_topmodel.py         # Ensemble discovery, time reconstruction
    test_g2017.py            # Multi-file GeoTIFF
    test_glwd.py             # Scale factor, class loading
    test_gwd30.py            # VRT construction, UTM handling
```

HPC integration tests use `@pytest.mark.hpc` marker, run only on cluster.

## System-Wide Impact

- **Interaction graph**: `config.py` reads YAML -> `registry.py` resolves loader class -> loader reads files via xarray/rasterio -> returns `xr.Dataset`. No callbacks or middleware.
- **Error propagation**: `FileNotFoundError` when HPC paths unavailable locally (expected). Loaders should raise `ValueError` for malformed data. Missing files within expected ranges log warnings, insert NaN.
- **State lifecycle risks**: Loaders are stateless (read-only). No risk of orphaned state. Dask lazy arrays hold file handles open — callers should `.close()` or use context managers.
- **API surface parity**: The `get_loader()` factory is the single entry point. All loaders share the same `load(bbox, time_range)` interface.

## Acceptance Criteria

- [ ] `src/WA/config.py`: loads and validates `config/datasets.yaml`
- [ ] `src/WA/loaders/base.py`: `DatasetLoader` ABC with `load()` and `metadata()` methods
- [ ] `src/WA/loaders/registry.py`: `get_loader()` resolves all 7 loader types
- [ ] `src/WA/loaders/berkeley.py`: loads multi-file Berkeley-RWAWC, parses time from filename
- [ ] `src/WA/loaders/netcdf_generic.py`: loads GIEMS-MC (with flag masking) and WAD2M
- [ ] `src/WA/loaders/swamps.py`: handles sensor shift at year 2000, both filename patterns
- [ ] `src/WA/loaders/topmodel.py`: discovers ensemble configs dynamically, reconstructs datetime from month index
- [ ] `src/WA/loaders/g2017.py`: loads 3 GeoTIFF files with rioxarray
- [ ] `src/WA/loaders/glwd.py`: loads multi-class GeoTIFFs, applies scale factor 0.1
- [ ] `src/WA/loaders/gwd30.py`: builds VRT mosaic, supports bbox subsetting
- [ ] All loaders return `xr.Dataset` with CRS metadata attached
- [ ] All loaders support `bbox` and `time_range` parameters for subsetting
- [ ] `pytest` passes with 100% of loader tests using synthetic fixtures
- [ ] `ruff` and `mypy` pass
- [ ] Dependencies declared in `pyproject.toml`

## Scientific Decisions (Resolved)

### 1. Wetland Definition: Vegetated Wetland (Exclude Open Water)

Binary comparison uses **vegetated wetland** definition — open water bodies (lakes, rivers, reservoirs) are excluded. This aligns with WAD2M's approach.

**Berkeley-RWAWC** is a watermask (binary water/non-water) that includes all water bodies. It does **NOT participate in wetland classification comparison or metrics calculation**. It serves as background/auxiliary reference data only.

**Artificial wetlands** (rice paddies, aquaculture ponds) are **marked separately as `artificial_wetland`** — not counted as natural wetland, but information is preserved for optional inclusion.

#### G2017 Class-to-Wetland Mapping

| Value | Description | Wetland Category |
|-------|-------------|-----------------|
| 0 | No Data | `nodata` |
| 10 | Open Water | `open_water` (excluded) |
| 20 | Mangrove | `wetland` |
| 30 | Swamps (Incl. bogs) | `wetland` |
| 40 | Fens | `wetland` |
| 50 | Riverine and Lacustrine | `wetland` |
| 60 | Floodplains (permanent) | `wetland` |
| 70 | Floodplains (seasonal) | `wetland` |
| 80 | Marshes (general) | `wetland` |
| 90 | Marshes (arid) | `wetland` |
| 100 | Marshes (wet meadows) | `wetland` |

#### GLWD v2 Class-to-Wetland Mapping

| ID | Class Name | Wetland Category |
|----|------------|-----------------|
| 00 | Dryland | `non_wetland` |
| 01 | Freshwater lake | `open_water` (excluded) |
| 02 | Saline lake | `open_water` (excluded) |
| 03 | Reservoir | `open_water` (excluded) |
| 04 | Large river | `open_water` (excluded) |
| 05 | Large estuarine river | `open_water` (excluded) |
| 06 | Other permanent waterbody | `open_water` (excluded) |
| 07 | Small streams | `open_water` (excluded) |
| 08-15 | Lacustrine/Riverine wetlands | `wetland` |
| 16-19 | Palustrine wetlands | `wetland` |
| 20-21 | Ephemeral wetlands | `wetland` |
| 22-27 | Peatlands | `wetland` |
| 28 | Mangrove | `wetland` |
| 29 | Saltmarsh | `wetland` |
| 30 | Large river delta | `wetland` |
| 31 | Other coastal wetland | `wetland` |
| 32 | Salt pan, saline/brackish wetland | `wetland` |
| 33 | Rice paddies | `artificial_wetland` (separate) |

#### GWD30 Class-to-Wetland Mapping

| Value | Class | Wetland Category |
|-------|-------|-----------------|
| 0 | Non-wetland | `non_wetland` |
| 1 | River | `open_water` (excluded) |
| 2 | Canal/Channel | `open_water` (excluded) |
| 3 | Lake | `open_water` (excluded) |
| 4 | Reservoir/Pond | `open_water` (excluded) |
| 5 | Estuary Water | `open_water` (excluded) |
| 6 | Lagoon | `open_water` (excluded) |
| 7 | Aquaculture Pond / Salt Pan | `artificial_wetland` (separate) |
| 8 | Inland Marsh | `wetland` |
| 9 | Inland Swamp | `wetland` |
| 10 | Floodplain | `wetland` |
| 11 | Coastal Marsh | `wetland` |
| 12 | Coastal Swamp | `wetland` |
| 13 | Tidal Flat | `wetland` |
| 14 | Shallow Marine Water | `open_water` (excluded) |

### 2. Resampling Method: Area-Weighted Fraction

For classification datasets (G2017, GLWD v2, GWD30) downsampled to 0.25° grid:
- Count wetland pixels within each 0.25° cell, output as **fraction 0-1**
- This preserves area information and is the standard approach in geospatial wetland studies
- For fraction datasets (SWAMPS, WAD2M, TOPMODEL): bilinear interpolation

### 3. Temporal Aggregation: Both Mean and Max

When aggregating daily/4-day data to monthly:
- Output **two variables**: `wetland_fraction_mean` (monthly average) and `wetland_fraction_max` (monthly maximum)
- Mean reflects average state (standard for climate research)
- Max reflects peak wetland extent (relevant for methane modeling)
- Analysis stage selects which variable to use per comparison

### 4. GWD30 Band-to-Date Mapping (Resolved)

92 bands at 4-day interval starting from January 1st:
- Band 1 = Jan 1 (day 1)
- Band N = day (N-1)*4 + 1
- Band 92 = day 365 (Dec 31 for non-leap years; covers Dec 30-31 for leap years)
- Each band represents a 4-day composite window

### 5. TOPMODEL Configuration (Resolved)

HPC directory confirms **6 configs x 7 forcings = 42 combinations** (not 28 as originally documented):

**Configs:** G2017_max, GIEMS-2_max, GIEMS-2_yrmax, RFW_max, WAD2M_max, WAD2M_yrmax

**Forcings:** ERA5, ERA5-Land, GLDAS-Noahv2.0, GLDAS-Noahv2.1, MERRA-2, MERRA-Land, NCEP-DOE

Note: Time ranges differ per forcing (GLDAS-Noahv2.1 starts at 2000, others at 1980-1981). Loader discovers combinations dynamically from directory structure.

### 6. SWAMPS Sensor Shift: Continuous Time Series

Pre-2000 (SSM/I + ERS, bi-monthly) and post-2000 (SSM/I + QuikSCAT, daily) are loaded as a **single continuous time series**. The sensor shift year (2000) is recorded in dataset metadata attributes. Bias correction is deferred to the analysis stage.

### 7. Open Water Policy: Excluded by Vegetated Wetland Definition

Resolved by Decision #1. All datasets use the vegetated wetland definition:
- Datasets that already exclude water (WAD2M): no action needed
- Classification datasets (G2017, GLWD v2, GWD30): class mapping tables above define exclusions
- Berkeley-RWAWC: does not participate in comparison (auxiliary only)
- GIEMS-MC, SWAMPS, TOPMODEL: represent inundation/wetland fraction, inherently exclude permanent open water in their algorithms

## Success Metrics

- All 8 documented datasets can be loaded from HPC without manual intervention
- Loader initialization from config takes < 1 second
- Spatial subsetting to tropical_subtropical region works for all datasets
- Synthetic test suite runs in < 30 seconds locally

## Dependencies & Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| GWD30 mosaic of 18k+ tiles is extremely slow | High | Use `gdalbuildvrt` + bbox tile filtering; cache VRT files |
| Real data may differ from documentation | Medium | HPC integration tests with `@pytest.mark.hpc`; validate against data profiles in `docs/datasets/` |
| LSTM Wetland has no documentation | Low (skipped) | Deferred to future phase; requires `ncdump -h` on HPC |
| Generic "netcdf" loader may not handle all edge cases | Medium | Make it configurable via YAML fields (variable mapping, flag values) |
| TOPMODEL config/forcing matrix may be larger than documented | Low | Discover dynamically from directory structure |
| Python 3.13 compatibility with geospatial stack | Medium | Test early; pin versions that support 3.13 |

## Sources & References

### Internal References
- Project objectives: `docs/aim.md`
- Dataset configurations: `config/datasets.yaml`
- Per-dataset documentation: `docs/datasets/*.md`
- HPC sync mechanism: `.claude/skills/sync-hpc/`

### External References
- xarray I/O: https://docs.xarray.dev/en/stable/user-guide/io.html
- rioxarray CRS management: https://corteva.github.io/rioxarray/latest/getting_started/crs_management.html
- GDAL VRT format: https://gdal.org/en/stable/drivers/raster/vrt.html
- Dask best practices: https://docs.dask.org/en/latest/array-best-practices.html

---

# 数据集加载器计划（中文版）

## 概述

为存储在北大 HPC 集群上的 8 个湿地地理空间数据集构建模块化、配置驱动的加载框架。每个加载器读取原始数据（NetCDF/GeoTIFF），处理格式特定的复杂性，并转换为基于 xarray 的通用格式，供下游跨数据集比较和分析使用。

这是 Wetland Assemble (WA) 项目的第一阶段——所有后续分析工作的基础。

## 问题与动机

项目需要比较和评估热带/亚热带地区的 8 个湿地数据集。这些数据集在格式（NetCDF/GeoTIFF）、时间分辨率（静态到日频）、空间分辨率（30m 到 25km）、坐标参考系（EPSG:4326/UTM/EASE）和变量语义（二值掩膜/分数/多类别整数）方面差异极大。

没有统一的加载层，每个分析脚本都需要重新实现格式解析、标志处理、CRS对齐和时间重建——导致脆弱且重复的代码。

## 技术方案

### 架构：抽象基类 + 注册表模式

- **基类** `DatasetLoader`：定义 `load(bbox, time_range)` 和 `metadata()` 接口
- **注册表**：将 `config/datasets.yaml` 中的 `loader_type` 字符串映射到具体加载器类
- **工厂函数** `get_loader()`：根据配置实例化正确的加载器

### 各数据集加载器

| 数据集 | 加载器文件 | 关键挑战 | 复杂度 |
|--------|-----------|---------|--------|
| Berkeley-RWAWC | `berkeley.py` | 时间坐标是占位符，需从文件名解析 | 中 |
| GIEMS-MC | `netcdf_generic.py` | 标志值(-999/-998/-997)需掩膜为NaN | 低 |
| WAD2M | `netcdf_generic.py` | 变量名 `Fw`（大写F）；单文件 | 低 |
| SWAMPS | `swamps.py` | 2000年传感器切换改变文件名模式；EASE网格 | 高 |
| TOPMODEL | `topmodel.py` | 集合：6配置x7强迫；时间坐标是月份索引 | 高 |
| G2017 | `g2017.py` | 3个独立TIF文件；仅热带覆盖 | 低 |
| GLWD v2 | `glwd.py` | 34类；3个子目录；公顷数据比例因子0.1 | 中 |
| GWD30 | `gwd30.py` | 每年18000+个UTM瓦片；需gdalbuildvrt拼接 | 极高 |

### 科学决策（已确定）

1. **湿地定义**：采用"植被湿地"定义，排除开放水体（湖泊、河流、水库）。稻田和养殖塘单独标记为 `artificial_wetland`。Berkeley-RWAWC 不参与湿地分类比较，仅作背景辅助数据。详细分类映射表见英文版。
2. **重采样方法**：分类数据使用面积加权分数（统计 0.25° 网格内湿地像元占比，输出 0-1）；分数数据使用双线性插值。
3. **时间聚合**：同时保留月均值（`wetland_fraction_mean`）和月最大值（`wetland_fraction_max`），分析时按需选择。
4. **GWD30 波段映射**：从 1 月 1 日起每 4 天一个波段，92 个波段覆盖全年。Band N = day (N-1)*4 + 1。
5. **TOPMODEL 配置**：确认为 6 个校准配置 x 7 个强迫数据 = 42 种组合。加载器从目录结构动态发现。
6. **SWAMPS 传感器切换**：作为连续时间序列加载，在元数据中记录传感器切换年份（2000年）。偏差校正留给分析阶段。
7. **开放水体**：由决策 #1 统一——所有数据集使用植被湿地定义排除开放水体。

## 验收标准

- [ ] 所有 8 个文档化数据集可从 HPC 加载，无需手动干预
- [ ] 所有加载器返回带 CRS 元数据的 `xr.Dataset`
- [ ] 所有加载器支持 `bbox` 和 `time_range` 参数
- [ ] pytest 合成数据测试 100% 通过
- [ ] ruff 和 mypy 通过
- [ ] 依赖声明在 `pyproject.toml` 中
