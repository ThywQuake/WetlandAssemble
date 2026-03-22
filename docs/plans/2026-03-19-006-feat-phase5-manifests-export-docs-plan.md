---
title: "feat: Phase 5 Review Manifests, Export Policy, and Documentation"
type: feat
status: active
date: 2026-03-19
parent: docs/plans/2026-03-19-002-feat-phase2345-comparison-trends-manifests-plan.md
---

# Phase 5 审查清单、导出策略与文档

## Overview

Phase 5 是整个流水线的收尾阶段，将前四个阶段的所有输出连接成一个可审查、可追溯的完整工件体系。核心任务：持久化清单（manifest）、实现 GEE 大 AOI 导出回退、填充 results/ 目录、编写协议文档。

## 文件清单

### 新建

| 文件 | 说明 |
|------|------|
| `src/WA/validation/manifests.py` | 清单持久化 |
| `src/WA/validation/export_policy.py` | GEE Export.image.* 异步回退 |
| `tests/test_validation/test_manifests.py` | 清单测试 |
| `tests/test_validation/test_export_policy.py` | 导出策略测试 |
| `docs/gee-truth-protocol.md` | GEE 参考影像协议 |
| `docs/trend-analysis-protocol.md` | 趋势分析协议 |

---

## Task 5.1: manifests.py — 清单持久化

### 数据模型

```python
@dataclass
class ManifestRow:
    """One row per AOI download job."""
    run_id: str
    aoi_id: str
    aoi_type: str               # "rough" | "fine"
    region_slug: str
    data_source: str            # e.g. "MODIS/061/MOD09A1", "COPERNICUS/S2_SR_HARMONIZED"
    target_time: pd.Timestamp
    window_start: pd.Timestamp
    window_end: pd.Timestamp
    cloud_threshold: float | None
    quicklook_path: str
    chip_path: str
    status: str                 # terminal status
    download_mode: str          # "synchronous" | "export"
    message: str | None = None
    created_at: pd.Timestamp = field(default_factory=pd.Timestamp.now)
```

### 核心函数

```python
def from_modis_artifact(
    artifact: ModisReferenceArtifact,
    *,
    run_id: str,
) -> ManifestRow:
    """Convert a ModisReferenceArtifact to a ManifestRow."""

def from_s2_artifact(
    artifact: S2ReferenceArtifact,
    *,
    run_id: str,
) -> ManifestRow:
    """Convert a S2ReferenceArtifact to a ManifestRow."""

def save_manifest(
    rows: list[ManifestRow],
    output_path: Path,
    *,
    fmt: str = "parquet",
) -> Path:
    """Persist manifest to parquet or CSV.

    Parquet preferred for typed columns;
    CSV as fallback if pyarrow not available.
    """

def load_manifest(path: Path) -> pd.DataFrame:
    """Load a persisted manifest."""

def generate_run_id() -> str:
    """Deterministic run ID from timestamp + git short hash.

    Format: YYYYMMDD_HHMMSS_{git_short_hash}
    """
```

### 输出路径

```
results/manifests/{run_id}_truth_manifest.parquet
```

### 测试设计

```
test_manifests.py:
  - test_from_modis_artifact_preserves_fields
  - test_from_s2_artifact_preserves_fields
  - test_save_manifest_parquet_roundtrip
  - test_save_manifest_csv_roundtrip
  - test_generate_run_id_format
  - test_load_manifest_reads_saved_data
```

---

## Task 5.2: export_policy.py — GEE 大 AOI 导出

### 问题背景

GEE `getDownloadURL()` 有硬限制：32MB payload / 10000 grid dimensions。Sentinel-2 在 10m 分辨率下，1° x 1° AOI = ~11,000 x 11,000 pixels，会触发限制。

### 策略

```python
def should_use_export(
    bbox: BBox,
    scale_meters: int,
    *,
    max_dimension: int = 10000,
    max_payload_mb: float = 32.0,
    band_count: int = 3,
    bytes_per_pixel: int = 2,
) -> bool:
    """Estimate whether synchronous download will exceed GEE limits.

    Calculation:
    - width_pixels = (east - west) * 111320 * cos(center_lat) / scale_meters
    - height_pixels = (north - south) * 111320 / scale_meters
    - payload_mb = width * height * band_count * bytes_per_pixel / 1e6
    - Return True if either dimension > max_dimension or payload > max_payload_mb
    """

def submit_export_task(
    image: Any,  # ee.Image
    bbox: BBox,
    output_description: str,
    *,
    scale_meters: int,
    gee_client: EarthEngineClient,
    drive_folder: str = "WA_exports",
) -> str:
    """Submit an Export.image.toDrive task.

    Returns task_id for polling.
    Uses ee.batch.Export.image.toDrive() with:
    - crs: EPSG:4326
    - maxPixels: 1e9
    - fileFormat: GeoTIFF
    """

def poll_export_task(
    task_id: str,
    *,
    poll_interval_seconds: int = 30,
    timeout_seconds: int = 600,
) -> str:
    """Poll until task completes.

    Returns terminal status:
    - "COMPLETED"
    - "FAILED"
    - "CANCELLED"
    - "TIMED_OUT"
    """

def download_from_drive(
    drive_file_name: str,
    destination: Path,
) -> Path:
    """Download exported file from Google Drive to local path.

    Note: requires google-api-python-client or manual download.
    For HPC: user downloads from Drive and places in results/.
    """
```

