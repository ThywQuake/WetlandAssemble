---
title: "feat: Phase 3.5 Classification Visualization Panels"
type: feat
status: active
date: 2026-03-23
supersedes: docs/plans/2026-03-23-feat-phase25-comparison-visualization-plan.md
---

# Phase 3.5 分类可视化面板

## Overview

为每个 Phase 3 hotspot 生成一张 2×3 分类对比面板图。上排展示卫星影像、Shannon 熵分布、多数据集投票分类；下排展示 GLWD / G2017 / GWD30 各自原生分辨率下的分类地图。用于直观展示三个分类数据集在高熵区域的分歧模式。

## 图面规格

### 布局

```
┌────────────────┬────────────────┬────────────────┐
│  S2 影像       │  Shannon 熵    │  投票分类       │
│  (RGB)         │  (白→红)       │  (categorical)  │
├────────────────┼────────────────┼────────────────┤
│  GLWD v2       │  G2017         │  GWD30          │
│  (~1km native) │  (0.05° native)│  (30m→500m)     │
└────────────────┴────────────────┴────────────────┘
                                                  ▕█▏ 熵 colorbar (白→红, 右侧)
━━━━━━━━ 分类图例 (patches, 底部) ━━━━━━━━
```

- **固定 2 行 × 3 列**
- 总标题：`"{region_label} ({hotspot_id})"`，仅体现区域和代号
- 仅最左列标注纬度 (row 0 col 0, row 1 col 0)
- 仅最底行标注经度 (row 1 col 0, row 1 col 1, row 1 col 2)
- **所有子图无独立 colorbar**
- fig 右侧：一个统一的 Shannon 熵 colorbar（白→红，[0, 1]）
- fig 底部：分类色块 legend（4class 方案的 4 个类别 patches）

### 分类方案

使用 Phase 3 定义的 **4class** 方案（`src/WA/comparison/fine_grained.py`）：

| class_id | 标签 | 建议颜色 |
|----------|------|----------|
| 0 | Non-wetland | `#d9d9d9` 浅灰 |
| 1 | Open Water | `#2166ac` 深蓝 |
| 2 | Wetland | `#1b7837` 深绿 |
| 3 | Artificial Wetland | `#f4a582` 橙粉 |

### 投票分类逻辑（Top-right 子图）

1. 将三个数据集 (GLWD / G2017 / GWD30) 聚合到统一的 **500m** 网格：
   - **GWD30** (30m)：对每个 500m cell，统计原生像元中各 4class 类别的面积比例（class-fraction resampling，类似 `hpc_probe_fine_grained.py` 的逻辑，但目标分辨率为 500m）
   - **GLWD v2** (~1km)：对每个 500m cell，因原生分辨率已粗于 500m，取最近邻或 mode → 100% 该类别
   - **G2017** (0.05°≈5km)：同上，每个 500m cell 继承所属 5km 格点类别 → 100% 该类别
2. 对每个 500m 格点，将三个数据集的 class fractions **逐类求和**（每个数据集贡献 1 票，以 fraction 形式分配）
3. 取 **argmax** → 投票分类结果
4. 可视化：用 4class categorical colormap 显示

### 下排三个子图

- 每个数据集在其 **原生分辨率** 下加载该 hotspot bbox 内的分类数据
- 应用 `FINE_4CLASS_MAPS` 映射到 4class 方案
- 用相同的 4class categorical colormap 显示
- GWD30 在下排以 500m 显示（不在 30m，因文件太大且视觉上不必要）

---

## 文件清单

### 新建

| 文件 | 说明 |
|------|------|
| `src/WA/visualization/__init__.py` | 包初始化 |
| `src/WA/visualization/panel.py` | 核心绘图模块 |
| `scripts/plot_phase3_panels.py` | CLI 脚本 |
| `tests/test_visualization/__init__.py` | 测试包初始化 |
| `tests/test_visualization/test_panel.py` | 绘图逻辑测试 |

### 依赖确认

