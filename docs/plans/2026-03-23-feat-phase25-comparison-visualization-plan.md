---
title: "feat: Phase 2.5 Comparison Visualization Panels"
type: feat
status: active
date: 2026-03-23
---

# Phase 2.5 对比可视化面板

## Overview

为每个 hotspot/focus area 生成一张综合对比面板图，将卫星参考影像、Shannon 熵（或 disagreement score）、平均湿地百分比、以及各数据集的湿地百分比分布整合在一张图中。每个数据集以各自原始分辨率展示（GWD30 除外，以 1km 呈现），确保跨分辨率的视觉对比。

## 图面规格

### 布局

```
┌──────────────┬──────────────┬──────────────┐  ┌──┐
│  Satellite   │  Entropy     │  Mean Wetland │  │  │ Entropy
│  (RGB)       │  (white→red) │  (white→blue) │  │  │ colorbar
├──────────────┼──────────────┼──────────────┤  │  │
│  g2017       │  giems_mc    │  glwd_v2     │  ├──┤
│  (0.05°)     │  (0.25°)     │  (~1km)      │  │  │ Wetland %
├──────────────┼──────────────┼──────────────┤  │  │ colorbar
│  gwd30       │  swamps      │  topmodel    │  │  │
│  (1km)       │  (25km)      │  (0.25°)     │  └──┘
├──────────────┼──────────────┼──────────────┤
│  wad2m       │  (empty)     │  (empty)     │
│  (0.25°)     │              │              │
└──────────────┴──────────────┴──────────────┘
```

- **3 列 × N 行**（N = 1 + ceil(参与数据集数 / 3)）
- 第一行固定：卫星影像 | 熵/不一致度 | 平均湿地百分比
- 后续行：每个数据集一个子图，按名称排序填充
- 最后一行可能有空位（隐藏 axes）

### 分辨率策略

| 数据集 | 原始分辨率 | 显示分辨率 |
|--------|-----------|-----------|
| g2017 | 0.05° (~5km) | 0.05° |
| giems_mc | 0.25° (~25km) | 0.25° |
| glwd_v2 | 30s (~1km) | ~1km |
| gwd30 | 30m | ~1km (降采样) |
| swamps | 25km | 25km |
| topmodel | 0.25° | 0.25° |
| wad2m | 0.25° (~25km) | 0.25° |

每个子图覆盖相同地理范围（hotspot bbox），分辨率不同带来细节差异。

### 样式要求

- [ ] **坐标标注**：仅最左列子图标注纬度，仅最底行子图标注经度
- [ ] **Colorbar**：子图无独立 colorbar；fig 右侧两个统一 colorbar
  - 上方：Shannon 熵，白→红 (`LinearSegmentedColormap`)，范围 [0, 1]
  - 下方：湿地百分比，白→蓝 (`LinearSegmentedColormap`)，范围 [0, 1]
- [ ] **Scale 一致**：所有湿地百分比子图使用相同 vmin=0, vmax=1
- [ ] **子图尺寸**：所有子图物理尺寸一致（`gridspec` 等宽等高）
- [ ] **标题**：`"{year} / {region_label} ({hotspot_id})"`，不含经纬范围
- [ ] **子图标题**：各子图显示数据集名称 + 分辨率，如 `"G2017 (0.05°)"`
- [ ] **卫星影像**：用 `imshow` 显示 RGB quicklook（MODIS 或 S2）

## 文件清单

### 新建

| 文件 | 说明 |
|------|------|
| `src/WA/visualization/__init__.py` | 包初始化 |
| `src/WA/visualization/comparison_panel.py` | 核心绘图模块 |
| `scripts/plot_comparison_panels.py` | CLI 脚本（从 probe 结果生成图） |
| `tests/test_visualization/test_comparison_panel.py` | 绘图逻辑测试 |

### 新增依赖

`matplotlib` 已在 pyproject.toml 中（确认即可）。

---

## Task 1: `comparison_panel.py` — 核心绘图

### 数据准备函数

