---
title: "feat: Phase 3 Fine-Grained Comparison + Entropy Hotspots + Sentinel-2 — Implementation Plan"
type: feat
status: completed
date: 2026-03-22
parent: docs/plans/2026-03-19-004-feat-phase3-fine-grained-entropy-s2-plan.md
origin: docs/plans/2026-03-19-004-feat-phase3-fine-grained-entropy-s2-plan.md
---

# Phase 3 细尺度分类对比 + 熵热点 + Sentinel-2 — 落实路径

## Overview

本文档是 Phase 3 的**可执行实施计划**，基于已有的 Phase 3 技术规范 (`docs/plans/2026-03-19-004`) 和 Phase 2 综合评审 (`docs/stashes/2026-03-22-003`) 制定。在进入 Phase 3 核心开发前，先解决 Phase 2 遗留的技术债务，避免新代码继承已知问题。

**分支策略：** 在当前 `feat/phase2-rough-binary-modis-truth` 上先完成 Phase 2 收尾修复，然后新建 `feat/phase3-fine-grained-entropy-s2` 分支开展 Phase 3。

---

## Problem Statement

Phase 2 完成了粗尺度二值对比流水线。但项目仍需回答：

1. G2017 / GLWD v2 / GWD30 在**细粒度分类层面**（非简单 wetland/non_wetland）一致性如何？
2. 哪些地理区域的分类**不一致性最高**（Shannon 熵热点）？
3. 这些不一致区域的**高分辨率光学影像**长什么样（Sentinel-2 参考）？

Phase 2 只能说"这里数据集对湿地有没有达成共识"，Phase 3 要说"这里数据集在**哪一类**湿地上分歧最大，而且 Sentinel-2 影像显示真实地表是什么"。

---

## Proposed Solution

分 4 个实施阶段：

| 阶段 | 名称 | 估计工作量 | 依赖 |
|------|------|-----------|------|
| **Phase 2.5** | 技术债务清理 | 1 个子会话 | 无 |
| **Step 3.1** | fine_grained.py — 分类调和 | 1 个子会话 | Phase 2.5 |
| **Step 3.2** | hotspots.py — Shannon 熵 + 热点提取 | 1 个子会话 | Step 3.1 |
| **Step 3.3** | s2_reference.py + batch + HPC probe | 1 个子会话 | Step 3.2 + Phase 2.5 |

---

## Phase 2.5: 技术债务清理（前置）

### 动机

Phase 2 评审发现 2 个 P0 bug 和 4 个 P1 问题。其中有 3 个会直接阻塞或污染 Phase 3：

1. **validation 包 5 个重复函数** — Phase 3 新增 `s2_reference.py` 将导致第三份拷贝，维护灾难
2. **`urlopen` 无 timeout** — S2 10m 分辨率下载比 MODIS 500m 慢得多，无 timeout 在 HPC 上更危险
3. **tqdm fallback crash** — Phase 3 batch 脚本会复用同一模式

### 任务清单

#### Task 2.5A: 提取 validation 共享工具模块

**新建：** `src/WA/validation/_download_utils.py`

从 `modis_reference.py` 和 `landsat_reference.py` 提取：

```python
# _download_utils.py

def download_file(url: str, destination: Path, *, timeout: int = 300) -> None:
    """Atomic file download with streaming and timeout."""

def collection_size(collection: Any) -> int:
    """Count images in EE collection."""

def format_date(timestamp: pd.Timestamp) -> str:
    """Format timestamp for EE date filter."""

def month_window(target_time: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Compute month-boundary window from target time."""

def classify_failure(exc: Exception) -> str:
    """Classify GEE download failure into terminal status."""

def output_paths(
    results_root: Path,
    subdirectory: str,
    region_slug: str,
    window_slug: str,
    prefix: str,
    *,
    quicklook_ext: str = ".jpg",
    chip_ext: str = ".tif",
) -> tuple[Path, Path]:
    """Generate standardized quicklook + chip output paths."""
```

关键改进：
- `download_file`: 添加 `timeout` 参数，改用 `shutil.copyfileobj` 流式写入
- 原 `modis_reference.py` 和 `landsat_reference.py` 改为 `from WA.validation._download_utils import ...`

**验收：** `pytest tests/test_validation/ -q` 通过且无行为变化

#### Task 2.5B: 修复 tqdm fallback

**修改：** `src/WA/modis_batch.py`