`matplotlib` — 确认已在 `pyproject.toml`（若无需添加）。

---

## Task 1: `src/WA/visualization/panel.py`

### 1.1 分类颜色定义

```python
# panel.py
import numpy as np
from matplotlib.colors import ListedColormap, LinearSegmentedColormap
from matplotlib.patches import Patch

FINE_4CLASS_COLORS = {
    0: "#d9d9d9",  # Non-wetland
    1: "#2166ac",  # Open Water
    2: "#1b7837",  # Wetland
    3: "#f4a582",  # Artificial Wetland
}

FINE_4CLASS_LABELS = {
    0: "Non-wetland",
    1: "Open Water",
    2: "Wetland",
    3: "Artificial Wetland",
}

CLASS_CMAP = ListedColormap(
    [FINE_4CLASS_COLORS[i] for i in range(4)],
    name="wetland_4class",
)

ENTROPY_CMAP = LinearSegmentedColormap.from_list("entropy_wr", ["white", "red"])
```

### 1.2 投票分类计算

```python
def compute_vote_classification(
    datasets: dict[str, xr.Dataset],
    bbox: BBox,
    *,
    class_scheme: ClassScheme = "4class",
    vote_resolution_m: int = 500,
) -> xr.DataArray:
    """Compute majority-vote classification at ~500m grid.

    Steps:
      1. Create a 500m reference grid for the bbox
      2. For each dataset, harmonize to 4class and resample to 500m
         (class-fraction resampling for fine-res, nearest for coarse-res)
      3. Stack class fractions, sum across datasets, argmax → vote
    """
```

### 1.3 原生分辨率分类加载

```python
def load_native_classification(
    dataset_id: str,
    ds_config: dict,
    bbox: BBox,
    *,
    class_scheme: ClassScheme = "4class",
    gwd30_display_resolution_m: int = 500,
) -> xr.DataArray:
    """Load one dataset's classification at native resolution.

    - GLWD: ~1km (30 arcsec)
    - G2017: 0.05°
    - GWD30: aggregated to 500m via class-fraction resampling

    Returns int DataArray with values in {0, 1, 2, 3}.
    """
```

### 1.4 主绘图函数

```python
def plot_classification_panel(
    hotspot_id: str,
    region_label: str,
    bbox: BBox,
    *,
    satellite_image_path: Path | None,
    entropy_surface: xr.DataArray,
    vote_classification: xr.DataArray,
    native_classifications: dict[str, xr.DataArray],
    output_path: Path,
    dpi: int = 200,
    figsize: tuple[float, float] = (14.0, 9.0),
) -> Path:
    """Generate 2×3 classification comparison panel.

    Layout:
      [0,0] S2 RGB      [0,1] Shannon Entropy  [0,2] Vote Classification
      [1,0] GLWD v2     [1,1] G2017            [1,2] GWD30

    Colorbars/Legends:
      - Right: entropy colorbar (white→red, [0,1])
      - Bottom: categorical legend patches for 4class

    Axis labels:
      - Only [0,0] and [1,0] show latitude
      - Only [1,0], [1,1], [1,2] show longitude
      - All other axes: no labels

    Title: "{region_label} ({hotspot_id})"
    """
```

实现要点：