```python
def load_native_wetland_surface(
    dataset_id: str,
    ds_config: dict,
    bbox: BBox,
    *,
    target_time: str | pd.Timestamp | None = None,
    gwd30_resolution_m: int = 1000,
) -> xr.DataArray:
    """Load one dataset's binary wetland fraction at native resolution.

    For GWD30: resample from 30m to ~1km via Resampling.average.
    For others: load at native resolution, apply binary threshold.
    Returns float32 DataArray with values in [0, 1].
    """
```

### 主绘图函数

```python
def plot_comparison_panel(
    hotspot_bbox: BBox,
    satellite_image_path: Path | None,
    entropy_surface: xr.DataArray,
    mean_wetland_surface: xr.DataArray,
    dataset_surfaces: dict[str, xr.DataArray],
    dataset_labels: dict[str, str],
    *,
    year: int,
    region_label: str,
    hotspot_id: str,
    output_path: Path,
    dpi: int = 200,
    figsize_per_cell: tuple[float, float] = (4.0, 3.5),
) -> Path:
    """Generate comparison panel figure.

    Parameters
    ----------
    hotspot_bbox : geographic extent for all subplots
    satellite_image_path : path to RGB quicklook (MODIS/S2), None = skip
    entropy_surface : Shannon entropy or disagreement_score at comparison grid
    mean_wetland_surface : wetland_vote_fraction at comparison grid
    dataset_surfaces : {dataset_id: native-res wetland fraction DataArray}
    dataset_labels : {dataset_id: "G2017 (0.05°)"} display labels
    year : reference year for title
    region_label : region name for title
    hotspot_id : hotspot/focus-area ID for title
    output_path : where to save the PNG
    """
```

### 实现要点

```python
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.gridspec import GridSpec
import matplotlib.image as mpimg

# Colormaps
ENTROPY_CMAP = LinearSegmentedColormap.from_list("entropy", ["white", "red"])
WETLAND_CMAP = LinearSegmentedColormap.from_list("wetland", ["white", "blue"])

def plot_comparison_panel(...):
    n_datasets = len(dataset_surfaces)
    n_data_rows = math.ceil(n_datasets / 3)
    n_rows = 1 + n_data_rows
    n_cols = 3

    # GridSpec: main grid + colorbar column
    fig = plt.figure(figsize=(figsize_per_cell[0] * n_cols + 1.2,
                              figsize_per_cell[1] * n_rows))
    gs = GridSpec(n_rows, n_cols + 1, figure=fig,
                  width_ratios=[1, 1, 1, 0.08],
                  wspace=0.08, hspace=0.15)

    # --- Row 0: satellite | entropy | mean wetland ---
    ax_sat = fig.add_subplot(gs[0, 0])
    ax_ent = fig.add_subplot(gs[0, 1])
    ax_avg = fig.add_subplot(gs[0, 2])

    # Satellite: imshow RGB
    if satellite_image_path and satellite_image_path.exists():
        img = mpimg.imread(satellite_image_path)
        ax_sat.imshow(img, extent=[bbox W, E, S, N], aspect="equal")
    ax_sat.set_title("Satellite", fontsize=9)

    # Entropy: pcolormesh white→red
    entropy_surface.plot.pcolormesh(
        ax=ax_ent, cmap=ENTROPY_CMAP, vmin=0, vmax=1, add_colorbar=False)
    ax_ent.set_title("Shannon Entropy", fontsize=9)

    # Mean wetland: pcolormesh white→blue
    mean_wetland_surface.plot.pcolormesh(
        ax=ax_avg, cmap=WETLAND_CMAP, vmin=0, vmax=1, add_colorbar=False)
    ax_avg.set_title("Mean Wetland %", fontsize=9)

    # --- Rows 1+: individual datasets ---
    sorted_ids = sorted(dataset_surfaces)
    for idx, ds_id in enumerate(sorted_ids):
        row = 1 + idx // 3
        col = idx % 3
        ax = fig.add_subplot(gs[row, col])
        dataset_surfaces[ds_id].plot.pcolormesh(
            ax=ax, cmap=WETLAND_CMAP, vmin=0, vmax=1, add_colorbar=False)
        ax.set_title(dataset_labels.get(ds_id, ds_id), fontsize=9)

    # Hide empty cells in last row
    ...

    # --- Tick label control ---
    for ax in all_axes:
        is_leftmost = (col_index == 0)
        is_bottom = (row_index == n_rows - 1) or (no axes below)
        if not is_leftmost: ax.set_ylabel(""); ax.set_yticklabels([])
        if not is_bottom:   ax.set_xlabel(""); ax.set_xticklabels([])

    # --- Two colorbars on the right ---
    # Split the colorbar column into top and bottom
    cax_ent = fig.add_subplot(gs[:n_rows//2 + 1, -1])
    cax_wet = fig.add_subplot(gs[n_rows//2 + 1:, -1])
    fig.colorbar(entropy_mappable, cax=cax_ent, label="Shannon Entropy")
    fig.colorbar(wetland_mappable, cax=cax_wet, label="Wetland Fraction")

    # --- Title ---
    fig.suptitle(f"{year} / {region_label} ({hotspot_id})", fontsize=13)

    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return output_path
```

