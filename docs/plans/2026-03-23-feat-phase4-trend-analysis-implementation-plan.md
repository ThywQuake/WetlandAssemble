---
title: "feat: Phase 4 Trend Analysis Implementation Plan"
type: feat
status: active
date: 2026-03-23
parent: docs/plans/2026-03-19-005-feat-phase4-trend-analysis-plan.md
---

# Phase 4 趋势分析落实计划

## Overview

Phase 4 对所有动态湿地数据集执行时间序列趋势分析，并量化数据集间趋势方向的一致性。本计划基于现有 Phase 4 设计文档（`2026-03-19-005`），结合 legacy 代码库的成熟实现，提供可直接执行的实施路线。

**实施策略：**
- **一步到位**：trends.py + trend_agreement.py + 所有聚合层级（annual/seasonal/monthly）+ HPC probe 一次完成
- **纯 scipy**：不引入 pymannkendall 依赖，使用 legacy 的 scipy kendalltau + theilslopes fallback
- **向量化优先**：复用 legacy 的 `xr.apply_ufunc` + dask 并行模式

**当前基础：**
- ✅ Phase 1-3 完成，110/110 tests passing
- ✅ `harmonize_binary_dataset()` 返回带 time 维度的 wetland_fraction DataArray
- ✅ Legacy `/Users/mac/Code/Wetland_Assemble/src/wetland_analysis/analysis/trend.py` 有成熟参考实现
- ✅ scipy 已在 dependencies，无需新增依赖

---

## 参与数据集

仅动态时间序列数据集参与趋势分析：

| 数据集 | 时间范围 | 原始分辨率 | 趋势输入 | 传感器断裂 |
|--------|---------|-----------|---------|-----------|
| SWAMPS | 1992-2020 | daily | wetland_fraction | 2000 (F11→F13) |
| GIEMS-MC | 1993-2007 | monthly | inundation | 2007 终止 |
| WAD2M | 2000-2020 | monthly | wetland_fraction | - |
| TOPMODEL | varies | monthly | wetland_fraction (ensemble mean) | - |
| GWD30 | 2013-2022 | 4-day | wetland_fraction (from class) | - |

**静态数据集 (G2017, GLWD v2) 和 Berkeley-RWAWC 不参与趋势分析。**

---

## 文件清单

### 新建文件 (6 files)

| 文件 | 说明 |
|------|------|
| `src/WA/comparison/trends.py` | 单数据集 MK + Sen's Slope 逐像素趋势 |
| `src/WA/comparison/trend_agreement.py` | 跨数据集趋势一致性 |
| `tests/test_comparison/test_trends.py` | 趋势分析测试（9 tests） |
| `tests/test_comparison/test_trend_agreement.py` | 趋势一致性测试（7 tests） |
| `scripts/hpc_probe_trends.py` | HPC 趋势诊断脚本 |
| `scripts/run_phase4_trend_analysis.py` | Phase 4 批量趋势分析 CLI |

### 修改文件 (1 file)

| 文件 | 变更 |
|------|------|
| `src/WA/comparison/__init__.py` | 导出 trends + trend_agreement 模块 |

---

## Task 4.1: trends.py — 单数据集趋势

### 核心数据结构

```python
# src/WA/comparison/trends.py

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats

from WA.loaders.base import BBox

AggregationLevel = Literal["annual", "seasonal", "monthly"]

@dataclass(frozen=True)
class TrendResult:
    """Per-pixel Mann-Kendall + Sen's Slope trend analysis result."""

    dataset_id: str
    aggregation: AggregationLevel
    time_range: tuple[str, str]  # ISO format (start, end)
    observation_count: int
    sens_slope: xr.DataArray      # fraction per time unit
    p_value: xr.DataArray
    z_score: xr.DataArray
    significant: xr.DataArray     # bool mask (p < alpha)
    trend_direction: xr.DataArray # +1 (increasing), 0 (stable), -1 (decreasing)
    status: str  # "computed" | "insufficient_observations"
```

### 核心函数签名

