---
title: "feat: Phase 3.6 Global 500m Classification Disagreement — Implementation Plan"
type: feat
status: proposed
date: 2026-03-31
---

# Phase 3.6 全球 500m 分类分歧分析 — 实施方案

## Overview

Phase 3.6 的目标是：在**全球 500m 尺度**上，对 `G2017`、`GLWD v2`、`GWD30` 三个分类数据集做统一 8 类体系下的分类分歧分析，并输出严格限制在**三个数据集都存在**的格点上的 Shannon entropy 表面。

本阶段只讨论**三者交集格点上的分类分歧**，不讨论“2 个数据集存在、1 个缺失”的部分覆盖情形，也不把“像元内部类别混合度”当作主要不确定性指标。

---

## Problem Statement

当前项目已经具备：

- 500m 标准化数据生产能力
- 分类映射配置 `config/classification_mappings.yaml`
- G2017 / GLWD v2 / GWD30 三个分类数据集

但尚未形成一个**全球一致**、**口径严格**的 Phase 3.6 工作流来回答：

1. 在全球 500m 网格上，三个分类数据集在**同一格点**上是否给出相同的大类判断？
2. 哪些区域三者分歧最强？
3. 这种分歧是否可以用一个在 `[0, 1]` 范围内稳定解释的 Shannon entropy 指标表达？

---

## Hard Constraints

本阶段必须遵守以下硬约束：

1. **只使用三个数据集：** `G2017`、`GLWD v2`、`GWD30`
2. **只在三者共同有效的格点上比较**
3. 任一数据集缺失，则该格点：
   - 不计算 entropy
   - 不参与 majority vote
   - 不参与全局统计
4. **统一类别体系必须来自** `config/classification_mappings.yaml`
5. 本阶段**不沿用旧的硬编码 4-class / 8-class 映射表**
6. 本阶段主指标是**跨数据集分类分歧**，不是绝对 accuracy，也不是像元内部类别混合度

---

## Scope

### In Scope

- 基于 YAML 配置构建统一 8 类映射
- 生成三个数据集各自的 8 类主导分类图
- 构建三者共同有效掩膜
- 计算严格三者交集上的 Shannon entropy
- 输出全局 NetCDF 产品和摘要统计

### Out of Scope

- Sentinel-2 热点下载
- AOI 聚类 / hotspot 提取
- 2-of-3 partial overlap 比较
- 使用 probability mixture 直接计算像元内部熵
- 把 Berkeley / WAD2M / SWAMPS 等连续型产品纳入本阶段

---

## Canonical Definitions

### 1. Unified 8-Class Vocabulary

统一类别以 `config/classification_mappings.yaml` 为唯一真源，当前 8 大类为：

| unified_id | 类别名 |
|------------|--------|
| 0 | Non-wetland |
| 1 | Water |
| 2 | Inland Herbaceous Wetlands |
| 3 | Forested Wetlands |
| 4 | Peatland |
| 5 | Floodplain Wetlands |
| 6 | Coastal Wetlands |
| 7 | Artificial Wetlands |

### 2. Valid Cell

对某一数据集，一个 500m 格点满足以下条件才算 valid：

- 对应 unified 8 类 fraction 中至少有一类为有限值
- 8 类 fraction 和大于 0

### 3. Joint Valid Cell

只有当以下条件同时满足时，一个格点才进入比较：

```text
joint_valid = valid_g2017 & valid_glwd_v2 & valid_gwd30
```

### 4. Dominant Class

对每个数据集、每个格点：

- 先得到 unified 8 类 fraction 向量
- 再取 `argmax` 作为该数据集在该格点的**主导类别**

若存在并列最大值，则按 `classification_mappings.yaml` 中的 `priority_rules.order` 破平局。

---

## Proposed Metric

### 主指标：Vote-Based Normalized Shannon Entropy

Phase 3.6 的主指标定义为：

1. 在 joint-valid 格点上，收集三个数据集的主导类别
2. 统计该格点上各 unified class 的投票频率 `p(c)`
3. 计算 Shannon entropy：

```text
H = - Σ p(c) log2 p(c)
```

4. 用 **有效数据集个数** 归一化，而不是用类别总数归一化：

```text
H_norm = H / log2(3)
```

因为本阶段强制要求三者都存在，所以归一化分母固定为 `log2(3)`。

### 解释

- `H_norm = 0`
  - 三个数据集完全一致
- `0 < H_norm < 1`
  - 2 个一致，1 个不同
- `H_norm = 1`
  - 三个数据集各投不同类

### 为什么不用 `log2(8)` 归一化