将 `_NoOpProgress` 增加 `set_postfix_str()` 和 `close()` 方法：

```python
class _NoOpProgress:
    def update(self, _count: int = 1) -> None:
        return None
    def set_postfix_str(self, s: str, refresh: bool = True) -> None:
        return None
    def close(self) -> None:
        return None
```

**可选优化：** 将 tqdm fallback 移到 `src/WA/utils/progress.py`，解除 `landsat_batch.py` 对 `modis_batch.py` 的反向依赖。

**验收：** 在没有 tqdm 的环境下（`monkeypatch` 移除 tqdm）运行 batch 测试不报 `AttributeError`

#### Task 2.5C: JSON 序列化一致性

**修改：** `src/WA/landsat_review_manifest.py`

在 `json.dumps(...)` 调用中添加 `sort_keys=True, allow_nan=False`。

#### Task 2.5D: 添加 scipy 依赖

**修改：** `pyproject.toml`

```toml
scipy>=1.13
```

Phase 3 需要：
- `scipy.ndimage.label()` — 热点聚类
- `scipy.stats.mode()` — GWD30 时间维众数降维

**验收：** `uv add scipy>=1.13 && uv run python -c "from scipy import ndimage, stats; print('ok')"`

---

## Step 3.1: fine_grained.py — 分类调和与对比

### 新建文件

| 文件 | 说明 |
|------|------|
| `src/WA/comparison/fine_grained.py` | 分类调和 + 细尺度对比 |
| `tests/test_comparison/test_fine_grained.py` | 对应测试 |

### 核心设计

#### 参与数据集

仅分类数据集参与（见 Phase 3 规范 Task 3.1）：

| 数据集 | 原始变量 | 时间维 |
|--------|---------|-------|
| G2017 | `wetland` / `wetland_nolake` | 静态 |
| GLWD v2 | `combined_classes` | 静态 |
| GWD30 | `wetland_class` | 4-day, 92 bands/year |

#### 映射表

- **4-class** (`FINE_4CLASS_MAPS`): non_wetland / open_water / wetland / artificial_wetland
- **8-class** (`FINE_8CLASS_MAPS`): Non-wetland / Open Water / Mangrove / Peatland / Forested Swamp / Marsh / Floodplain / Coastal Wetland

已验证：两套映射表与 legacy `Wetland_Assemble/src/wetland_analysis/data/mappings.py` 一致。

**已知不一致（可接受）：** GLWD v2 rice paddies (class 33) 在 4-class 中映射为 `artificial_wetland`(3)，在 8-class 中映射为 `Marsh`(5)。前者反映土地利用属性，后者反映生物群落归属，两种视角均合理。保持现状。

#### GWD30 时间维处理

GWD30 每年 92 个 4-day band，需先降维再映射：

```python
def _temporal_mode(data: xr.DataArray) -> xr.DataArray:
    """Per-pixel mode across time dimension for classification data."""
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

#### 对齐策略

- **Resampling:** `Resampling.mode`（分类数据必须用众数，非 bilinear）
- **参考网格:** 复用 `harmonize.create_comparison_grid()` 的 0.25° 网格
- 复用 `harmonize._align_2d_surface()` 但传入 `resampling=Resampling.mode`

#### 核心函数

```python
ClassScheme = Literal["4class", "8class"]
CLASSIFICATION_DATASET_IDS = frozenset({"g2017", "glwd_v2", "gwd30"})

def dataset_supports_fine_comparison(dataset_id: str) -> bool
def harmonize_fine_collection(datasets, reference_grid, *, class_scheme="4class") -> dict[str, xr.DataArray]
def harmonize_fine_dataset(dataset_id, dataset, *, reference_grid, class_scheme="4class") -> xr.DataArray
def compute_class_agreement(harmonized, *, num_classes) -> xr.Dataset
```

`compute_class_agreement` 返回：
- `majority_class`: 每个网格单元中最常见的分类
- `agreement_count`: 多少个数据集同意 majority class
- `class_distribution`: 每个类别在数据集间的出现频率

### 测试计划

```
test_fine_grained.py:
  - test_fine_4class_maps_cover_all_known_values      # 验证映射表完整性
  - test_fine_8class_maps_cover_all_known_values       # 同上
  - test_harmonize_fine_dataset_remaps_g2017           # G2017 分类重映射
  - test_harmonize_fine_dataset_remaps_glwd            # GLWD 分类重映射
  - test_harmonize_fine_dataset_remaps_gwd30           # GWD30 分类重映射
  - test_harmonize_fine_collection_aligns_to_shared_grid # 多数据集对齐
  - test_compute_class_agreement_majority_and_count     # 一致性指标
  - test_dataset_supports_fine_comparison               # 资格检查
  - test_gwd30_temporal_mode_reduction                  # GWD30 时间降维
