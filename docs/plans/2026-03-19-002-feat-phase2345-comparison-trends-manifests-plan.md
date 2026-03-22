---
title: "feat: Phase 2-5 Comparison, Trends, and Manifest Pipeline"
type: feat
status: active
date: 2026-03-19
supersedes_phase2_section_of: docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md
---

# Phase 2-5 对比分析、趋势分析与审查清单流水线

## Overview

本计划整合 Phase 2 剩余工作和 Phase 3/4/5 全部工作，形成一份可执行的实施路线。

**当前状态：**

| Phase | 状态 | 说明 |
|-------|------|------|
| Phase 1 | DONE | 8 loaders + HPC probe, 3 bug fixes verified |
| Phase 2 | PARTIAL | harmonize + rough_binary + focus_areas + gee_client + modis_reference + rough_probe 已完成 |
| Phase 3 | NOT STARTED | fine_grained + hotspots + s2_reference |
| Phase 4 | NOT STARTED | trends + trend_agreement |
| Phase 5 | NOT STARTED | manifests + export_policy + docs + results population |

**总体目标：**
从 8 个湿地数据集的原始加载，经过粗尺度二值对比、细尺度分类对比、时间趋势分析，到最终可审查的影像清单和文档。

---

## Phase 2 剩余工作（收尾）

### 2A. HPC 端到端验证

`scripts/hpc_probe_rough_binary.py` 已就绪。需要在 HPC 上跑一次完整的 rough binary pipeline：

```bash
uv run python scripts/hpc_probe_rough_binary.py \
  --region tropical \
  --target-time 2019-07-01 \
  --json-out temp/rough_probe_full.json
```

**验收标准：**
- [ ] 至少 4 个数据集 status=`participating`
- [ ] pairwise metrics 全部有效（kappa, IoU, F1 非 NaN）
- [ ] disagreement_score 分布合理（max < 1.0, mean < 0.5）
- [ ] focus AOIs 覆盖至少 3 个区域

### 2B. Export.image.* fallback（推迟到 Phase 5）

当前 `download_limit_exceeded` 只做了状态识别。真正的 async export 路径涉及 GEE task polling，复杂度较高。

**决策：推迟到 Phase 5 的 `validation/export_policy.py` 统一实现。** 原因：
1. 粗尺度 AOI (2° x 2°, 500m MODIS) 大部分不会触发 32MB 限制
2. 细尺度 S2 (10m) 更可能触发，到 Phase 3/5 一并处理更合理

### 2C. Manifest 持久化（推迟到 Phase 5）

同理，manifest 持久化在 Phase 5 统一实现。当前内存对象足够 probe 阶段使用。

---

## Phase 3: 细尺度分类对比 + 熵热点 + Sentinel-2

### 3.1 文件清单

```
src/WA/comparison/fine_grained.py    # 新建
src/WA/comparison/hotspots.py        # 新建
src/WA/validation/s2_reference.py    # 新建
tests/test_comparison/test_fine_grained.py  # 新建
tests/test_comparison/test_hotspots.py      # 新建
tests/test_validation/test_s2_reference.py  # 新建
scripts/hpc_probe_fine_grained.py    # 新建 (HPC 诊断)
```

### 3.2 fine_grained.py — 分类调和与对比

**参与数据集：** 仅分类数据集
- G2017 (`g2017`)
- GLWD v2 (`glwd_v2`)
- GWD30 (`gwd30`)

**4-class 调和方案**（来自规范计划 lines 323-366）：

| 调和类 | G2017 原始值 | GLWD v2 原始值 | GWD30 原始值 |
|--------|-------------|---------------|-------------|
| `non_wetland` | 0 (nodata) | 0 | 0 |
| `open_water` | 10 | 1-7 | 1-6, 14 |
| `wetland` | 20-100 | 8-32 | 8-13 |
| `artificial_wetland` | — | 33 | 7 |

**8-class 细粒度方案**（迁移自前代 `Wetland_Assemble/src/wetland_analysis/data/mappings.py`）：