如果用 `log2(8)` 归一化，三套数据最多只有 3 票，熵永远达不到 1，解释会失真。  
本阶段关心的是**三个数据集之间是否一致**，因此归一化应由**投票主体数量**决定，而不是由理论类别数决定。

---

## Why Not Use Fraction-Mixture Entropy as the Main Metric

不推荐把三个数据集的 8 类 fraction 先平均，再直接对平均向量算 entropy，原因如下：

1. 那会把“像元内部多类别混合”与“数据集之间意见不一致”混在一起
2. 即使三个数据集完全一致、都认为该格点是 50% 水 + 50% 沼泽，该方法也会给出较高 entropy
3. Phase 3.6 的目标是**cross-dataset disagreement**，不是**within-pixel compositional complexity**

因此：

- **主指标**：dominant-class vote entropy
- **可选副指标**：fraction-mix entropy / top1 margin / confidence

---

## Input Assumptions

### 推荐输入

优先使用三个数据集的**标准化 500m 产品**，而不是直接读取原始文件：

- `g2017.nc`
- `glwd_v2.nc`
- `gwd30_<year>.nc`

### 年份口径

- 默认目标年份：`2016`
- `G2017` / `GLWD v2` 为静态产品
- `GWD30` 为动态产品，按目标年份选取

### GWD30 年聚合策略

对 `GWD30_<year>.nc`：

1. 先按原始类 `frac_0 ... frac_14` 读取全年时间序列
2. 依据 YAML 映射，把原始类聚合为 unified 8 类 fraction
3. 再对全年 unified fraction 做时间平均
4. 最后在每个格点上取 dominant class

这样得到的是“该年平均意义上的代表分类”，而不是某个单时相快照。

---

## Workflow

### Step 1: 从 YAML 读取统一映射

新建一个专用 helper，从 `config/classification_mappings.yaml` 读取：

- `dataset_id -> source_class -> unified_id`
- `priority_rules.order -> unified_id priority`
- unified 类别标签

### Step 2: 读取三个数据集的 500m 分类/分数产品

- `G2017`：读取原始类 fraction 或分类结果
- `GLWD v2`：读取原始类 fraction 或分类结果
- `GWD30(year)`：读取逐时相原始类 fraction

### Step 3: 聚合到 unified 8 类 fraction

每个数据集都变成：

```text
(class_id=8, lat, lon)
```

其中每个 `class_id` 对应一个 unified 类。

### Step 4: 生成 dataset-specific valid mask

对每个数据集：

```text
valid_dataset = finite(sum(unified_fractions)) & (sum(unified_fractions) > 0)
```

### Step 5: 生成 joint-valid mask

```text
joint_valid = valid_g2017 & valid_glwd_v2 & valid_gwd30
```

这是整个 Phase 3.6 的硬边界。

### Step 6: 生成三个 dominant-class surface

在每个 joint-valid 格点上：

- 从 unified 8 类 fraction 里取最大值对应的 `class_id`
- 若并列，则按 YAML priority rules 选

### Step 7: 计算 Shannon entropy

对每个 joint-valid 格点：

- 统计 3 个 dominant class 的频率
- 计算 `H_norm = H / log2(3)`

对非 joint-valid 格点：

- `entropy = NaN`

### Step 8: 计算辅助输出

同时输出：

- `majority_class`
- `agreement_count`（1/2/3）
- `joint_valid_mask`

### Step 9: 生成全局汇总统计

在 `joint_valid` 范围内计算：

- global mean entropy
- p50 / p90 / p99 entropy
- 各大类 majority class 面积占比

如果涉及面积平均，必须使用 `cos(lat)` 做面积加权。

---

## Proposed Files

### 新增

- `src/WA/comparison/phase36.py`
- `scripts/run_phase3_6_global_entropy.py`
- `tests/test_phase3_6_analysis.py`
- `docs/phase3_6_metrics_explained.md`

### 可选新增

- `src/WA/classification_mapping.py`
  - 专门负责从 YAML 构建 unified mapping

---

## Proposed API Shape

```python
def load_unified_class_mapping(path: Path) -> UnifiedMappingDocument

def aggregate_source_fractions_to_unified(
    dataset_id: str,
    dataset: xr.Dataset,
    *,
    mapping: UnifiedMappingDocument,
    year: int | None = None,
) -> xr.DataArray:
    \"\"\"Return unified 8-class fractions as (class_id, lat, lon).\"\"\"

def compute_joint_valid_mask(
    unified_fractions: dict[str, xr.DataArray],
) -> xr.DataArray:
    \"\"\"Return bool mask where all three datasets are valid.\"\"\"

def compute_dominant_class(
    fractions: xr.DataArray,
    *,
    priority_order: list[int],
) -> xr.DataArray:
    \"\"\"Return dominant unified class id per cell.\"\"\"

def compute_vote_entropy(
    dominant_classes: dict[str, xr.DataArray],
    *,
    joint_valid_mask: xr.DataArray,
) -> xr.Dataset:
    \"\"\"Return entropy, majority_class, agreement_count, joint_valid_mask.\"\"\"
```

