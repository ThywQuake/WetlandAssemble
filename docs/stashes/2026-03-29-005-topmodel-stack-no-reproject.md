# 2026-03-29 TOPMODEL Stacking (无重投影)

## 设计决策

**TOPMODEL 不需要预先重采样到 500m**：
- 原生分辨率 0.25° ≈ 500m（差异可忽略）
- 用时 nearest 重投影即可
- 只需 stack 分散的 config/forcing/year 文件

## TOPMODEL 数据结构

```
TOPMODEL/
├── G2017_max/
│   ├── ERA5/
│   │   ├── fwet_G2017_max_ERA5_reso025_1980.nc
│   │   ├── fwet_G2017_max_ERA5_reso025_1981.nc
│   │   └── ... (1980-2020)
│   ├── ERA5-Land/
│   ├── GLDAS-Noahv2.0/
│   ├── GLDAS-Noahv2.1/  (2000-2020)
│   ├── MERRA-2/
│   ├── MERRA-Land/
│   └── NCEP-DOE/
├── GIEMS-2_max/
├── GIEMS-2_yrmax/
├── RFW_max/
├── WAD2M_max/
└── WAD2M_yrmax/
```

**总计**: 6 configs × 7 forcings × ~40 years ≈ 1,680 个文件

## 新增文件

### 1. `scripts/stack_topmodel.py`

Stack TOPMODEL 文件，保留原生 0.25° 网格：

```python
# 输出：topmodel_{year}.nc
# 维度：(config: N, forcing: M, time: 12, lat, lon)
# 网格：原生 0.25°，无重投影
```

**使用方式**：
```bash
# 本地测试
python scripts/stack_topmodel.py --output-dir output/standardized --years 2016

# HPC 全量
python scripts/stack_topmodel.py --output-dir output/standardized --skip-existing
```

### 2. `scripts/submit_stack_topmodel.sh`

HPC SLURM 提交脚本：

```bash
# 按年份拆分提交（默认）
bash scripts/submit_stack_topmodel.sh

# 仅提交特定年份
bash scripts/submit_stack_topmodel.sh --years 2016,2017

# 不拆分年份（单作业）
bash scripts/submit_stack_topmodel.sh --no-split-years

# Dry run
bash scripts/submit_stack_topmodel.sh --dry-run

# 自定义资源
bash scripts/submit_stack_topmodel.sh --time 180 --cpus 8
```

**默认配置**：
- 时间：120 分钟（2 小时）
- CPU: 4
- 分区：high

## 输出规格

```
output/standardized/topmodel_2016.nc
output/standardized/topmodel_2017.nc
...
```

**每个文件**：
- 维度：`(config: N, forcing: M, time: 12, lat: ~720, lon: ~1440)`
- 变量：`wetland_fraction`
- 网格：原生 0.25°（未重投影）
- 编码：netCDF4, zlib (complevel=4, shuffle)

## 与 Phase 2.6 集成

`StandardizedDataLoader` 已自动支持 TOPMODEL：

```python
from WA.standardized_loader import StandardizedDataLoader

loader = StandardizedDataLoader("output/standardized")

# 加载 TOPMODEL 某年
topmodel_2016 = loader.load("topmodel", year=2016)

# 在 harmonize 中使用
from WA.comparison.harmonize import harmonize_standardized_datasets

harmonized = harmonize_standardized_datasets(
    standardized_dir="output/standardized",
    bbox=(100, 10, 110, 20),
)
# topmodel 会自动被包含（如果文件存在）
```

## 后续处理

在 analysis 阶段，如需要与其他 500m 数据比较：

```python
from rasterio.enums import Resampling
from WA.loaders._shared import reproject_dataset_to_grid

# 临时 nearest 重投影到 500m 网格
topmodel_aligned = reproject_dataset_to_grid(
    topmodel_dataset,
    reference_grid_500m,
    resampling=Resampling.nearest,  # 不用 bilinear
)
```

## 文件对比

| 脚本 | 用途 | 重投影 |
|------|------|--------|
| `submit_standardize_topmodel.sh` | 完整标准化（含重投影） | bilinear |
| `submit_stack_topmodel.sh` | 仅 stack（无重投影） | 无 |

**推荐使用** `submit_stack_topmodel.sh`（更轻量，按需重投影）。