| 调和类 | ID | G2017 | GLWD v2 | GWD30 |
|--------|----|-------|---------|-------|
| Non-wetland | 0 | 0 | 0 | 0 |
| Open Water | 1 | 10 | 1-7,30 | 1-6,14 |
| Mangrove | 2 | 20 | 28 | 12 |
| Peatland | 3 | — | 22-27 | — |
| Forested Swamp | 4 | 30 | 8,10,12,14,16,18,20 | 9 |
| Marsh | 5 | 40,50,80,90,100 | 9,11,13,15,17,19,21,33 | 8 |
| Floodplain | 6 | 60,70 | — | 10 |
| Coastal Wetland | 7 | — | 29,31,32 | 11,13 |

**关键函数：**

```python
# fine_grained.py

FINE_CLASS_MAPS: dict[str, dict[int, int]]  # 4-class mapping
FINE8_CLASS_MAPS: dict[str, dict[int, int]]  # 8-class mapping

def harmonize_fine_collection(
    datasets: Mapping[str, xr.Dataset],
    reference_grid: xr.DataArray,
    *,
    class_scheme: Literal["4class", "8class"] = "4class",
) -> dict[str, xr.DataArray]:
    """Harmonize classification datasets to shared class vocabulary + grid."""

def compute_class_agreement(
    harmonized: Mapping[str, xr.DataArray],
) -> xr.Dataset:
    """Per-cell class-agreement metrics across participating datasets."""
    # 返回: majority_class, agreement_count, class_distribution
```

**对齐策略：**
- 使用 `Resampling.mode`（分类数据用众数重采样）
- 参考网格复用 `harmonize.create_comparison_grid()`
- GWD30 有 time 维（4-day composites），取比较窗口内的 mode 作为"代表分类"

### 3.3 hotspots.py — Shannon 熵 + 热点提取

**计算公式：**

4-class 归一化 Shannon 熵：
```
H = -sum(p_k * log2(p_k)) / log2(K)
```
其中 K=4（4-class 方案下），p_k 是该类在参与数据集中的出现频率。

**参考实现：** `Wetland_Assemble/src/wetland_analysis/analysis/uncertainty.py:12-49`

**热点提取流程：**
1. 计算每个 grid cell 的 normalized Shannon entropy
2. 取熵分布上尾（默认 top 95th percentile）
3. 对连续/近邻高熵 cell 做空间聚类（`scipy.ndimage.label` 或等效）
4. 过滤最小面积（默认 >= 4 个 cell，即 1° x 1° at 0.25° resolution）
5. 去重（复用 `focus_areas._is_far_enough()`，默认最小间距 3°）

```python
# hotspots.py

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

def compute_shannon_entropy(
    harmonized: Mapping[str, xr.DataArray],
    *,
    num_classes: int = 4,
) -> xr.DataArray:
    """Per-cell normalized Shannon entropy across classification datasets."""

def extract_hotspots(
    entropy: xr.DataArray,
    harmonized: Mapping[str, xr.DataArray],
    *,
    percentile_threshold: float = 95.0,
    min_cluster_cells: int = 4,
    min_distance_deg: float = 3.0,
    top_n: int = 10,
    region_bboxes: Mapping[str, BBox] | None = None,
) -> list[EntropyHotspot]:
    """Extract stratified, deduplicated hotspot AOIs from entropy surface."""
```

### 3.4 s2_reference.py — Sentinel-2 云掩膜复合

**GEE 集合：**
- 影像: `COPERNICUS/S2_SR_HARMONIZED`
- 云评分: `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`
- 掩膜规则: `cs_cdf >= 0.60`
- 合成方式: 中位数复合

**时间可用性：** `S2_AVAILABLE_FROM = pd.Timestamp("2017-03-28")`

**终态与 MODIS 一致：**
- `downloaded`, `cached`, `unsupported_time_window`, `gee_auth_failed`, `empty_collection`, `download_failed`, `download_limit_exceeded`

