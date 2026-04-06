---
date: 2026-03-29
phase: Phase 1.6
title: 粗尺度湿地百分比分布可视化实现
---

# Phase 1.6 实现总结

## 完成内容

实现了粗尺度湿地百分比分布可视化模块，支持在 GWD30 缺位情况下对其他 7 个标准化数据集进行全域可视化分析。

## 新增文件

### 1. `src/WA/visualization/coarse_scale.py`
核心可视化模块，包含以下函数：
- `_get_wetland_variable()` - 从不同数据集类型提取湿地变量
- `_aggregate_temporal()` - 时间维度聚合（mean/sum/max/min）
- `_clip_to_bbox()` - 按区域边界裁剪数据
- `_compute_statistics()` - 计算统计量（mean/std/min/max/total）
- `plot_single_dataset_distribution()` - 单数据集分布图（含直方图和统计框）
- `plot_multi_dataset_comparison()` - 多数据集并排对比（2×4 网格）
- `plot_temporal_comparison()` - 时间序列对比图
- `plot_wetland_area_statistics()` - 统计柱状图

### 2. `scripts/plot_coarse_scale.py`
CLI 脚本，支持四种模式：
```bash
# 单数据集可视化
python scripts/plot_coarse_scale.py --dataset berkeley_rwawc --year 2020 --region all

# 多数据集对比
python scripts/plot_coarse_scale.py --compare --year 2016 --region tropical_subtropical

# 时间序列对比
python scripts/plot_coarse_scale.py --temporal --region all

# 统计柱状图
python scripts/plot_coarse_scale.py --statistics --year 2016 --region all

# 显示进度条
python scripts/plot_coarse_scale.py --compare --year 2016 --region all --progress
```

### 3. `tests/test_visualization/test_coarse_scale.py`
16 个单元测试，覆盖：
- 湿地变量提取（连续/分类/缺失）
- 时间聚合
- 边界裁剪（热带/亚热带）
- 统计计算
- 单数据集绘图
- 多数据集对比
- 时间序列对比
- 统计图

### 4. `docs/plans/2026-03-29-001-phase16-coarse-scale-wetland-percentage.md`
Phase 1.6 计划文档

## 技术细节

### 区域定义
- `tropical`: [-180, -23.5, 180, 23.5]
- `subtropical`: [-180, -35, 180, -23.5]
- `tropical_subtropical` / `all`: [-180, -35, 180, 23.5]

### 数据集颜色方案
为每个数据集分配了独特颜色以便区分：
- Berkeley-RWAWC: 蓝色 (#1f77b4)
- G2017: 橙色 (#ff7f0e)
- GIEMS-MC: 绿色 (#2ca02c)
- GLWD v2: 红色 (#d62728)
- SWAMPS: 紫色 (#9467bd)
- TOPMODEL: 棕色 (#8c564b)
- WAD2M: 粉色 (#e377c2)

### 湿地变量提取策略
1. **连续数据集**: 直接读取 `wetland_fraction` 变量
2. **分类数据集**: 求和所有 `frac_*` 变量（排除 `frac_0` 非湿地类）

## 测试结果

```
295 passed, 14 warnings in 11.92s
```

所有测试通过，包括新增的 16 个 coarse_scale 测试。

## 使用说明

### HPC 使用流程

1. **确认标准化数据可用**
```bash
ls -lh ~/Wetland_Assemble/data/standardized/*.nc
```

2. **生成单数据集图**
```bash
python scripts/plot_coarse_scale.py \
    --dataset g2017 \
    --region all \
    --output-dir results/figures/phase16
```

3. **生成多数据集对比（指定年份）**
```bash
python scripts/plot_coarse_scale.py \
    --compare \
    --year 2016 \
    --region tropical_subtropical \
    --output-dir results/figures/phase16
```

4. **生成时间序列对比**
```bash
python scripts/plot_coarse_scale.py \
    --temporal \
    --region all \
    --output-dir results/figures/phase16
```

**注意**: 脚本会自动检测 HPC 环境并使用正确的数据路径 `~/Wetland_Assemble/data/standardized/`。如果在本地开发环境运行，可使用 `--data-dir` 显式指定路径。

### 显示进度条

添加 `--progress` 参数显示绘图进度：

```bash
python scripts/plot_coarse_scale.py \
    --compare \
    --year 2016 \
    --region all \
    --progress
```

进度条会显示：
- 数据集加载进度
- 每个数据集的处理进度
- 绘图进度

### 显式指定数据路径（可选）

```bash
python scripts/plot_coarse_scale.py \
    --data-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized \
    --compare \
    --year 2016 \
    --region all
```

## 与后续 Phase 衔接

- **Phase 2**: 使用本 Phase 生成的分布图作为数据质量评估依据
- **Phase 3**: 粗尺度分布 → 细尺度热点选择的桥梁
- **Phase 4/5**: 时间序列分析的基础

## 备注

- GWD30 暂未加入可视化（等待 Phase 1.5 标准化完成）
- TOPMODEL 年份需根据 config 确认全面性
- 所有输出默认保存为 PNG (150 dpi)，可通过 `--dpi` 参数调整