```python
def compute_pixel_trends(
    harmonized_surface: xr.DataArray,
    *,
    dataset_id: str,
    aggregation: AggregationLevel = "annual",
    confidence_level: float = 0.95,
    min_observations: int = 5,
) -> TrendResult:
    """Per-pixel Mann-Kendall + Sen's Slope trend test.

    Implementation:
    1. Aggregate time series to target level (annual/seasonal/monthly)
    2. Drop pixels with < min_observations valid values
    3. For each pixel: MK test (z, p) + Theil-Sen slope via scipy
    4. Vectorize via xr.apply_ufunc with dask='parallelized'
    5. Return TrendResult with 5 spatial variables

    Parameters
    ----------
    harmonized_surface : xr.DataArray
        Output from harmonize_binary_dataset(), dims (time, lat, lon)
    dataset_id : str
        Dataset identifier for metadata
    aggregation : AggregationLevel
        Time aggregation: "annual", "seasonal", or "monthly"
    confidence_level : float
        Confidence level for significance test (default 0.95)
    min_observations : int
        Minimum valid time steps required (default 5)

    Returns
    -------
    TrendResult
        Dataclass with 5 spatial DataArrays + metadata
    """

def compute_year_over_year_change(
    harmonized_surface: xr.DataArray,
    *,
    dataset_id: str,
) -> xr.Dataset:
    """Short-term year-over-year wetland fraction change.

    Returns Dataset with:
    - delta_fraction: annual diff (year N - year N-1)
    - change_direction: +1/0/-1

    No statistical test — just raw differences for short-term monitoring.
    """

def compute_regional_summary(
    trend_result: TrendResult,
    region_bboxes: Mapping[str, BBox],
) -> pd.DataFrame:
    """Regional summary for 4 regions + full domain.

    Per region row:
    - mean_slope, median_slope
    - fraction_significant
    - fraction_increasing, fraction_decreasing, fraction_stable
    - total_valid_pixels
    """
```

### Mann-Kendall 实现策略

从 legacy `Wetland_Assemble/src/wetland_analysis/analysis/trend.py` 移植核心逻辑：

```python
def _pixel_mann_kendall(
    values: np.ndarray,
    alpha: float,
) -> tuple[float, float, float, float, float]:
    """Single pixel MK + Sen's slope using scipy.

    Returns: (sens_slope, p_value, z_score, significant, direction)

    Strategy:
    1. scipy.stats.kendalltau(x, values) for tau and p-value
    2. scipy.stats.theilslopes(values, x) for Sen's slope
    3. Convert tau to z-score via normal distribution
    4. significant = (p_value < alpha)
    5. direction = sign(slope) if significant else 0
    """
    if len(values) < 4:
        return (np.nan, 1.0, 0.0, 0.0, 0.0)

    if np.ptp(values) == 0:  # All values identical
        return (0.0, 1.0, 0.0, 0.0, 0.0)

    x = np.arange(len(values), dtype=float)

    # Mann-Kendall via Kendall's tau
    tau, p_value = stats.kendalltau(x, values, nan_policy="omit")

    # Sen's slope via Theil-Sen estimator
    slope, _, _, _ = stats.theilslopes(values, x)

    # Convert tau to z-score
    if p_value <= 0.0:
        z_score = float(np.sign(tau) * 8.0)
    else:
        z_score = float(np.sign(tau) * stats.norm.isf(p_value / 2.0))

    significant = float(p_value < alpha)
    direction = (
        1.0 if significant and slope > 0
        else -1.0 if significant and slope < 0
        else 0.0
    )

    return (float(slope), float(p_value), z_score, significant, direction)
```

### 向量化实现

```python
def _vectorized_mk_test(
    data: xr.DataArray,
    alpha: float,
    time_dim: str = "time",
) -> xr.Dataset:
    """Vectorized MK test via xr.apply_ufunc + dask."""

    result = xr.apply_ufunc(
        _pixel_mann_kendall,
        data,
        kwargs={"alpha": alpha},
        input_core_dims=[[time_dim]],
        output_core_dims=[[], [], [], [], []],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[float, float, float, float, float],
    )

    return xr.Dataset({
        "sens_slope": result[0],
        "p_value": result[1],
        "z_score": result[2],
        "significant": result[3].astype(bool),
        "trend_direction": result[4].astype(np.int8),
    })
```

### 时间聚合

```python
def _aggregate_time_series(
    data: xr.DataArray,
    aggregation: AggregationLevel,
) -> xr.DataArray:
    """Aggregate time series to target level."""

    if aggregation == "annual":
        return data.resample(time="YS").mean(skipna=True)

    elif aggregation == "seasonal":
        # Group by season: DJF, MAM, JJA, SON
        return data.groupby("time.season").mean(skipna=True)

    elif aggregation == "monthly":
        return data.resample(time="MS").mean(skipna=True)

    else:
        raise ValueError(f"Unknown aggregation: {aggregation}")
```