```python
# s2_reference.py

S2_COLLECTION_ID = "COPERNICUS/S2_SR_HARMONIZED"
S2_CLOUD_SCORE_ID = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
S2_AVAILABLE_FROM = pd.Timestamp("2017-03-28")
S2_CLOUD_THRESHOLD = 0.60
S2_RGB_BANDS = ("B4", "B3", "B2")

@dataclass(frozen=True)
class S2ReferenceArtifact:
    hotspot_id: str
    region_slug: str
    target_time: pd.Timestamp
    window_start: pd.Timestamp
    window_end: pd.Timestamp
    quicklook_path: Path
    chip_path: Path
    status: str
    collection_id: str = S2_COLLECTION_ID
    cloud_threshold: float = S2_CLOUD_THRESHOLD
    message: str | None = None

def download_s2_reference(
    hotspot: EntropyHotspot,
    gee_client: EarthEngineClient,
    *,
    target_time: str | pd.Timestamp,
    window_days: int = 30,
    results_root: str | Path = "results",
    scale_meters: int = 10,
    skip_existing: bool = True,
) -> S2ReferenceArtifact:
    """Download cloud-masked Sentinel-2 composite for one hotspot AOI."""
```

**输出路径：**
```
results/fine_truth/{region_slug}/{window_slug}/{hotspot_id}_s2_rgb.jpg
results/fine_truth/{region_slug}/{window_slug}/{hotspot_id}_s2_chip.tif
```

### 3.5 Phase 3 验收标准

- [ ] `fine_grained.py`: G2017/GLWD/GWD30 调和到共享 4-class 和 8-class 词表
- [ ] `hotspots.py`: Shannon 熵计算 + 热点 AOI 提取，区域分层 + 去重
- [ ] `s2_reference.py`: 云掩膜 Sentinel-2 复合下载，6 种终态
- [ ] 每个热点 AOI 有：熵分数、分类不一致摘要、时间窗口、S2 参考芯片（或显式终态）
- [ ] 新增测试全部通过
- [ ] HPC probe 脚本 (`scripts/hpc_probe_fine_grained.py`) 可运行

---

## Phase 4: 趋势分析

### 4.1 文件清单

```
src/WA/comparison/trends.py          # 新建
src/WA/comparison/trend_agreement.py # 新建
tests/test_comparison/test_trends.py            # 新建
tests/test_comparison/test_trend_agreement.py   # 新建
scripts/hpc_probe_trends.py          # 新建 (HPC 诊断)
```

### 4.2 trends.py — 单数据集趋势

**参考实现：** `Wetland_Assemble/src/wetland_analysis/analysis/trend.py`

**参与数据集（动态时间序列）：**

| 数据集 | 时间范围 | 时间分辨率 | 趋势输入 |
|--------|---------|-----------|---------|
| SWAMPS | 1992-2020 | daily | binary wetland fraction |
| GIEMS-MC | 1993-2007 | monthly | inundation fraction |
| WAD2M | 2000-2020 | monthly | wetland fraction |
| TOPMODEL | ~1980-2020 | monthly | collapsed wetland fraction |
| GWD30 | 2013-2022 | 4-day (annual files) | classification-derived fraction |

**静态数据集 (G2017, GLWD v2, Berkeley-RWAWC) 不参与趋势分析。**

**聚合层级**（来自 `config/datasets.yaml:analysis.aggregation_levels`）：
- `annual`: 年均湿地面积/比例
- `seasonal`: 季节（DJF/MAM/JJA/SON）均值
- `monthly`: 月均值

**统计检验**（来自 `config/datasets.yaml:analysis.trend_tests`）：
- **Mann-Kendall**: 趋势显著性（p-value, z-score）
- **Sen's Slope**: 趋势幅度（slope, unit: fraction/year）

**置信水平：** 0.95（来自 `config/datasets.yaml:analysis.confidence_level`）

```python
# trends.py

@dataclass(frozen=True)
class TrendResult:
    dataset_id: str
    aggregation: str  # "annual" | "seasonal" | "monthly"
    time_range: tuple[str, str]
    observation_count: int
    sens_slope: xr.DataArray      # fraction/year
    p_value: xr.DataArray
    z_score: xr.DataArray
    significant: xr.DataArray     # bool mask at confidence_level
    trend_direction: xr.DataArray # +1/0/-1
    status: str  # "computed" | "insufficient_observations"

def compute_pixel_trends(
    harmonized_surface: xr.DataArray,
    *,
    aggregation: str = "annual",
    confidence_level: float = 0.95,
    min_observations: int = 5,
) -> TrendResult:
    """Per-pixel Mann-Kendall + Sen's Slope for one dataset."""

def compute_regional_summary(
    trend_result: TrendResult,
    region_bboxes: Mapping[str, BBox],
) -> pd.DataFrame:
    """Regional summary statistics for a trend result."""
```