```python
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import matplotlib.image as mpimg

def plot_classification_panel(...):
    fig = plt.figure(figsize=figsize)

    # GridSpec: 2 rows × 3 cols + narrow colorbar column on right
    gs = GridSpec(
        2, 4, figure=fig,
        width_ratios=[1, 1, 1, 0.04],
        wspace=0.05, hspace=0.12,
    )

    axes = {}
    for r in range(2):
        for c in range(3):
            axes[(r, c)] = fig.add_subplot(gs[r, c])

    # --- [0,0] S2 影像 ---
    ax = axes[(0, 0)]
    if satellite_image_path and satellite_image_path.exists():
        img = mpimg.imread(str(satellite_image_path))
        ax.imshow(img, extent=[bbox[0], bbox[2], bbox[1], bbox[3]],
                  aspect="auto", origin="upper")
    else:
        ax.text(0.5, 0.5, "No S2 Image", transform=ax.transAxes,
                ha="center", va="center", fontsize=10, color="gray")
    ax.set_title("Sentinel-2", fontsize=10)

    # --- [0,1] Shannon 熵 ---
    ax = axes[(0, 1)]
    im_ent = entropy_surface.plot.pcolormesh(
        ax=ax, cmap=ENTROPY_CMAP, vmin=0, vmax=1,
        add_colorbar=False, add_labels=False,
    )
    ax.set_title("Shannon Entropy", fontsize=10)

    # --- [0,2] 投票分类 ---
    ax = axes[(0, 2)]
    vote_classification.plot.pcolormesh(
        ax=ax, cmap=CLASS_CMAP, vmin=-0.5, vmax=3.5, levels=5,
        add_colorbar=False, add_labels=False,
    )
    ax.set_title("Vote Classification", fontsize=10)

    # --- [1,0] GLWD, [1,1] G2017, [1,2] GWD30 ---
    bottom_order = ["glwd_v2", "g2017", "gwd30"]
    bottom_labels = {
        "glwd_v2": "GLWD v2 (~1km)",
        "g2017": "G2017 (0.05°)",
        "gwd30": "GWD30 (500m)",
    }
    for col, ds_id in enumerate(bottom_order):
        ax = axes[(1, col)]
        if ds_id in native_classifications:
            native_classifications[ds_id].plot.pcolormesh(
                ax=ax, cmap=CLASS_CMAP, vmin=-0.5, vmax=3.5, levels=5,
                add_colorbar=False, add_labels=False,
            )
        ax.set_title(bottom_labels.get(ds_id, ds_id), fontsize=10)

    # --- 坐标标注控制 ---
    for (r, c), ax in axes.items():
        ax.set_xlim(bbox[0], bbox[2])
        ax.set_ylim(bbox[1], bbox[3])
        # 仅最左列标注纬度
        if c != 0:
            ax.set_ylabel("")
            ax.set_yticklabels([])
        else:
            ax.set_ylabel("Lat", fontsize=8)
        # 仅最底行标注经度
        if r != 1:
            ax.set_xlabel("")
            ax.set_xticklabels([])
        else:
            ax.set_xlabel("Lon", fontsize=8)
        ax.tick_params(labelsize=7)

    # --- 右侧 entropy colorbar ---
    cax = fig.add_subplot(gs[:, 3])
    fig.colorbar(im_ent, cax=cax, label="Shannon Entropy")

    # --- 底部分类 legend ---
    legend_patches = [
        Patch(facecolor=FINE_4CLASS_COLORS[k], edgecolor="black",
              linewidth=0.5, label=FINE_4CLASS_LABELS[k])
        for k in sorted(FINE_4CLASS_LABELS)
    ]
    fig.legend(
        handles=legend_patches,
        loc="lower center",
        ncol=4,
        fontsize=9,
        frameon=False,
        bbox_to_anchor=(0.45, -0.02),
    )

    # --- 总标题 ---
    fig.suptitle(f"{region_label} ({hotspot_id})", fontsize=13, y=0.98)

    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return output_path
```

---

## Task 2: `scripts/plot_phase3_panels.py`

CLI 入口脚本。

```python
"""Generate Phase 3.5 classification comparison panels for all hotspots."""

# CLI args:
#   --phase3-root  results/phase3/fine/probe  (读取 fine_grained_probe.json)
#   --results-root results                    (S2 影像所在根目录)
#   --output-dir   results/figures/phase3     (输出 PNG)
#   --class-scheme 4class                     (分类方案)
#   --vote-resolution 500                     (投票分辨率, meters)

# Flow:
# 1. 读取 probe manifest → hotspot 列表 (含 bbox)
# 2. 加载 config/datasets.yaml
# 3. 对每个 hotspot:
#    a. 查找 S2 quicklook: results/fine_truth/{region}/{window}/*_s2_rgb.jpg
#    b. 加载三个分类数据集到 bbox 范围
#    c. compute_vote_classification() → 投票分类
#    d. compute_shannon_entropy() → 熵面
#    e. load_native_classification() × 3 → 各数据集原生分类
#    f. plot_classification_panel() → PNG
# 4. 打印汇总: N hotspots processed, output directory
```

