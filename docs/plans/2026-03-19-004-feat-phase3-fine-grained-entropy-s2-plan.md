---
title: "feat: Phase 3 Fine-Grained Comparison + Entropy Hotspots + Sentinel-2"
type: feat
status: active
date: 2026-03-19
parent: docs/plans/2026-03-19-002-feat-phase2345-comparison-trends-manifests-plan.md
---

# Phase 3 细尺度分类对比 + 熵热点 + Sentinel-2

## Overview

Phase 3 聚焦于分类数据集（G2017, GLWD v2, GWD30）的细粒度对比。将各数据集的原始分类映射到共享词表，计算 Shannon 熵以量化数据集间不一致性，提取高熵热点 AOI，并下载 Sentinel-2 云掩膜参考影像。

## 文件清单

### 新建

| 文件 | 说明 |
|------|------|
| `src/WA/comparison/fine_grained.py` | 分类调和 + 细尺度对比 |
| `src/WA/comparison/hotspots.py` | Shannon 熵 + 热点 AOI 提取 |
| `src/WA/validation/s2_reference.py` | Sentinel-2 云掩膜复合下载 |
| `tests/test_comparison/test_fine_grained.py` | 细尺度对比测试 |
| `tests/test_comparison/test_hotspots.py` | 热点提取测试 |
| `tests/test_validation/test_s2_reference.py` | S2 下载测试 |
| `scripts/hpc_probe_fine_grained.py` | HPC 细尺度诊断 |

### 依赖（已有）

| 文件 | 复用内容 |
|------|---------|
| `comparison/harmonize.py` | `create_comparison_grid()`, `_align_2d_surface()`, `_prepare_spatial_array()` |
| `comparison/focus_areas.py` | `DEFAULT_FOCUS_REGION_BBOXES`, `_is_far_enough()`, `_assign_region()` |
| `validation/gee_client.py` | `EarthEngineClient` |

---

## Task 3.1: fine_grained.py — 分类调和与对比

### 参与数据集

仅分类数据集参与（非 fraction/binary 的数据集排除）：

| 数据集 | 原始变量 | 是否有 time 维 |
|--------|---------|--------------|
| G2017 (`g2017`) | `wetland` or `wetland_nolake` | No (static) |
| GLWD v2 (`glwd_v2`) | `combined_classes` | No (static) |
| GWD30 (`gwd30`) | `wetland_class` | Yes (4-day, 92 bands/year) |

### 4-class 调和方案

来自规范计划 (lines 323-366)：

```python
FINE_4CLASS_MAPS: dict[str, dict[int, int]] = {
    "g2017": {
        0: 0,    # nodata → non_wetland
        10: 1,   # Open Water → open_water
        20: 2, 30: 2, 40: 2, 50: 2, 60: 2, 70: 2, 80: 2, 90: 2, 100: 2,
        # All wetland types → wetland
    },
    "glwd_v2": {
        0: 0,                                  # Dryland → non_wetland
        1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1,  # Water → open_water
        8: 2, 9: 2, 10: 2, 11: 2, 12: 2, 13: 2, 14: 2, 15: 2,
        16: 2, 17: 2, 18: 2, 19: 2, 20: 2, 21: 2, 22: 2, 23: 2,
        24: 2, 25: 2, 26: 2, 27: 2, 28: 2, 29: 2, 30: 2, 31: 2, 32: 2,
        # All wetland → wetland
        33: 3,  # Rice paddies → artificial_wetland
    },
    "gwd30": {
        0: 0,                                  # Non-wetland
        1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 14: 1,  # Water → open_water
        7: 3,                                  # Aquaculture/Salt pan → artificial_wetland
        8: 2, 9: 2, 10: 2, 11: 2, 12: 2, 13: 2,  # Wetland types → wetland
    },
}

FINE_4CLASS_LABELS = {
    0: "non_wetland",
    1: "open_water",
    2: "wetland",
    3: "artificial_wetland",
}
```

### 8-class 细粒度方案

迁移自前代 `Wetland_Assemble/src/wetland_analysis/data/mappings.py` 的 `FINE_CONCORDANCE_MAP`：