**关键实现细节：**
- 使用 `xr.apply_ufunc` + Dask 并行化逐像素 MK+Sen's slope（参考前代 `mann_kendall_vectorized()`）
- 若 `pymannkendall` 可用，使用 Yue-Wang 修正预白化；否则用 `scipy.stats.kendalltau` fallback
- 观测数 < `min_observations` 的像素输出 `insufficient_observations` 终态
- 季节聚合按 DJF/MAM/JJA/SON 分组后分别计算趋势

**短期 vs 长期：**
- **短期 (year-over-year):** 相邻年份差值，不做统计检验，输出变化方向和幅度
- **长期 (multi-decadal):** MK + Sen's slope，输出 5 变量 Dataset: `sens_slope`, `p_value`, `z_score`, `significant`, `trend_direction`

### 4.3 trend_agreement.py — 跨数据集趋势一致性

```python
# trend_agreement.py

@dataclass(frozen=True)
class TrendAgreementResult:
    overlap_window: tuple[str, str]
    participant_ids: list[str]
    agreement_ratio: xr.DataArray      # 0-1, 趋势方向一致比例
    mean_slope: xr.DataArray           # 多数据集均值斜率
    slope_std: xr.DataArray            # 斜率标准差
    robust_increase: xr.DataArray      # bool: 所有数据集一致增加
    robust_decrease: xr.DataArray      # bool: 所有数据集一致减少
    robust_stable: xr.DataArray        # bool: 所有数据集一致稳定
    disputed: xr.DataArray             # bool: 数据集间方向不一致
    status: str

def compute_trend_agreement(
    trend_results: Mapping[str, TrendResult],
    *,
    overlap_strategy: str = "maximum_common",
) -> TrendAgreementResult:
    """Cross-dataset trend consistency on the maximum defensible overlap window."""
```

**重叠窗口策略：**
- `maximum_common`: 所有参与数据集共同覆盖的最大时间区间
- 若重叠 < `min_observations` 年，输出 `overlap_window_empty` 终态

**区域汇总：** 对 Brazil / Indonesia / Southeast Asia / Africa / full tropical-subtropical 分别输出 agreement ratio 和 predominant trend direction。

### 4.4 Phase 4 验收标准

- [ ] `trends.py`: 每个动态数据集在其支持时间窗口内产出 annual/seasonal 趋势
- [ ] Mann-Kendall + Sen's Slope 输出完整（5 变量 Dataset）
- [ ] 短期 year-over-year 变化摘要
- [ ] `trend_agreement.py`: 跨数据集趋势一致性图（robust increase/decrease/stable/disputed）
- [ ] 区域汇总（4 区域 + 全域）
- [ ] 新增测试全部通过
- [ ] `insufficient_observations` 正确标记短时序像素

### 4.5 依赖说明

Phase 4 需要新增依赖（在 `pyproject.toml` 中）：
- `scipy` — `stats.kendalltau`, `stats.theilslopes`
- `pymannkendall` (optional) — Yue-Wang 预白化 MK

---

## Phase 5: 审查清单、导出策略与文档

### 5.1 文件清单

```
src/WA/validation/manifests.py       # 新建
src/WA/validation/export_policy.py   # 新建
docs/gee-truth-protocol.md           # 新建
docs/trend-analysis-protocol.md      # 新建
results/                             # 目录结构初始化
```

### 5.2 manifests.py — 清单持久化

```python
# manifests.py

@dataclass
class ManifestRow:
    run_id: str
    aoi_id: str
    aoi_type: str              # "rough" | "fine"
    region_slug: str
    data_source: str           # "MODIS/061/MOD09A1" | "COPERNICUS/S2_SR_HARMONIZED"
    target_time: pd.Timestamp
    window_start: pd.Timestamp
    window_end: pd.Timestamp
    cloud_threshold: float | None
    quicklook_path: str
    chip_path: str
    status: str
    message: str | None = None

def save_manifest(
    rows: list[ManifestRow],
    output_path: Path,
    *,
    format: str = "parquet",
) -> Path:
    """Persist manifest to parquet or CSV."""

def load_manifest(path: Path) -> pd.DataFrame:
    """Load a persisted manifest."""
```