```

### 验收标准

- [x] 4-class 和 8-class 映射表覆盖所有已知原始值
- [x] G2017 / GLWD / GWD30 分别正确重映射
- [x] GWD30 时间维通过 mode 降维为代表分类
- [x] 分类数据使用 `Resampling.mode` 对齐（非 bilinear）
- [x] `pytest tests/test_comparison/test_fine_grained.py -q` 通过
- [x] `ruff check src/WA/comparison/fine_grained.py` 通过

---

## Step 3.2: hotspots.py — Shannon 熵 + 热点提取

### 新建文件

| 文件 | 说明 |
|------|------|
| `src/WA/comparison/hotspots.py` | Shannon 熵 + 热点 AOI 提取 |
| `tests/test_comparison/test_hotspots.py` | 对应测试 |

### Shannon 熵

**K-class 归一化公式：**

```
H = -sum(p_k * log2(p_k)) / log2(K)
```

- K = 类别数（4-class 方案下 K=4）
- p_k = 该类在参与数据集中的出现频率
- H ∈ [0, 1]：0 = 完全一致，1 = 最大不一致（均匀分布）

**参考实现：** legacy `Wetland_Assemble/src/wetland_analysis/analysis/uncertainty.py` 的 `calculate_shannon_entropy()`（binary 版），需推广到 K-class。

```python
def compute_shannon_entropy(
    harmonized: Mapping[str, xr.DataArray],
    *,
    num_classes: int = 4,
) -> xr.DataArray:
    """Per-cell normalized Shannon entropy across classification datasets."""
```

### 热点提取流水线

```python
@dataclass(frozen=True)
class EntropyHotspot:
    hotspot_id: str           # "entropy-{YYYYMM}-{region}-{NNN}"
    region_slug: str
    bbox: BBox
    center_lon: float
    center_lat: float
    mean_entropy: float
    max_entropy: float
    cell_count: int
    class_disagreement_summary: dict[str, float]

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
```

**流水线步骤：**
1. **阈值化：** 取 entropy >= percentile_threshold 的网格单元
2. **聚类：** `scipy.ndimage.label()` 在阈值二值 mask 上识别连通区域
3. **过滤：** 丢弃 cell_count < min_cluster_cells 的簇
4. **排序：** 按簇内平均熵降序
5. **区域分层：** 复用 `focus_areas._assign_region()` + `DEFAULT_FOCUS_REGION_BBOXES`
6. **去重：** 复用 `focus_areas._is_far_enough()` + min_distance_deg
7. **构建 AOI：** 以簇质心为中心 buffer aoi_size_deg
8. **标注：** 从 harmonized 数组中提取 class_disagreement_summary

### 测试计划

```
test_hotspots.py:
  - test_compute_shannon_entropy_uniform_distribution_gives_max   # 均匀分布 → H=1
  - test_compute_shannon_entropy_perfect_agreement_gives_zero     # 完全一致 → H=0
  - test_compute_shannon_entropy_partial_agreement                # 部分一致
  - test_extract_hotspots_finds_high_entropy_clusters             # 端到端
  - test_extract_hotspots_respects_min_cluster_cells              # 面积过滤
  - test_extract_hotspots_deduplicates_nearby                     # 距离去重
  - test_extract_hotspots_stratifies_by_region                    # 区域分层
  - test_class_disagreement_summary_content                       # 注释内容