### 测试设计

```python
# tests/test_comparison/test_trends.py

def test_compute_pixel_trends_increasing_series():
    """Increasing trend should have positive slope and direction=+1."""

def test_compute_pixel_trends_decreasing_series():
    """Decreasing trend should have negative slope and direction=-1."""

def test_compute_pixel_trends_stable_series():
    """Stable series should have slope≈0 and direction=0."""

def test_compute_pixel_trends_insufficient_observations():
    """< min_observations should return status='insufficient_observations'."""

def test_compute_year_over_year_change():
    """YoY change should compute annual diffs correctly."""

def test_compute_regional_summary_covers_all_regions():
    """Regional summary should include all 4 regions + full domain."""

def test_seasonal_aggregation_groups_correctly():
    """Seasonal aggregation should group DJF/MAM/JJA/SON."""

def test_annual_aggregation_resamples_correctly():
    """Annual aggregation should resample to year-start."""

def test_monthly_aggregation_preserves_monthly():
    """Monthly aggregation should preserve monthly resolution."""
```

---

## Task 4.2: trend_agreement.py — 跨数据集一致性

### 核心数据结构

```python
# src/WA/comparison/trend_agreement.py

@dataclass(frozen=True)
class TrendAgreementResult:
    """Cross-dataset trend consistency analysis result."""

    overlap_window: tuple[str, str]  # ISO format (start, end)
    participant_ids: list[str]
    agreement_ratio: xr.DataArray       # 0-1, fraction agreeing on direction
    mean_slope: xr.DataArray            # mean across datasets
    slope_std: xr.DataArray             # std across datasets
    robust_increase: xr.DataArray       # bool, all datasets agree on increase
    robust_decrease: xr.DataArray       # bool, all datasets agree on decrease
    robust_stable: xr.DataArray         # bool, all datasets agree on stable
    disputed: xr.DataArray              # bool, any pair disagrees
    regional_summary: pd.DataFrame
    status: str  # "computed" | "overlap_window_empty"
```

### 核心函数签名

```python
def compute_overlap_window(
    trend_results: Mapping[str, TrendResult],
) -> tuple[str, str] | None:
    """Find the maximum common time window across all participants.

    Logic:
    - start = max(all dataset start dates)
    - end = min(all dataset end dates)
    - If start > end: return None (no overlap)
    """

def compute_trend_agreement(
    trend_results: Mapping[str, TrendResult],
    *,
    overlap_strategy: str = "maximum_common",
    min_overlap_years: int = 5,
    region_bboxes: Mapping[str, BBox] | None = None,
) -> TrendAgreementResult:
    """Cross-dataset trend consistency.

    Steps:
    1. Find overlap window via compute_overlap_window()
    2. Re-compute trends for each dataset within overlap window
    3. Stack trend_direction arrays along 'dataset' dim
    4. Agreement = fraction of datasets with same direction
    5. Robust = all datasets agree (agreement_ratio == 1.0)
    6. Disputed = any pair disagrees (agreement_ratio < 1.0)
    7. Regional summary for 4 regions + full domain

    Parameters
    ----------
    trend_results : Mapping[str, TrendResult]
        Per-dataset trend results from compute_pixel_trends()
    overlap_strategy : str
        "maximum_common" (default) or "pairwise"
    min_overlap_years : int
        Minimum overlap duration required (default 5)
    region_bboxes : Mapping[str, BBox] | None
        Region definitions (default: DEFAULT_FOCUS_REGION_BBOXES)

    Returns
    -------
    TrendAgreementResult
        Cross-dataset agreement metrics + regional summary
    """
```

### 一致性计算逻辑

```python
def _compute_agreement_metrics(
    stacked_directions: xr.DataArray,  # dims: (dataset, lat, lon)
) -> dict[str, xr.DataArray]:
    """Compute agreement metrics from stacked trend directions.

    Returns dict with:
    - agreement_ratio: fraction of datasets agreeing on direction
    - robust_increase: all datasets have direction=+1
    - robust_decrease: all datasets have direction=-1
    - robust_stable: all datasets have direction=0
    - disputed: not all datasets agree
    """

    n_datasets = stacked_directions.sizes["dataset"]

    # Count how many datasets agree on each direction per pixel
    count_increase = (stacked_directions == 1).sum(dim="dataset")
    count_decrease = (stacked_directions == -1).sum(dim="dataset")
    count_stable = (stacked_directions == 0).sum(dim="dataset")

    # Agreement ratio = max count / total datasets
    max_count = xr.concat([count_increase, count_decrease, count_stable], dim="direction").max(dim="direction")
    agreement_ratio = max_count / n_datasets

    # Robust = all datasets agree
    robust_increase = (count_increase == n_datasets)
    robust_decrease = (count_decrease == n_datasets)
    robust_stable = (count_stable == n_datasets)

    # Disputed = not all agree
    disputed = (agreement_ratio < 1.0)

    return {
        "agreement_ratio": agreement_ratio,
        "robust_increase": robust_increase,
        "robust_decrease": robust_decrease,
        "robust_stable": robust_stable,
        "disputed": disputed,
    }
```