---

## Task 2: `scripts/plot_comparison_panels.py` — CLI

```python
"""Generate comparison panel figures for all hotspots / focus areas."""

# CLI args:
#   --phase3-root  results/phase3/fine/probe  (读取 fine_grained_probe.json)
#   --results-root results                    (MODIS/S2 影像所在根目录)
#   --output-dir   results/figures            (输出 PNG)
#   --year         2016                       (标题年份)
#   --region       "SE Asia"                  (标题区域名)
#   --entropy-source  "phase3" | "phase2"     (用 Shannon entropy 还是 disagreement_score)

# Flow:
# 1. 读取 probe manifest → 获取 hotspot 列表
# 2. 加载 config → 获取 dataset 信息
# 3. 对每个 hotspot:
#    a. load_native_wetland_surface() for each dataset
#    b. 加载 entropy 或 disagreement surface (从 probe 结果或重新计算)
#    c. 加载 satellite quicklook (MODIS/S2)
#    d. plot_comparison_panel() → 输出 PNG
# 4. 打印汇总
```

---

## Task 3: 测试

```
test_comparison_panel.py:
  - test_plot_comparison_panel_creates_png          # 合成数据生成图
  - test_plot_comparison_panel_correct_subplot_count # 行列数正确
  - test_entropy_cmap_white_to_red                  # colormap 验证
  - test_wetland_cmap_white_to_blue                 # colormap 验证
  - test_load_native_wetland_surface_respects_bbox   # 子集裁剪正确
  - test_gwd30_resampled_to_1km                     # GWD30 降采样逻辑
```

---

## Acceptance Criteria

- [ ] 每个 hotspot 生成一张 PNG 面板图
- [ ] 第一行：卫星影像 | 熵分布 | 平均湿地百分比
- [ ] 后续行：各数据集湿地百分比，原始分辨率（GWD30 1km）
- [ ] 仅最左列标注纬度，仅最底行标注经度
- [ ] 无子图 colorbar，fig 右侧两个统一 colorbar（白→红 / 白→蓝）
- [ ] 所有湿地百分比子图 scale 一致 [0, 1]
- [ ] 所有子图尺寸一致
- [ ] 标题格式：`"{year} / {region} ({hotspot_id})"`
- [ ] `pytest` + `ruff` 通过

## Dependencies

- `matplotlib`（确认已在 pyproject.toml）
- Phase 2 probe 结果（`comparison_grids.nc` 或 `participant_surfaces.nc`）
- Phase 3 probe 结果（`fine_grained_probe.json`）
- MODIS/S2 quicklook 影像（可选，无则跳过卫星面板）

---

# 英文摘要 (English Summary)

Phase 2.5 adds a visualization module that generates per-hotspot comparison panel figures. Each figure has 3 columns × N rows: row 1 shows satellite reference, Shannon entropy (white→red), and mean wetland fraction (white→blue); subsequent rows show each dataset's wetland fraction at native resolution (GWD30 at 1km). Only leftmost subplots show latitude, only bottom subplots show longitude. Two shared colorbars sit on the right margin. All wetland subplots share the same [0,1] scale. Title format: "year / region (hotspot_id)".