```

### 验收标准

- [x] Shannon 熵正确计算（perfect agreement → 0, uniform → 1）
- [x] 热点聚类正确使用 `scipy.ndimage.label()`
- [x] 热点 AOI 满足：面积过滤 + 去重 + 区域分层
- [x] `class_disagreement_summary` 包含各类别频率
- [x] `pytest tests/test_comparison/test_hotspots.py -q` 通过
- [x] `ruff check src/WA/comparison/hotspots.py` 通过

---

## Step 3.3: s2_reference.py + batch + HPC probe

### 新建文件

| 文件 | 说明 |
|------|------|
| `src/WA/validation/s2_reference.py` | Sentinel-2 Cloud Score+ 复合下载 |
| `tests/test_validation/test_s2_reference.py` | 对应测试 |
| `src/WA/s2_batch.py` | 批量 S2 下载（基于 hotspot CSV） |
| `tests/test_s2_batch.py` | 对应测试 |
| `scripts/hpc_probe_fine_grained.py` | HPC 细尺度诊断入口 |
| `scripts/run_phase3_s2_downloads.py` | S2 批量下载 CLI |

### Sentinel-2 GEE 配置

```python
S2_COLLECTION_ID = "COPERNICUS/S2_SR_HARMONIZED"
S2_CLOUD_SCORE_ID = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
S2_AVAILABLE_FROM = pd.Timestamp("2017-03-28")
S2_CLOUD_THRESHOLD = 0.60    # cs_cdf >= 0.60
S2_RGB_BANDS = ("B4", "B3", "B2")
S2_SCALE_METERS = 10
```

### 云掩膜复合流程

```python
def _build_cloud_masked_composite(ee, geometry, window_start, window_end):
    """
    1. Load S2_SR_HARMONIZED filtered by geometry + date
    2. Load CLOUD_SCORE_PLUS linked by system:index
    3. Join with ee.Join.saveFirst('cloud_score')
    4. Map: mask pixels where cs_cdf < S2_CLOUD_THRESHOLD
    5. Median composite over masked collection
    """
```

### S2ReferenceArtifact

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
    status: str               # 7 种终态（同 MODIS/Landsat 模式）
    collection_id: str = S2_COLLECTION_ID
    cloud_threshold: float = S2_CLOUD_THRESHOLD
    download_mode: str = "synchronous"
    message: str | None = None
```

**关键：** `s2_reference.py` 使用 Phase 2.5 提取的 `_download_utils.py` 共享工具，**不再重复** `_download_file` 等 5 个函数。

### 输出路径

```
results/fine_truth/{region_slug}/{window_slug}/{hotspot_id}_s2_rgb.jpg
results/fine_truth/{region_slug}/{window_slug}/{hotspot_id}_s2_chip.tif
```

### 测试计划

```
test_s2_reference.py:
  - test_s2_unsupported_time_window_before_2017
  - test_s2_cached_skips_download                       # Phase 2 缺失的测试场景
  - test_s2_gee_auth_failed_returns_terminal_state      # Phase 2 缺失
  - test_s2_empty_collection_returns_terminal_state      # Phase 2 缺失
  - test_s2_download_success_creates_artifacts
  - test_s2_cloud_masking_threshold_applied

test_s2_batch.py:
  - test_s2_batch_discovers_hotspot_files
  - test_s2_batch_download_creates_manifest
```

**测试改进：** 提取 `FakeEeModule` 到 `tests/test_validation/conftest.py` 共享，不再在每个测试文件中重复。

### 验收标准

- [x] Cloud Score+ 掩膜正确应用（cs_cdf >= 0.60）
- [x] 7 种终态全覆盖（包括 Phase 2 缺失的 `cached`、`empty_collection` 等）
- [x] `download_s2_reference` 使用 `_download_utils.download_file` 带 timeout
- [x] HPC probe 可运行
- [x] 每个热点 AOI 有：熵分数 + 分类摘要 + S2 artifact 或终态
- [x] `pytest tests/test_validation/test_s2_reference.py tests/test_s2_batch.py -q` 通过

---

## System-Wide Impact

### Interaction Graph

```
fine_grained.py
  └→ harmonize.create_comparison_grid()        # 共享参考网格
  └→ harmonize._align_2d_surface()             # 空间对齐（mode resampling）
  └→ loaders/gwd30.py load_dataset()           # GWD30 原始分类数据

hotspots.py
  └→ fine_grained.harmonize_fine_collection()  # 调和后的分类数组
  └→ focus_areas._assign_region()              # 区域分层
  └→ focus_areas._is_far_enough()              # 距离去重
  └→ scipy.ndimage.label()                     # 聚类

s2_reference.py
  └→ validation.gee_client.EarthEngineClient   # GEE 包装
  └→ validation._download_utils.*              # 共享下载工具
  └→ hotspots.EntropyHotspot                   # 输入 AOI
```

### State Lifecycle Risks