---

## Output Products

### NetCDF

- `phase3_6_entropy_global_500m_2016.nc`
  - `entropy`
  - `majority_class`
  - `agreement_count`
  - `joint_valid_mask`

- `phase3_6_unified_classes_global_500m_2016.nc`
  - `g2017_dominant_class`
  - `glwd_v2_dominant_class`
  - `gwd30_dominant_class`

### JSON

- `phase3_6_summary_global_500m_2016.json`

内容建议包括：

- target year
- valid cell count
- joint-valid area share
- mean / p50 / p90 / p99 entropy
- class histogram of majority class

---

## Performance Strategy

全球 500m 计算量很大，实施时必须采用分块策略。

### 推荐策略

1. 按纬度条带分块，例如：
   - 每块 512 或 1024 行
2. 每块独立完成：
   - unified fraction 聚合
   - valid mask
   - dominant class
   - entropy
3. 最终再顺序写入 NetCDF

### 禁止

- 一次性把三个全球产品完整读入内存后再计算
- 在 full-resolution GWD30 原始镶嵌上直接做全球运算

---

## Edge Cases

### 1. Dataset Tie Within One Cell

若某数据集在某格点上两个 unified 类 fraction 完全相同：

- 使用 YAML `priority_rules` 破平局

### 2. Sum of Fractions < 1

允许存在浮点误差或局部覆盖不足，但 valid 判定必须满足：

- finite
- sum > 0

### 3. One Dataset Has All-NaN at a Cell

- joint-valid 直接为 false
- entropy 直接为 NaN

### 4. GWD30 Year Has Sparse Coverage

- 不做 partial comparison
- 只有在 `G2017 + GLWD + GWD30` 同时 valid 的格点才保留

---

## Validation Plan

### 单元测试

新增 `tests/test_phase3_6_analysis.py`，至少覆盖：

1. `test_yaml_mapping_builds_complete_unified_lookup`
2. `test_joint_valid_requires_all_three_datasets`
3. `test_dominant_class_uses_priority_rules_for_ties`
4. `test_entropy_is_zero_when_all_three_agree`
5. `test_entropy_is_one_when_all_three_disagree`
6. `test_entropy_is_partial_when_two_agree_one_differs`
7. `test_non_joint_valid_cells_become_nan`
8. `test_gwd30_annual_mean_then_argmax_pipeline`
9. `test_majority_class_and_agreement_count_outputs`
10. `test_global_summary_uses_cos_lat_weighting`

### 集成验证

1. 小 bbox 冒烟测试
2. 单块纬带测试
3. 全局 dry-run（只检查输入、shape、坐标、输出路径）

---

## Acceptance Criteria

- [ ] Phase 3.6 只使用 `G2017 / GLWD v2 / GWD30`
- [ ] 统一类别体系完全来自 `config/classification_mappings.yaml`
- [ ] 只在三者共同有效格点上比较
- [ ] 非 joint-valid 格点全部输出为 `NaN`
- [ ] 熵归一化使用 `log2(3)`，不是 `log2(8)`
- [ ] 完全一致格点熵为 `0`
- [ ] 三者各不相同格点熵为 `1`
- [ ] 输出至少包含 `entropy / majority_class / agreement_count / joint_valid_mask`
- [ ] 文档与测试全部齐备

---

## Recommended Execution Order

1. 实现 YAML mapping loader
2. 实现 unified fraction aggregation
3. 实现 joint-valid mask
4. 实现 dominant class + tie-break
5. 实现 vote entropy
6. 实现 global summary
7. 加入 CLI
8. 做小范围测试
9. 做全球 dry-run

---

## 中文摘要

Phase 3.6 的核心不是“像元内部有多混合”，而是“`G2017 / GLWD / GWD30` 三个数据集在同一个 500m 格点上是否给出相同的大类判断”。因此主指标应定义为：在**三个数据集都存在**的格点上，先让每个数据集投出一个 unified 8 类的主导类别，再对这 3 票计算 Shannon entropy，并用 `log2(3)` 归一化到 `[0,1]`。所有非三者交集格点都直接设为 `NaN`。整个阶段只做全球分类分歧分析，不做 hotspot、S2 下载或 partial overlap 比较。
