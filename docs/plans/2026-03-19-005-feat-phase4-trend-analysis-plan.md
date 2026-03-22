---
title: "feat: Phase 4 Trend Analysis and Cross-Dataset Agreement"
type: feat
status: active
date: 2026-03-19
parent: docs/plans/2026-03-19-002-feat-phase2345-comparison-trends-manifests-plan.md
---

# Phase 4 趋势分析与跨数据集一致性

## Overview

Phase 4 对所有动态湿地数据集执行时间序列趋势分析，并量化数据集间趋势方向的一致性。使用 Mann-Kendall 显著性检验 + Sen's Slope 效应量，在 annual/seasonal/monthly 三个聚合层级上运行。

## 文件清单

### 新建

| 文件 | 说明 |
|------|------|
| `src/WA/comparison/trends.py` | 单数据集 MK + Sen's Slope 逐像素趋势 |
| `src/WA/comparison/trend_agreement.py` | 跨数据集趋势一致性 |
| `tests/test_comparison/test_trends.py` | 趋势分析测试 |
| `tests/test_comparison/test_trend_agreement.py` | 趋势一致性测试 |
| `scripts/hpc_probe_trends.py` | HPC 趋势诊断 |

### 新增依赖

```toml
# pyproject.toml
dependencies = [
    "scipy",  # stats.kendalltau, stats.theilslopes
]

[project.optional-dependencies]
trend = ["pymannkendall"]  # Yue-Wang 预白化
```

---

## 参与数据集

仅动态时间序列数据集参与趋势分析：

| 数据集 | 时间范围 | 原始时间分辨率 | 趋势输入变量 | 输入类型 |
|--------|---------|--------------|------------|---------|
| SWAMPS | 1992-2020 | daily | `wetland_fraction` | continuous fraction |
| GIEMS-MC | 1993-2007 | monthly | `inundation` | continuous fraction |
| WAD2M | 2000-2020 | monthly | `wetland_fraction` | continuous fraction |
| TOPMODEL | ~1980-2020 | monthly | collapsed `wetland_fraction` | continuous fraction |
| GWD30 | 2013-2022 | 4-day | classification → fraction | derived fraction |

**静态数据集 (G2017, GLWD v2) 和 Berkeley-RWAWC 不参与趋势分析。**

---

## Task 4.1: trends.py — 单数据集趋势

### 输入准备

趋势分析在 Phase 2 的 binary harmonized fraction 上运行：

1. 从 `harmonize.harmonize_binary_dataset()` 获取对齐到 0.25° 网格的 wetland fraction
2. 按聚合层级 resample：
   - `annual`: `.resample(time="YS").mean()`
   - `seasonal`: 按 DJF/MAM/JJA/SON 分组 `.groupby("time.season").mean()`
   - `monthly`: `.resample(time="MS").mean()`

### 统计检验

来自 `config/datasets.yaml:analysis`：
- **Mann-Kendall**: 趋势方向显著性
- **Sen's Slope**: 趋势幅度（fraction/year 或 fraction/season）
- **置信水平**: 0.95

### 核心函数

```python
# trends.py

@dataclass(frozen=True)
class TrendResult:
    dataset_id: str
    aggregation: str            # "annual" | "seasonal" | "monthly"
    time_range: tuple[str, str]
    observation_count: int
    sens_slope: xr.DataArray    # fraction per time unit
    p_value: xr.DataArray
    z_score: xr.DataArray
    significant: xr.DataArray   # bool mask (p < 1-confidence_level)
    trend_direction: xr.DataArray  # +1 (increasing), 0 (stable), -1 (decreasing)
    status: str  # "computed" | "insufficient_observations"

def compute_pixel_trends(
    harmonized_surface: xr.DataArray,
    *,
    dataset_id: str,
    aggregation: str = "annual",
    confidence_level: float = 0.95,
    min_observations: int = 5,
) -> TrendResult:
    """Per-pixel Mann-Kendall + Sen's Slope.

    Implementation:
    1. Aggregate time series to target level
    2. Drop pixels with < min_observations valid values
    3. For each pixel: MK test (z, p) + Theil-Sen slope
    4. Vectorize via xr.apply_ufunc with dask='parallelized'
    5. Return 5-variable TrendResult
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
    No statistical test — just raw differences.
    """

def compute_regional_summary(
    trend_result: TrendResult,
    region_bboxes: Mapping[str, BBox],
) -> pd.DataFrame:
    """Regional summary for 4 regions + full domain.

    Per region:
    - mean_slope, median_slope
    - fraction_significant
    - fraction_increasing, fraction_decreasing, fraction_stable
    - total_valid_pixels
    """
```

### Mann-Kendall 实现策略

参考前代 `Wetland_Assemble/src/wetland_analysis/analysis/trend.py`：

```python
def _pixel_mann_kendall(
    values: np.ndarray,
    alpha: float,
) -> tuple[float, float, float, float, float]:
    """Single pixel MK + Sen's slope.

    Returns: (sens_slope, p_value, z_score, significant, direction)

    Strategy:
    1. If pymannkendall available: use mk.yue_wang_modification_test()
       (prewhitened for monthly data with autocorrelation)
    2. Else: fallback to scipy.stats.kendalltau + theilslopes
    """
```

通过 `xr.apply_ufunc` 向量化：