### 集成点

`modis_reference.py` 和 `s2_reference.py` 在捕获 `download_limit_exceeded` 后，可选调用 `export_policy`：

```python
# In s2_reference.py download flow:
if should_use_export(hotspot.bbox, scale_meters):
    task_id = submit_export_task(image, hotspot.bbox, ...)
    export_status = poll_export_task(task_id)
    return S2ReferenceArtifact(..., status=export_status, download_mode="export")
```

### 测试设计

```
test_export_policy.py:
  - test_should_use_export_small_aoi_returns_false
  - test_should_use_export_large_aoi_returns_true
  - test_should_use_export_high_resolution_returns_true
  - test_submit_export_task_calls_ee_export  (fake ee)
  - test_poll_export_task_returns_completed
  - test_poll_export_task_returns_timed_out
```

---

## Task 5.3: Results 目录结构

初始化完整目录结构：

```
results/
  rough_truth/
    brazil/
    indonesia/
    southeast_asia/
    africa/
  fine_truth/
    brazil/
    indonesia/
    southeast_asia/
    africa/
  trends/
  manifests/
  quicklooks/
    brazil/
    indonesia/
    southeast_asia/
    africa/
```

添加 `.gitkeep` 文件保持目录结构。`results/` 本身应在 `.gitignore` 中（数据文件不入版本控制），但目录结构的 `.gitkeep` 可以提交。

---

## Task 5.4: 文档

### docs/gee-truth-protocol.md

**内容大纲：**

1. **参考影像选择依据**
   - MODIS MOD09A1: 500m 8-day surface reflectance, 粗尺度审查
   - Sentinel-2 SR Harmonized: 10m 多光谱, 细尺度审查
   - 选择理由与替代方案评估

2. **时间窗口策略**
   - MODIS: 8-day bucket 对齐到比较月份
   - Sentinel-2: ±15 天 median 复合
   - 可用性边界: MODIS ≥ 2000-02-18, S2 ≥ 2017-03-28

3. **云掩膜规则**
   - Cloud Score+ `cs_cdf >= 0.60`
   - 为何不用 QA60（DN 变化历史问题）

4. **下载策略**
   - 同步 `getDownloadURL()` 优先
   - `Export.image.toDrive` 回退条件
   - 大小估算公式

5. **终态定义**
   - 6 种终态及其触发条件

6. **审查指南**
   - 如何从 disagreement score → focus AOI → manifest → 影像
   - MODIS/S2 是参考影像而非地面实况

### docs/trend-analysis-protocol.md

**内容大纲：**

1. **重叠窗口策略**
   - maximum_common 方法
   - 数据集特定窗口 vs 交叉窗口

2. **聚合逻辑**
   - annual / seasonal (DJF/MAM/JJA/SON) / monthly
   - 从 daily/4-day 到月/年的 resample 策略

3. **统计检验**
   - Mann-Kendall: 假设、限制、预白化
   - Sen's Slope: 非参数线性趋势幅度
   - 置信水平 0.95

4. **传感器过渡**
   - SWAMPS 2000 传感器切换
   - GIEMS-MC 2007 终止
   - 各数据集覆盖年限表

5. **区域汇总解读**
   - 4 区域 + 全域
   - robust vs disputed 的含义

6. **已知限制**
   - 短时序数据集的趋势可靠性
   - 语义差异（fraction vs classification-derived）

---

## Acceptance Criteria

- [ ] `manifests.py`: ModisReferenceArtifact / S2ReferenceArtifact → ManifestRow → parquet/CSV
- [ ] `export_policy.py`: 大小估算 + Export.image.toDrive 提交 + polling
- [ ] 从 metric → manifest → 影像的端到端导航可行
- [ ] `results/` 目录结构就绪
- [ ] `docs/gee-truth-protocol.md` 完成（中英双语）
- [ ] `docs/trend-analysis-protocol.md` 完成（中英双语）
- [ ] `pytest` + `ruff` + `mypy` 通过

## Dependencies

- Phase 2/3/4 全部完成
- `pyarrow` (optional, for parquet; fallback to CSV)

---

# 英文摘要 (English Summary)

Phase 5 closes the pipeline by persisting manifest rows that link every AOI download job to its metrics, geometry, time window, and terminal status. The export policy module adds async `Export.image.toDrive` fallback for Sentinel-2 chips exceeding the synchronous 32MB limit. The results/ directory structure is initialized with region-specific subdirectories. Two protocol documents (GEE truth reference and trend analysis) provide reviewable methodology documentation. The goal is end-to-end traceability: from disagreement metric → AOI manifest → downloaded reference imagery, with no manual bookkeeping required.