- **GWD30 temporal mode:** 如果比较窗口内所有 bands 均为 NaN，mode 返回 NaN → 该像元在调和后被视为 non_wetland(0)。这是正确的降级行为。
- **S2 下载中断：** 原子文件写入确保无半成品文件。`skip_existing=True` 保证可安全重跑。
- **熵 = 0 的区域：** 所有数据集完全一致 → 不会产生热点 → 无 S2 下载触发。这是期望行为。

### API Surface Parity

Phase 3 公共 API 应遵循 Phase 2 的模式：
- `harmonize_fine_collection` 对应 `harmonize_binary_collection`
- `compute_class_agreement` 对应 `compute_rough_binary_metrics`
- `extract_hotspots` 对应 `select_focus_areas`
- `download_s2_reference` 对应 `download_modis_reference`
- `S2ReferenceArtifact` 对应 `ModisReferenceArtifact`

---

## Dependencies & Prerequisites

| 依赖 | 状态 | 操作 |
|------|------|------|
| Phase 2 代码基线 | Done | 82 tests passing |
| `scipy>=1.13` | **需添加** | Phase 2.5 Task D |
| `_download_utils.py` 提取 | **需完成** | Phase 2.5 Task A |
| tqdm fallback 修复 | **需完成** | Phase 2.5 Task B |
| `comparison/__init__.py` 导出更新 | Step 3.1 时更新 | 添加 Phase 3 公共 API |
| `validation/__init__.py` 导出更新 | Step 3.3 时更新 | 添加 S2 API |

---

## Risk Analysis & Mitigation

| 风险 | 可能性 | 影响 | 缓解策略 |
|------|--------|------|---------|
| `scipy.stats.mode` 在大数据上慢 | 中 | GWD30 降维可能耗时 | 先在 Phase 3.1 本地测试性能；如不可接受，改用 `np.apply_along_axis` + `np.bincount` |
| S2 Cloud Score+ 在早期数据中不可用 | 低 | 2017-03 前无 S2 → 终态 `unsupported_time_window` | 已在设计中处理 |
| 热带地区 S2 持续多云 | 中 | `empty_collection` 终态 | 扩大融合窗口（默认 ±30 天），必要时可增至 ±60 天 |
| GLWD v2 分类在某些区域空白 | 低 | 参与数据集减少到 2 个 | 熵公式自适应 K=实际参与数据集数 |
| 8-class 方案中某些类别极少出现 | 中 | 熵值偏低，热点不明显 | 提供 4-class 和 8-class 双方案并行输出 |

---

## Sources & References

### Internal References

- **Phase 3 技术规范（origin）:** [docs/plans/2026-03-19-004-feat-phase3-fine-grained-entropy-s2-plan.md](docs/plans/2026-03-19-004-feat-phase3-fine-grained-entropy-s2-plan.md)
- **Phase 2 综合评审:** [docs/stashes/2026-03-22-003-phase2-comprehensive-review.md](docs/stashes/2026-03-22-003-phase2-comprehensive-review.md)
- **Canonical 5-phase 计划:** [docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md](docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md) (Phase 3 section: lines 170-199)
- **Legacy 映射参考:** `/Users/mac/Code/Wetland_Assemble/src/wetland_analysis/data/mappings.py`
- **Legacy 熵参考:** `/Users/mac/Code/Wetland_Assemble/src/wetland_analysis/analysis/uncertainty.py`

### GEE Documentation

- Sentinel-2 SR Harmonized: `COPERNICUS/S2_SR_HARMONIZED`
- Cloud Score+: `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`
- Cloud Score+ 使用指南: cs_cdf >= 0.60 threshold, saveFirst join pattern

---

# 英文摘要 (English Summary)

This is the executable implementation plan for Phase 3: Fine-Grained Comparison + Entropy Hotspots + Sentinel-2 Reference. It builds on the Phase 3 technical specification and the Phase 2 comprehensive review. The plan prescribes 4 stages: (1) Phase 2.5 — resolve P0/P1 technical debt (extract shared download utils, fix tqdm fallback, add scipy dependency), (2) Step 3.1 — implement fine_grained.py with 4-class and 8-class harmonization for G2017/GLWD/GWD30, (3) Step 3.2 — implement hotspots.py with K-class Shannon entropy and cluster-based hotspot extraction, (4) Step 3.3 — implement s2_reference.py with Cloud Score+ masking using shared download utilities. Mapping tables are verified against the legacy project. GWD30's temporal dimension is collapsed via per-pixel mode before classification remapping.