```python
FINE_8CLASS_MAPS: dict[str, dict[int, int]] = {
    "g2017": {
        0: 0,     # No Data → Non-wetland
        10: 1,    # Open Water → Open Water
        20: 2,    # Mangrove → Mangrove
        30: 4,    # Swamps → Forested Swamp
        40: 5, 50: 5, 80: 5, 90: 5, 100: 5,  # Fens/Marshes → Marsh
        60: 6, 70: 6,  # Floodplains → Floodplain
    },
    "glwd_v2": {
        0: 0,
        1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 30: 1,
        28: 2,                                    # Mangrove
        22: 3, 23: 3, 24: 3, 25: 3, 26: 3, 27: 3,  # Peatland
        8: 4, 10: 4, 12: 4, 14: 4, 16: 4, 18: 4, 20: 4,  # Forested Swamp
        9: 5, 11: 5, 13: 5, 15: 5, 17: 5, 19: 5, 21: 5, 33: 5,  # Marsh
        29: 7, 31: 7, 32: 7,                     # Coastal Wetland
    },
    "gwd30": {
        0: 0,
        1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 14: 1,
        12: 2,     # Coastal Swamp → Mangrove
        9: 4,      # Inland Swamp → Forested Swamp
        8: 5,      # Inland Marsh → Marsh
        10: 6,     # Floodplain → Floodplain
        11: 7, 13: 7,  # Coastal Marsh/Tidal Flat → Coastal Wetland
    },
}

FINE_8CLASS_LABELS = {
    0: "Non-wetland",
    1: "Open Water",
    2: "Mangrove",
    3: "Peatland",
    4: "Forested Swamp",
    5: "Marsh",
    6: "Floodplain",
    7: "Coastal Wetland",
}
```

### 核心函数设计

```python
# fine_grained.py

ClassScheme = Literal["4class", "8class"]
EXCLUDED_FINE_DATASET_IDS = frozenset({"berkeley_rwawc", "lstm_wetland"})
CLASSIFICATION_DATASET_IDS = frozenset({"g2017", "glwd_v2", "gwd30"})

def dataset_supports_fine_comparison(dataset_id: str) -> bool:
    return dataset_id in CLASSIFICATION_DATASET_IDS

def harmonize_fine_collection(
    datasets: Mapping[str, xr.Dataset],
    reference_grid: xr.DataArray,
    *,
    class_scheme: ClassScheme = "4class",
) -> dict[str, xr.DataArray]:
    """Harmonize classification datasets to shared vocabulary + grid.

    Returns dict mapping dataset_id -> DataArray with harmonized class IDs.
    Resampling uses mode (categorical data).
    GWD30: if time dim present, take temporal mode within comparison window.
    """

def harmonize_fine_dataset(
    dataset_id: str,
    dataset: xr.Dataset,
    *,
    reference_grid: xr.DataArray,
    class_scheme: ClassScheme = "4class",
) -> xr.DataArray:
    """Harmonize one classification dataset."""

def compute_class_agreement(
    harmonized: Mapping[str, xr.DataArray],
    *,
    num_classes: int,
) -> xr.Dataset:
    """Per-cell agreement metrics.

    Returns Dataset with:
    - majority_class: most common class at each cell
    - agreement_count: how many datasets agree on majority class
    - class_distribution: fraction of each class across datasets
    """
```

### GWD30 时间维处理

GWD30 有 92 个 4-day bands per year。细尺度对比需要一个"代表分类"：

1. 加载比较时间窗口内的 bands
2. 对 time 维取 mode（最频繁出现的类别）
3. 然后 remap + reproject 到共享网格

```python
def _temporal_mode(data: xr.DataArray) -> xr.DataArray:
    """Take per-pixel mode across time dimension."""
    from scipy.stats import mode as scipy_mode
    return xr.apply_ufunc(
        lambda x: scipy_mode(x, axis=0, nan_policy="omit").mode[0],
        data,
        input_core_dims=[["time"]],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[data.dtype],
    )
```

### 对齐策略

- **Resampling:** `Resampling.mode`（分类数据用众数，非 bilinear）
- **参考网格:** 复用 `harmonize.create_comparison_grid()` 的 0.25° 网格
- **CRS:** 所有 loader 已输出 WGS84，无需额外投影

### 测试设计