**输出路径：**
```
results/manifests/{run_id}_truth_manifest.parquet
```

### 5.3 export_policy.py — GEE 大 AOI 导出回退

```python
# export_policy.py

def should_use_export(bbox: BBox, scale_meters: int) -> bool:
    """Estimate whether synchronous download will exceed GEE limits."""

def submit_export_task(
    image: Any,  # ee.Image
    bbox: BBox,
    output_path: Path,
    *,
    scale_meters: int,
    gee_client: EarthEngineClient,
) -> str:
    """Submit an Export.image.toDrive or toCloudStorage task."""

def poll_export_task(task_id: str, *, timeout_seconds: int = 600) -> str:
    """Poll until task completes, returning terminal status."""
```

### 5.4 结果目录结构

```
results/
  rough_truth/{region_slug}/{window_slug}/
    {aoi_id}_modis_rgb.jpg
    {aoi_id}_modis_chip.tif
  fine_truth/{region_slug}/{window_slug}/
    {hotspot_id}_s2_rgb.jpg
    {hotspot_id}_s2_chip.tif
  trends/
    {dataset_id}_{aggregation}_trend.nc     # per-dataset trend rasters
    cross_dataset_agreement_{overlap_window}.nc
    regional_summaries.csv
  manifests/
    {run_id}_truth_manifest.parquet
  quicklooks/
    {region_slug}/{window_slug}/
      {aoi_id}_modis_rgb.jpg
```

### 5.5 文档

**`docs/gee-truth-protocol.md`:**
- 参考影像集合选择依据（MODIS MOD09A1, S2 SR Harmonized）
- 时间窗口策略（MODIS 8-day bucket, S2 ±15day median composite）
- 云掩膜规则（Cloud Score+ cs_cdf >= 0.60）
- 下载策略（synchronous → Export fallback）
- 审查指南（如何从 metric → manifest → 影像导航）

**`docs/trend-analysis-protocol.md`:**
- 重叠窗口策略
- 聚合逻辑（annual/seasonal/monthly）
- MK + Sen's slope 配置
- 传感器过渡和语义断裂的文档化
- 区域汇总解读指南

### 5.6 Phase 5 验收标准

- [ ] `manifests.py`: 从 ModisReferenceArtifact / S2ReferenceArtifact 到持久化 manifest row
- [ ] `export_policy.py`: 大 AOI 的 Export.image.* 异步回退
- [ ] 审查者可以从 metric 输出 → AOI manifest → 下载影像，无需手动簿记
- [ ] `results/` 目录结构就绪
- [ ] 文档写完（中英双语）

---

## 实施顺序与依赖

```
Phase 2 收尾 (2A: HPC 验证)
    ↓
Phase 3 (fine_grained → hotspots → s2_reference)
    ↓
Phase 4 (trends → trend_agreement)
    ↓
Phase 5 (manifests + export_policy + docs)
```

**Phase 3 和 Phase 4 无直接依赖，但建议先完成 Phase 3**，因为：
1. 细尺度对比产出的 class disagreement 信息对理解趋势差异有辅助价值
2. S2 下载逻辑可以为 Phase 5 的 export_policy 提供真实需求反馈

**每个 Phase 结束时都需要：**
- `pytest` + `ruff` + `mypy` 全部通过
- HPC probe 脚本验证
- stash 摘要更新

---

## 前代项目迁移策略

| 前代文件 | 迁移目标 | 迁移方式 |
|---------|---------|---------|
| `data/mappings.py` FINE_CONCORDANCE_MAP | `fine_grained.py` FINE8_CLASS_MAPS | 适配 WA 命名，验证映射完整性 |
| `analysis/uncertainty.py` calculate_shannon_entropy | `hotspots.py` compute_shannon_entropy | 从 binary 推广到 K-class |
| `analysis/hotspots.py` HotspotAnalyzer | `hotspots.py` extract_hotspots | 简化为函数式 API，加入区域分层 |
| `analysis/trend.py` mann_kendall_vectorized | `trends.py` compute_pixel_trends | 直接适配，加聚合层级 + 终态 |
| `analysis/temporal_dynamics.py` TemporalDynamicsAnalyzer | `trend_agreement.py` | 简化为 overlap-window agreement |

---