### 区域汇总

```python
def _compute_regional_summary(
    agreement_result: dict[str, xr.DataArray],
    region_bboxes: Mapping[str, BBox],
) -> pd.DataFrame:
    """Compute regional summary statistics.

    Per region row:
    - region: str
    - total_valid_pixels: int
    - fraction_robust_increase: float
    - fraction_robust_decrease: float
    - fraction_robust_stable: float
    - fraction_disputed: float
    - mean_agreement_ratio: float
    - mean_slope_across_datasets: float
    """

    rows = []
    for region_slug, bbox in region_bboxes.items():
        # Crop to region bbox
        west, south, east, north = bbox
        regional = {
            key: arr.sel(lon=slice(west, east), lat=slice(north, south))
            for key, arr in agreement_result.items()
        }

        # Compute fractions
        total = int(regional["agreement_ratio"].count().item())
        if total == 0:
            continue

        rows.append({
            "region": region_slug,
            "total_valid_pixels": total,
            "fraction_robust_increase": float(regional["robust_increase"].sum() / total),
            "fraction_robust_decrease": float(regional["robust_decrease"].sum() / total),
            "fraction_robust_stable": float(regional["robust_stable"].sum() / total),
            "fraction_disputed": float(regional["disputed"].sum() / total),
            "mean_agreement_ratio": float(regional["agreement_ratio"].mean()),
        })

    return pd.DataFrame(rows)
```

### 测试设计

```python
# tests/test_comparison/test_trend_agreement.py

def test_compute_overlap_window_common_range():
    """Overlap window should be max(starts) to min(ends)."""

def test_compute_overlap_window_no_overlap():
    """Non-overlapping time ranges should return None."""

def test_trend_agreement_all_increasing():
    """All datasets increasing → robust_increase=True everywhere."""

def test_trend_agreement_all_decreasing():
    """All datasets decreasing → robust_decrease=True everywhere."""

def test_trend_agreement_disputed():
    """Mixed directions → disputed=True, agreement_ratio < 1.0."""

def test_trend_agreement_regional_summary():
    """Regional summary should cover all regions."""

def test_overlap_window_empty_status():
    """No overlap → status='overlap_window_empty'."""
```

---

## Task 4.3: HPC Probe Script

### 脚本结构

```python
# scripts/hpc_probe_trends.py

"""HPC diagnostic script for Phase 4 trend analysis."""

import argparse
import json
from pathlib import Path

from WA.comparison import harmonize_binary_dataset, create_comparison_grid
from WA.comparison.trends import compute_pixel_trends
from WA.loaders import get_loader

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--aggregation", default="annual", choices=["annual", "seasonal", "monthly"])
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"))
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    # Load dataset
    loader = get_loader(args.dataset_id)
    dataset = loader.load(bbox=args.bbox)

    # Harmonize
    reference_grid = create_comparison_grid(args.bbox)
    harmonized = harmonize_binary_dataset(
        args.dataset_id,
        dataset,
        reference_grid=reference_grid,
    )

    # Compute trends
    result = compute_pixel_trends(
        harmonized,
        dataset_id=args.dataset_id,
        aggregation=args.aggregation,
    )

    # Report
    report = {
        "dataset_id": result.dataset_id,
        "aggregation": result.aggregation,
        "time_range": result.time_range,
        "observation_count": result.observation_count,
        "status": result.status,
        "significant_pixels": int(result.significant.sum().item()),
        "increasing_pixels": int((result.trend_direction == 1).sum().item()),
        "decreasing_pixels": int((result.trend_direction == -1).sum().item()),
        "stable_pixels": int((result.trend_direction == 0).sum().item()),
        "mean_slope": float(result.sens_slope.mean().item()),
    }

    print(json.dumps(report, indent=2))

    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
```