```
test_fine_grained.py:
  - test_fine_4class_maps_cover_all_known_values
  - test_fine_8class_maps_cover_all_known_values
  - test_harmonize_fine_dataset_remaps_g2017
  - test_harmonize_fine_dataset_remaps_glwd
  - test_harmonize_fine_dataset_remaps_gwd30
  - test_harmonize_fine_collection_aligns_to_shared_grid
  - test_compute_class_agreement_majority_and_count
  - test_dataset_supports_fine_comparison
```

---

## Task 3.2: hotspots.py — Shannon 熵 + 热点提取

### Shannon 熵

**公式（K-class 归一化）：**

```
H = -sum(p_k * log2(p_k)) / log2(K)
```

其中 `K` = 类别数（4-class 方案下 K=4），`p_k` = 该类在参与数据集中的出现频率。

**参考实现：** `Wetland_Assemble/src/wetland_analysis/analysis/uncertainty.py:12-49`（binary entropy，需推广到 K-class）

```python
# hotspots.py

def compute_shannon_entropy(
    harmonized: Mapping[str, xr.DataArray],
    *,
    num_classes: int = 4,
) -> xr.DataArray:
    """Per-cell normalized Shannon entropy across classification datasets.

    Steps:
    1. Stack harmonized arrays along 'dataset' dim
    2. For each class k in [0, num_classes):
       p_k = fraction of datasets with class == k
    3. H = -sum(p_k * log2(p_k)) / log2(num_classes)
    4. Handle log(0) safely with xr.where
    """
```

### 热点提取

```python
@dataclass(frozen=True)
class EntropyHotspot:
    hotspot_id: str
    region_slug: str
    bbox: BBox
    center_lon: float
    center_lat: float
    mean_entropy: float
    max_entropy: float
    cell_count: int
    class_disagreement_summary: dict[str, float]
    # class_disagreement_summary: {"wetland": 0.33, "open_water": 0.33, "non_wetland": 0.33}

def extract_hotspots(
    entropy: xr.DataArray,
    harmonized: Mapping[str, xr.DataArray],
    *,
    percentile_threshold: float = 95.0,
    min_cluster_cells: int = 4,
    min_distance_deg: float = 3.0,
    top_n: int = 10,
    top_n_per_region: int = 3,
    aoi_size_deg: float = 1.0,
    region_bboxes: Mapping[str, BBox] | None = None,
) -> list[EntropyHotspot]:
    """Extract stratified, deduplicated hotspot AOIs from entropy surface.

    Pipeline:
    1. Threshold: entropy >= percentile_threshold
    2. Cluster: scipy.ndimage.label on thresholded binary mask
    3. Filter: drop clusters with < min_cluster_cells cells
    4. Rank: by mean entropy within cluster, descending
    5. Stratify: region assignment via focus_areas._assign_region()
    6. Dedup: min_distance_deg between cluster centroids
    7. Build: EntropyHotspot with bbox buffered to aoi_size_deg
    8. Annotate: class_disagreement_summary from harmonized arrays
    """
```

### 测试设计

```
test_hotspots.py:
  - test_compute_shannon_entropy_uniform_distribution_gives_max
  - test_compute_shannon_entropy_perfect_agreement_gives_zero
  - test_compute_shannon_entropy_partial_agreement
  - test_extract_hotspots_finds_high_entropy_clusters
  - test_extract_hotspots_respects_min_cluster_cells
  - test_extract_hotspots_deduplicates_nearby
  - test_extract_hotspots_stratifies_by_region
  - test_class_disagreement_summary_content
```

---

## Task 3.3: s2_reference.py — Sentinel-2 参考影像

### GEE 配置

```python
S2_COLLECTION_ID = "COPERNICUS/S2_SR_HARMONIZED"
S2_CLOUD_SCORE_ID = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
S2_AVAILABLE_FROM = pd.Timestamp("2017-03-28")
S2_CLOUD_THRESHOLD = 0.60
S2_RGB_BANDS = ("B4", "B3", "B2")  # True color
S2_SCALE_METERS = 10
```

### 云掩膜复合流程

```python
def _build_cloud_masked_composite(
    ee: Any,
    geometry: Any,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> Any:
    """Build median composite with Cloud Score+ masking.

    Steps:
    1. Load S2_SR_HARMONIZED filtered by geometry + date
    2. Load CLOUD_SCORE_PLUS linked by system:index
    3. Join with ee.Join.saveFirst('cloud_score')
    4. Map: mask pixels where cs_cdf < S2_CLOUD_THRESHOLD
    5. Median composite over masked collection
    """
```

