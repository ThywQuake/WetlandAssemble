---
title: "Phase 1.6: 粗尺度湿地百分比分布可视化"
type: feat
status: completed
date: 2026-03-29
---

# Phase 1.6: 粗尺度湿地百分比分布可视化

## Overview

在 GWD30 缺位的情况下，规划并实现**所有数据集在全尺度（热带/亚热带）的湿地百分比分布可视化**。

**背景**: GWD30 标准化尚未完成，但 Phase 2-5 的比较分析需要直观的湿地分布概览。本 Phase 使用已标准化的 7 个数据集（Berkeley, G2017, GIEMS-MC, GLWD v2, SWAMPS, TOPMODEL, WAD2M）生成粗尺度可视化。

---

## 数据集清单（基于 HPC 现有标准化数据）

```
~/Wetland_Assemble/data/standardized/
├── berkeley_rwawc_2018.nc  → 2025.nc   # 8 年，月分辨率
├── g2017.nc                               # 静态，13 个 frac 变量
├── giems_mc_1993.nc → 2007.nc            # 15 年，月分辨率
├── glwd_v2.nc                             # 静态，34 个 frac 变量
├── swamps_1992.nc → 2020.nc              # 29 年，日分辨率
├── topmodel_1980.nc → 2015.nc            # 需确认年份，月分辨率 + config/forcing 维度
├── wad2m_2000.nc → 2020.nc               # 21 年，月分辨率
└── metadata.json
```

**注意**: GWD30 暂未加入（等待 Phase 1.5 完成）。

---

## 可视化目标

### 1. 单数据集湿地百分比分布图

对每个数据集生成：
- **空间分布图**: 热带/亚热带全域的湿地百分比热力图
- **时间序列**: 年/月平均湿地面积变化曲线
- **直方图**: 像元湿地百分比分布频率

### 2. 多数据集对比图

- **并排对比**: 所有数据集在同一投影下的湿地百分比分布（2×4 网格）
- **统计对比**: 各数据集的总面积、平均值、标准差对比柱状图
- **一致性图**: 多数据集重叠区域的一致性分析

---

## 技术规格

### 空间范围

| 区域 | BBox | 用途 |
|------|------|------|
| 热带 | [-180, -23.5, 180, 23.5] | 热带区域分析 |
| 亚热带 | [-180, -35, 180, -23.5] | 亚热带区域分析 |
| 热带 + 亚热带 | [-180, -35, 180, 23.5] | 全尺度分析 |

### 输出格式

- **静态图**: PNG (300 dpi), PDF (矢量)
- **交互式**: HTML (可选，使用 bokeh/plotly)

### 颜色方案

- **连续数据** (湿地百分比): viridis/cividis 颜色映射，[0, 1] 范围
- **分类数据**: 使用 FINE_4CLASS_COLORS 或数据集特定配色

---

## 新增文件

### 1. `src/WA/visualization/coarse_scale.py`

```python
"""粗尺度湿地百分比分布可视化模块"""

def plot_wetland_percentage_distribution(
    dataset: xr.Dataset,
    dataset_id: str,
    year: int | None = None,
    region: Literal["tropical", "subtropical", "all"] = "all",
    output_path: Path,
) -> Path:
    """生成单数据集的湿地百分比分布图"""

def plot_multi_dataset_comparison(
    datasets: dict[str, xr.Dataset],
    year: int,
    region: Literal["tropical", "subtropical", "all"] = "all",
    output_path: Path,
) -> Path:
    """生成多数据集并排对比图 (2×4 网格)"""

def plot_temporal_comparison(
    datasets: dict[str, xr.Dataset],
    region: Literal["tropical", "subtropical", "all"] = "all",
    output_path: Path,
) -> Path:
    """生成时间序列对比图"""

def plot_wetland_area_statistics(
    datasets: dict[str, xr.Dataset],
    year: int,
    region: Literal["tropical", "subtropical", "all"] = "all",
    output_path: Path,
) -> Path:
    """生成统计对比柱状图（总面积、平均值、标准差）"""
```

### 2. `scripts/plot_coarse_scale.py`

```bash
# 单数据集可视化
python scripts/plot_coarse_scale.py \
    --dataset berkeley_rwawc \
    --year 2020 \
    --region all \
    --output-dir results/figures/phase16

# 多数据集对比（指定年份）
python scripts/plot_coarse_scale.py \
    --compare \
    --year 2016 \
    --region tropical_subtropical \
    --output-dir results/figures/phase16

# 时间序列对比
python scripts/plot_coarse_scale.py \
    --temporal \
    --region all \
    --output-dir results/figures/phase16

# 显示进度条
python scripts/plot_coarse_scale.py \
    --compare \
    --year 2016 \
    --region all \
    --progress
```

### 3. `tests/test_visualization/test_coarse_scale.py`

---

## 实施步骤

### Step 1: 确认标准化数据可用性

```bash
# HPC: 检查标准化数据
ls -lh ~/Wetland_Assemble/data/standardized/*.nc
```

### Step 2: 实现 `src/WA/visualization/coarse_scale.py`

- [x] `plot_single_dataset_distribution()` - 单数据集分布图
- [x] `plot_multi_dataset_comparison()` - 多数据集并排对比
- [x] `plot_temporal_comparison()` - 时间序列
- [x] `plot_wetland_area_statistics()` - 统计柱状图

### Step 3: 实现 `scripts/plot_coarse_scale.py` CLI

- [x] 参数解析
- [x] 数据加载逻辑
- [x] 批量生成

### Step 4: 测试 + 验证

```bash
python -m pytest tests/test_visualization/test_coarse_scale.py -v  # 16 passed
python scripts/plot_coarse_scale.py --dataset g2017 --region all
```

---

## 可视化设计

### 单数据集图（单图）

```
┌────────────────────────────────────┐
│  Berkeley-RWAWC 2020 - 湿地百分比   │
├────────────────────────────────────┤
│                                    │
│    [热力图：热带/亚热带全域]        │
│                                    │
├────────────────────────────────────┤
│ [直方图：像元百分比分布]            │
└────────────────────────────────────┘
```

### 多数据集对比（2×4 网格）

```
┌──────┬──────┬──────┬──────┐
│Berkeley│ G2017 │GIEMS │ GLWD │
├──────┼──────┼──────┼──────┤
│SWAMPS │TOPMDL│ WAD2M │ [统计]│
└──────┴──────┴──────┴──────┘
```

---

## 与后续 Phase 的衔接

- **Phase 2**: 使用本 Phase 生成的分布图作为数据质量评估依据
- **Phase 3**: 粗尺度分布 → 细尺度热点选择的桥梁
- **Phase 4/5**: 时间序列分析的基础

---

# 中文版摘要

## 目标

在 GWD30 缺位情况下，使用现有 7 个标准化数据集生成粗尺度（热带/亚热带全域）湿地百分比分布可视化。

## 输出

1. 单数据集分布图（含直方图）
2. 多数据集并排对比图（2×4 网格）
3. 时间序列对比图
4. 统计柱状图（总面积、平均值、标准差）

## 实施顺序

Step 1（确认数据）→ Step 2（可视化模块）→ Step 3（CLI）→ Step 4（测试验证）