---

## 输出产物

```
results/trends/
  {dataset_id}_annual_trend.nc        # 5-variable trend raster
  {dataset_id}_seasonal_trend.nc
  {dataset_id}_monthly_trend.nc
  {dataset_id}_yoy_change.nc          # year-over-year change
  cross_dataset_agreement_{overlap}.nc
  regional_summaries.csv              # all regions x all aggregation levels
```

---

## Acceptance Criteria

- [ ] `trends.py`: 每个动态数据集产出 annual + seasonal + monthly 趋势（5 变量 Dataset）
- [ ] Mann-Kendall p-value 和 Sen's Slope 对合成数据正确（increasing/decreasing/stable）
- [ ] 短期 year-over-year 变化摘要
- [ ] `trend_agreement.py`: 跨数据集一致性图（robust increase/decrease/stable/disputed）
- [ ] 区域汇总覆盖 4 区域 + 全域
- [ ] `insufficient_observations` 正确标记短时序（< min_observations）
- [ ] `overlap_window_empty` 正确标记无重叠情况
- [ ] 纯 scipy 实现，无 pymannkendall 依赖
- [ ] `pytest` + `ruff` + `mypy` 通过
- [ ] HPC probe 脚本在 tropical bbox 上成功运行

---

## Implementation Order

### Step 1: trends.py 核心实现

1. 从 legacy 移植 `_pixel_mann_kendall()` 函数（scipy 版本）
2. 实现 `_aggregate_time_series()` 时间聚合
3. 实现 `_vectorized_mk_test()` 向量化包装
4. 实现 `compute_pixel_trends()` 主函数
5. 实现 `compute_year_over_year_change()`
6. 实现 `compute_regional_summary()`

### Step 2: trends.py 测试

编写 9 个测试用例，覆盖：
- Increasing/decreasing/stable 趋势识别
- Insufficient observations 处理
- Annual/seasonal/monthly 聚合
- YoY change 计算
- Regional summary

### Step 3: trend_agreement.py 核心实现

1. 实现 `compute_overlap_window()`
2. 实现 `_compute_agreement_metrics()`
3. 实现 `_compute_regional_summary()`
4. 实现 `compute_trend_agreement()` 主函数

### Step 4: trend_agreement.py 测试

编写 7 个测试用例，覆盖：
- Overlap window 计算
- All increasing/decreasing 场景
- Disputed 场景
- Regional summary
- Empty overlap 处理

### Step 5: HPC Probe Script

1. 编写 `scripts/hpc_probe_trends.py`
2. 本地测试小 bbox
3. HPC 验证 tropical bbox

### Step 6: 模块导出

更新 `src/WA/comparison/__init__.py` 导出新模块

---

## 已知风险与缓解

| 风险 | 缓解策略 |
|------|---------|
| 大区域 GWD30 时间序列内存占用高 | 使用 dask chunking，spatial_chunk_size=50 |
| 热带持续多云导致短时序 | min_observations=5 足够宽松，标记为 insufficient_observations |
| SWAMPS 2000 传感器切换影响趋势 | 在 TrendResult.attrs 中记录 sensor_shift_year |
| Seasonal 聚合对短时序（GIEMS-MC 14年）可能不足 | 允许 status='insufficient_observations'，不强制要求所有数据集都有 seasonal 结果 |

---

## 英文摘要 (English Summary)

Phase 4 implements per-pixel Mann-Kendall trend tests and Sen's Slope estimates for all dynamic wetland datasets (SWAMPS, GIEMS-MC, WAD2M, TOPMODEL, GWD30) at annual/seasonal/monthly aggregation levels. Cross-dataset trend agreement identifies pixels where all datasets agree on increase/decrease/stable versus where they disagree. Regional summaries are produced for Brazil, Indonesia, Southeast Asia, Africa, and the full tropical/subtropical domain.

**Key decisions:**
- **Pure scipy implementation** — no pymannkendall dependency, using scipy.stats.kendalltau + theilslopes
- **One-shot delivery** — all aggregation levels + year-over-year + cross-dataset agreement in single implementation
- **Vectorized with dask** — ported from legacy `Wetland_Assemble` mature implementation using xr.apply_ufunc

**Deliverables:**
- `src/WA/comparison/trends.py` — single-dataset trend analysis
- `src/WA/comparison/trend_agreement.py` — cross-dataset consistency
- 16 tests (9 + 7)
- HPC probe script
- Regional summary CSV + NetCDF trend rasters