```python
result = xr.apply_ufunc(
    _pixel_mann_kendall,
    aggregated_series,
    kwargs={"alpha": 1.0 - confidence_level},
    input_core_dims=[["time"]],
    output_core_dims=[[], [], [], [], []],
    vectorize=True,
    dask="parallelized",
    output_dtypes=[float, float, float, float, float],
)
```

### 终态

- `computed`: MK + Sen's slope 正常计算
- `insufficient_observations`: 有效时间步 < `min_observations`（整个数据集级别）

### 传感器过渡注意事项

| 数据集 | 断裂点 | 说明 |
|--------|--------|------|
| SWAMPS | 2000 | F11 → F13+QUIKSCAT 传感器切换 |
| GIEMS-MC | 2007 终止 | 仅 14 年序列 |
| GWD30 | 2013 开始 | 仅 10 年序列 |
| TOPMODEL | varies by forcing | ERA5-Land / GLDAS-Noahv2.1 起始年份晚 |

趋势结果的 attrs 中应包含 `sensor_shift_year`（如果适用），文档需说明断裂点对解读的限制。

### 测试设计

```
test_trends.py:
  - test_compute_pixel_trends_increasing_series
  - test_compute_pixel_trends_decreasing_series
  - test_compute_pixel_trends_stable_series
  - test_compute_pixel_trends_insufficient_observations
  - test_compute_year_over_year_change
  - test_compute_regional_summary_covers_all_regions
  - test_seasonal_aggregation_groups_correctly
  - test_fallback_mk_without_pymannkendall
```

---

## Task 4.2: trend_agreement.py — 跨数据集一致性

### 重叠窗口策略

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
```

### 核心函数

```python
@dataclass(frozen=True)
class TrendAgreementResult:
    overlap_window: tuple[str, str]
    participant_ids: list[str]
    agreement_ratio: xr.DataArray       # 0-1
    mean_slope: xr.DataArray
    slope_std: xr.DataArray
    robust_increase: xr.DataArray       # bool
    robust_decrease: xr.DataArray       # bool
    robust_stable: xr.DataArray         # bool
    disputed: xr.DataArray              # bool
    regional_summary: pd.DataFrame
    status: str  # "computed" | "overlap_window_empty"

def compute_trend_agreement(
    trend_results: Mapping[str, TrendResult],
    *,
    overlap_strategy: str = "maximum_common",
    min_overlap_years: int = 5,
    region_bboxes: Mapping[str, BBox] | None = None,
) -> TrendAgreementResult:
    """Cross-dataset trend consistency.

    Steps:
    1. Find overlap window
    2. Re-compute trends for each dataset within overlap window
    3. Stack trend_direction arrays along 'dataset' dim
    4. Agreement = fraction of datasets with same direction
    5. Robust = all datasets agree
    6. Disputed = any pair disagrees on direction
    7. Regional summary for 4 regions + full domain
    """
```

### 区域汇总

对 Brazil / Indonesia / Southeast Asia / Africa / full tropical-subtropical 分别输出：

```python
# Per region row in regional_summary DataFrame:
{
    "region": str,
    "total_valid_pixels": int,
    "fraction_robust_increase": float,
    "fraction_robust_decrease": float,
    "fraction_robust_stable": float,
    "fraction_disputed": float,
    "mean_agreement_ratio": float,
    "mean_slope_across_datasets": float,
}
```

### 测试设计

```
test_trend_agreement.py:
  - test_compute_overlap_window_common_range
  - test_compute_overlap_window_no_overlap
  - test_trend_agreement_all_increasing
  - test_trend_agreement_all_decreasing
  - test_trend_agreement_disputed
  - test_trend_agreement_regional_summary
  - test_overlap_window_empty_status
```

---

## 输出产物

```
results/trends/
  {dataset_id}_annual_trend.nc        # per-dataset 5-variable trend raster
  {dataset_id}_seasonal_trend.nc
  {dataset_id}_yoy_change.nc          # year-over-year change
  cross_dataset_agreement_{overlap}.nc
  regional_summaries.csv              # all regions x all aggregation levels
```

---

## Acceptance Criteria

- [ ] `trends.py`: 每个动态数据集产出 annual + seasonal 趋势（5 变量 Dataset）
- [ ] Mann-Kendall p-value 和 Sen's Slope 对合成数据正确（increasing/decreasing/stable）
- [ ] 短期 year-over-year 变化摘要
- [ ] `trend_agreement.py`: 跨数据集一致性图（robust increase/decrease/stable/disputed）
- [ ] 区域汇总覆盖 4 区域 + 全域
- [ ] `insufficient_observations` 正确标记短时序（< min_observations）
- [ ] `overlap_window_empty` 正确标记无重叠情况
- [ ] `pymannkendall` 不可用时 fallback 到 scipy 正常工作
- [ ] `pytest` + `ruff` + `mypy` 通过

---

# 英文摘要 (English Summary)

Phase 4 computes per-pixel Mann-Kendall trend tests and Sen's Slope estimates for all dynamic wetland datasets (SWAMPS, GIEMS-MC, WAD2M, TOPMODEL, GWD30) at annual/seasonal/monthly aggregation levels. Cross-dataset trend agreement identifies pixels where all datasets agree on increase/decrease/stable versus where they disagree. Regional summaries are produced for Brazil, Indonesia, Southeast Asia, Africa, and the full tropical/subtropical domain. Terminal states handle insufficient observations and empty overlap windows. Legacy implementation from `Wetland_Assemble/src/wetland_analysis/analysis/trend.py` provides the vectorized MK+Sen's slope foundation.