## Technical Considerations

### 新增依赖

```toml
# pyproject.toml — 新增
dependencies = [
    # Phase 4
    "scipy",
    # Phase 3/5 (already present: earthengine-api, requests)
]

[project.optional-dependencies]
trend = ["pymannkendall"]
```

### 性能考量

- **GWD30 趋势分析（Phase 4）：** 30m 数据做逐像素趋势计算量巨大。建议先在 comparison grid (0.25°) 上的 aggregated fraction 上做趋势，而非原始 30m。
- **S2 下载（Phase 3）：** 10m 分辨率的 hotspot chip 容易触发 GEE 32MB 限制。需要 export_policy fallback 或限制 AOI 大小。
- **Shannon 熵（Phase 3）：** 计算量轻（3 个数据集、4 个类），主要瓶颈在 GWD30 的 mode resampling。

### 错误传播设计

所有终态枚举在各 Phase 中保持一致：
- **数据层面：** `insufficient_observations`, `semantic_incompatibility`
- **GEE 层面：** `downloaded`, `cached`, `unsupported_time_window`, `gee_auth_failed`, `empty_collection`, `download_failed`, `download_limit_exceeded`
- **趋势层面：** `computed`, `insufficient_observations`, `overlap_window_empty`

### 传感器过渡注意事项（Phase 4）

| 数据集 | 断裂点 | 影响 |
|--------|--------|------|
| SWAMPS | 2000 (F11→F13+QUIKSCAT) | 传感器变更可能引入偏差 |
| GIEMS-MC | 2007 结束 | 仅 14 年序列，长期趋势受限 |
| GWD30 | 2013 开始 | 仅 10 年序列，长期趋势受限 |

趋势分析需在 metadata 中标注 `sensor_shift_year`，在文档中说明断裂点对趋势解读的限制。

---

## Acceptance Criteria (Overall)

### Functional Requirements

- [ ] 8 个数据集全部可通过 loader → harmonization → comparison 流水线
- [ ] 粗尺度二值对比产出 pairwise metrics + disagreement surface + focus AOIs + MODIS artifacts
- [ ] 细尺度分类对比产出 class agreement + Shannon entropy + hotspot AOIs + S2 artifacts
- [ ] 时间趋势产出 per-dataset MK+Sen's slope + cross-dataset agreement + 区域汇总
- [ ] 所有 AOI/下载操作有显式终态，无静默跳过

### Non-Functional Requirements

- [ ] `pytest` + `ruff` + `mypy` 全部通过
- [ ] HPC probe 脚本可成功运行
- [ ] 审查者可从 metric → manifest → 影像完成端到端导航

### Quality Gates

- [ ] 每个 Phase 完成后 stash 摘要
- [ ] 中英双语文档
- [ ] config/ 未修改

---

## Sources & References

### 当前项目

- 规范计划: `docs/plans/2026-03-18-001-feat-wetland-loaders-gee-truth-plan.md`
- Phase 1 修复计划: `docs/plans/2026-03-19-001-fix-phase1-loader-hpc-validation-findings-plan.md`
- Phase 2 stash: `docs/stashes/2026-03-19-003-phase2-rough-binary-modis-foundation.md`
- Rough probe stash: `docs/stashes/2026-03-19-004-hpc-rough-binary-probe-script.md`
- 二值调和: `src/WA/comparison/harmonize.py`
- 粗尺度对比: `src/WA/comparison/rough_binary.py`
- Focus AOI: `src/WA/comparison/focus_areas.py`
- GEE client: `src/WA/validation/gee_client.py`
- MODIS 下载: `src/WA/validation/modis_reference.py`
- Config: `config/datasets.yaml`, `config/gee_config.yaml`

### 前代项目 (`/Users/mac/Code/Wetland_Assemble/`)

- 分类映射: `src/wetland_analysis/data/mappings.py`
- Shannon 熵: `src/wetland_analysis/analysis/uncertainty.py:12-49`
- 热点分析: `src/wetland_analysis/analysis/hotspots.py`
- Mann-Kendall 趋势: `src/wetland_analysis/analysis/trend.py`
- 时间动力学: `src/wetland_analysis/analysis/temporal_dynamics.py`
- 空间对齐: `src/wetland_analysis/utils/alignment.py`