### 关键实现细节

- S2 quicklook 发现逻辑：遍历 `results/fine_truth/{region_slug}/*/` 目录，匹配 `{hotspot_id}_s2_rgb.jpg`
- 如果某数据集在 bbox 范围内无数据，该子图显示 "No Data" 文字
- 进度条：使用 tqdm（本地）或 LogProgress（HPC）

---

## Task 3: 测试

```
tests/test_visualization/test_panel.py:

  test_plot_classification_panel_creates_png
    # 合成 entropy DataArray + 合成 classification DataArrays → 生成 PNG
    # 验证文件存在且大小 > 0

  test_classification_cmap_4_colors
    # CLASS_CMAP 有 4 个颜色，对应 4 个类别

  test_entropy_cmap_white_to_red
    # ENTROPY_CMAP(0.0) ≈ white, ENTROPY_CMAP(1.0) ≈ red

  test_vote_classification_unanimous
    # 三个数据集全部同一类 → vote 结果 = 该类

  test_vote_classification_majority_wins
    # 两个数据集类别A，一个类别B → vote 结果 = A

  test_native_classification_applies_4class_map
    # 原始值经过 FINE_4CLASS_MAPS 映射后在 {0,1,2,3} 范围内
```

---

## Acceptance Criteria

- [ ] 每个 hotspot 生成一张 2×3 PNG 面板图
- [ ] 上排：S2 影像 | Shannon 熵 | 投票分类
- [ ] 下排：GLWD | G2017 | GWD30 各自分辨率下的 4class 分类图
- [ ] 仅最左列标注纬度，仅最底行标注经度
- [ ] **无子图 colorbar**
- [ ] fig 右侧：统一的 Shannon 熵 colorbar（白→红，[0,1]）
- [ ] fig 底部：4class 分类 legend（色块 patches）
- [ ] 总标题格式：`"{region_label} ({hotspot_id})"`
- [ ] 投票分类逻辑正确：500m 网格 + class-fraction 聚合 + argmax
- [ ] `pytest` + `ruff` 通过
- [ ] 可在 HPC 上通过脚本批量生成

## Dependencies

- `matplotlib`
- Phase 3 probe 结果：`results/phase3/fine/probe/fine_grained_probe.json`
- S2 quicklook 影像：`results/fine_truth/{region}/{window}/*_s2_rgb.jpg`（可选）
- 三个分类数据集的原始文件（config/datasets.yaml 中配置的路径）

## Risks

- **GWD30 at 500m**：对于 1° bbox 区域，500m 网格约 200×200 cells。GWD30 30m 数据需要处理 ~4000×4000 原生像元 → 内存可控（~64MB per class binary mask）。
- **G2017 在 500m 网格上呈块状**：因原生 5km 分辨率，每个 5km 格点映射到 ~10×10 个 500m cells，视觉上方块明显。这是预期行为，体现了分辨率差异。
- **分类颜色需与论文一致**：当前颜色为建议值，可能需根据最终出版需求调整。

---

# English Summary

Phase 3.5 adds a visualization module that generates 2×3 classification comparison panels per hotspot. Top row: Sentinel-2 RGB, Shannon entropy (white→red), and vote classification (majority vote across GLWD/G2017/GWD30 at ~500m via class-fraction aggregation). Bottom row: each dataset's native-resolution 4-class map (GLWD ~1km, G2017 0.05°, GWD30 at 500m). Only leftmost subplots show latitude, only bottom subplots show longitude. No per-subplot colorbars. Right margin: unified entropy colorbar. Bottom: categorical legend patches for the 4 wetland classes. Title shows region + hotspot_id only.