### 核心函数

```python
@dataclass(frozen=True)
class S2ReferenceArtifact:
    hotspot_id: str
    region_slug: str
    target_time: pd.Timestamp
    window_start: pd.Timestamp
    window_end: pd.Timestamp
    quicklook_path: Path
    chip_path: Path
    status: str  # 同 MODIS 的 6 种终态
    collection_id: str = S2_COLLECTION_ID
    cloud_threshold: float = S2_CLOUD_THRESHOLD
    download_mode: str = "synchronous"
    message: str | None = None

def download_s2_reference(
    hotspot: EntropyHotspot,
    gee_client: EarthEngineClient,
    *,
    target_time: str | pd.Timestamp,
    window_days: int = 30,
    results_root: str | Path = "results",
    scale_meters: int = S2_SCALE_METERS,
    skip_existing: bool = True,
) -> S2ReferenceArtifact:
    """Download cloud-masked S2 composite for one hotspot.

    Terminal states:
    - downloaded: chip + quicklook saved
    - cached: files already exist
    - unsupported_time_window: target < 2017-03-28
    - gee_auth_failed: EE init failed
    - empty_collection: no S2 scenes in window after cloud masking
    - download_failed: generic failure
    - download_limit_exceeded: > 32MB / 10000 dims
    """
```

### 输出路径

```
results/fine_truth/{region_slug}/{window_slug}/{hotspot_id}_s2_rgb.jpg
results/fine_truth/{region_slug}/{window_slug}/{hotspot_id}_s2_chip.tif
```

### 测试设计

```
test_s2_reference.py:
  - test_s2_unsupported_time_window_before_2017
  - test_s2_cached_skips_download
  - test_s2_gee_auth_failed_returns_terminal_state
  - test_s2_empty_collection_returns_terminal_state
  - test_s2_download_success_creates_artifacts
  - test_s2_cloud_masking_threshold_applied
```

（测试使用 fake `ee` module 模式，与 `test_modis_reference.py` 保持一致）

---

## Task 3.4: HPC probe 脚本

`scripts/hpc_probe_fine_grained.py`：

```bash
# 基础细尺度诊断
uv run python scripts/hpc_probe_fine_grained.py \
  --region tropical \
  --class-scheme 4class

# 带 S2 下载
uv run python scripts/hpc_probe_fine_grained.py \
  --region tropical \
  --download-s2 \
  --target-time 2019-07-01
```

---

## Acceptance Criteria

- [ ] `fine_grained.py`: G2017/GLWD/GWD30 调和到 4-class 和 8-class 词表
- [ ] 映射表覆盖所有已知原始值（测试验证）
- [ ] GWD30 时间维通过 mode 降维为代表分类
- [ ] `hotspots.py`: Shannon 熵正确计算（perfect agreement → 0, uniform → 1）
- [ ] 热点 AOI 提取：聚类 + 面积过滤 + 去重 + 区域分层
- [ ] `s2_reference.py`: Cloud Score+ 掩膜 + median 复合 + 6 种终态
- [ ] 每个热点 AOI 有：熵分数 + 分类不一致摘要 + 时间窗口 + S2 artifact or 终态
- [ ] `pytest` + `ruff` + `mypy` 通过
- [ ] HPC probe 可运行

## Dependencies

- Phase 2 完成（至少 HPC 验证通过）
- `scipy` 已在依赖中（用于 `ndimage.label` 聚类和 `mode` 时间降维）

---

# 英文摘要 (English Summary)

Phase 3 implements fine-grained classification comparison across G2017, GLWD v2, and GWD30 using shared 4-class and 8-class vocabularies. Shannon entropy identifies disagreement hotspots, which are clustered, ranked, and used to drive Sentinel-2 cloud-masked composite downloads via GEE. The 4-class mapping (non_wetland, open_water, wetland, artificial_wetland) comes from the canonical plan; the 8-class mapping is migrated from the legacy project's `FINE_CONCORDANCE_MAP`. GWD30's temporal dimension is collapsed via per-pixel mode before classification remapping.
