---
title: "Phase 1.1: Loader 体系重构"
type: feat
status: in_progress
date: 2026-03-30
---

# Phase 1.1: Loader 体系重构

## Overview

重构当前 loader 体系，使其从“按原始数据格式分别实现”转为“按数据源策略统一实现”。

本阶段的目标不是继续扩展旧 loader，而是建立一套更稳定的访问层，满足以下新约束：

1. Berkeley / G2017 / GLWD v2 / TOPMODEL 直接读取 HPC 上已经标准化好的 netCDF 数据。
2. GIEMS-MC / SWAMPS / WAD2M 继续读取原始数据。
3. GWD30 不再依赖整年 merged netCDF，转向 TileNC + manifest 驱动的按需读取。
4. 所有 coarse-scale 湿地百分比提取必须遵守 `config/classification_mappings.yaml`，且不得把 waterbody 计入 wetland percentage。

---

## 数据源分层

### A. 标准化源（直接读 `~/Wetland_Assemble/data/standardized`）

适用数据集：

- `berkeley_rwawc`
- `g2017`
- `glwd_v2`
- `topmodel`

文件约定：

- 静态：`[dataset].nc`
- 动态：`[dataset]_[YYYY].nc`

设计要求：

- 统一由标准化 netCDF loader 负责。
- 动态数据按 `time_range` 自动定位所需年份文件，可跨年拼接。
- 支持 `bbox` 子集、`reference_grid` 对齐、懒加载打开。

### B. 原始源（继续读原始数据）

适用数据集：

- `giems_mc`
- `swamps`
- `wad2m`

设计要求：

- 保留 raw loader，但接口与标准化 loader 对齐。
- 配置仍由 `config/datasets.yaml` 管理。
- 输出仍统一为规范化的 `xr.Dataset`。

### C. GWD30 专用源（TileNC / manifest）

适用数据集：

- `gwd30`

设计要求：

- 通过 manifest 确认 bbox / year 所需 tiles。
- 按需读取 tile partial / TileNC，而不是依赖年度 merged 文件。
- 支持面向不同任务的读取模式：
  - native classification 提取
  - coarse fraction 聚合
  - 特定预处理后读取（例如先重采样到 `0.25deg`）

当前结论：

- GWD30 路径单独规划和验证。
- 本阶段先为 GWD30 保留清晰入口和配置契约，不强行把复杂逻辑塞回普通 standardized loader。

---

## 代码结构调整

### 1. Loader 层

- 新增统一的 standardized netCDF loader。
- 原 `StandardizedDataLoader` 不再作为游离于主体系之外的工具，需与主 loader contract 对齐。
- `config/datasets.yaml` 中的数据集条目改为描述“来源策略”，而不是只描述“原始格式”。

### 2. 分类规则层

- 新增 classification helper，从 `config/classification_mappings.yaml` 读取最新分类方案。
- 所有 binary / coarse-scale / fraction 提取逻辑不再硬编码 class map。
- 提供统一能力：
  - 查询某数据集的 water classes
  - 查询某数据集的 wetland classes
  - 构造 “water excluded” 的 wetland binary / fraction 掩膜

### 3. 消费层

受影响模块：

- `src/WA/comparison/harmonize.py`
- `src/WA/visualization/coarse_scale.py`
- 与 loader 直接耦合的脚本 / 测试

要求：

- coarse-scale wetland percentage 必须排除 waterbody
- harmonize 的分类二值化逻辑必须与 YAML 分类方案一致

---

## 实施顺序

### Step 1

新增 Phase 1.1 规划文档，并明确 GWD30 单独拆分。

### Step 2

引入 classification helper，替换 `harmonize.py` 和 coarse-scale 中的硬编码类别逻辑。

### Step 3

新增 standardized netCDF loader，并将 Berkeley / G2017 / GLWD v2 / TOPMODEL 切到标准化目录。

### Step 4

保留 GIEMS-MC / SWAMPS / WAD2M raw loader，并统一接口行为。

### Step 5

为 GWD30 TileNC 路径定义单独配置和入口，后续另开验证任务。

### Step 6

补齐测试，运行 `ruff` 和 `python -m pytest tests/`。

---

## 风险与边界

1. 若直接替换 `config/datasets.yaml` 的 loader 策略，依赖“原始数据标准化”的旧脚本可能不再适用，需要接受这一架构转向。
2. TOPMODEL 和 Berkeley 虽然转为 standardized source，但仍需保留跨年拼接与时间窗口筛选能力。
3. GWD30 不能被降级成“再做一个普通 annual nc loader”；否则会再次回到 merge 路径的性能与稳定性问题。

---

## 中文摘要

Phase 1.1 的核心不是“再写几个 loader”，而是把 loader 体系拆成三类来源：

- 标准化 netCDF 直读：Berkeley / G2017 / GLWD v2 / TOPMODEL
- 原始数据直读：GIEMS-MC / SWAMPS / WAD2M
- TileNC + manifest 按需读取：GWD30

同时把分类规则统一收口到 `classification_mappings.yaml`，确保后续所有 coarse-scale 湿地百分比计算都不会把 waterbody 算进湿地面积。
