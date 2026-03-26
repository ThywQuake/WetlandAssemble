---
title: "refactor: Loader 架构重构 — 接受 ReferenceGrid 逐文件 reproject 避免 mosaic OOM"
type: refactor
status: active
date: 2026-03-26
---

# refactor: Loader 架构重构 — 接受 ReferenceGrid 逐文件 reproject 避免 mosaic OOM

## Overview

将所有 `DatasetLoader.load()` 改为可选接受 `reference_grid: xr.DataArray`，在逐文件加载阶段直接 reproject 到目标粗网格，再 merge 已对齐的结果。这消除了"先 mosaic 超大原生分辨率图 → 再 reproject"的 OOM 路径（主要影响 GWD30 30m MGRS 瓦片），同时为所有 loader 提供统一的"加载即对齐"能力。

## Problem Statement / Motivation

**GWD30 OOM 根因：**
`GWD30Loader.load()` → 对每个 30m 瓦片 `open_multiband_raster(reproject_to_wgs84=True)` → 在 WGS84 下保留 30m → `merge_rasters()` 将所有瓦片拼接。对印尼区域数百瓦片、92 波段/年，这会在内存中产出 10GB+ 的 mosaic。

**现有绕路方案：**
GWD30 已有 `load_rough_binary_surface()` 和 `load_fine_classification_grid()` 两个特化方法，接受 `reference_grid` 逐瓦片处理。但所有调用方必须对 GWD30 做 `if dataset_id == "gwd30"` 分支跳转，且 `loader_probe.py` 等通用路径仍走 OOM 的 `load()`。

**目标：**
1. `load(reference_grid=...)` 成为统一入口，消除调用方的 dataset-specific 分支
2. GWD30 `load()` 不再有 OOM 风险
3. 非 GWD30 loader 可选使用 reference_grid 进行 load-time 对齐
4. 下游 `harmonize.py` 检测到数据已对齐时跳过冗余 reproject

## Proposed Solution

### 核心设计

```
┌─────────────┐    reference_grid    ┌──────────────────┐
│   Caller     │───────────────────▶│  loader.load()    │
│ (probe/viz)  │    bbox, time_range │                  │
└─────────────┘                      │  per-file:       │
                                     │  1. open file     │
                                     │  2. clip to bbox  │
                                     │  3. reproject →   │
                                     │     reference_grid│
                                     │  4. accumulate    │
                                     │                  │
                                     │  merge aligned    │
                                     │  chunks → output  │
                                     └──────────────────┘
```

### API 签名变更

```python
# base.py
class DatasetLoader(ABC):
    @abstractmethod
    def load(
        self,
        bbox: BBox | None = None,
        time_range: TimeRange | None = None,
        *,
        reference_grid: xr.DataArray | None = None,  # NEW
    ) -> xr.Dataset:
        ...

    # REMOVED: load_tropic() — dead abstract method, never implemented
```

### reference_grid 约定

不新建 `ReferenceCoordinationDataset` 类——当前代码库已在 20+ 处使用 `reference_grid: xr.DataArray`，保持一致。新增一个验证函数：

```python
# base.py
def validate_reference_grid(grid: xr.DataArray) -> None:
    """Validate that an xr.DataArray can serve as a reference grid."""
    if grid.rio.crs is None:
        raise ValueError("reference_grid must have a CRS (via rio.write_crs)")
    spatial = {"lat", "lon"} | {"y", "x"}
    if not (spatial & set(grid.dims)):
        raise ValueError("reference_grid must have lat/lon or y/x dimensions")
```

### 各 Loader 行为矩阵

| Loader | 原 CRS | reference_grid=None | reference_grid 提供时 |
|--------|--------|---------------------|----------------------|
| **GWD30** | UTM/tile | 旧 mosaic 路径 (保留但标记 warning) | 逐瓦片 reproject → reference_grid, 增量 merge |
| **G2017** | EPSG:4326 | 原样返回 | `rio.reproject_match(reference_grid)` |
| **GLWD** | EPSG:4326 | 原样返回 | `rio.reproject_match(reference_grid)` |
| **Berkeley** | EPSG:4326 | 原样返回 | `rio.reproject_match(reference_grid)` |
| **SWAMPS** | EPSG:4326 | 原样返回 | `rio.reproject_match(reference_grid)` |
| **Topmodel** | EPSG:4326 | 原样返回 | `rio.reproject_match(reference_grid)` |
| **GenericNetCDF** | EPSG:4326 | 原样返回 | `rio.reproject_match(reference_grid)` |

### GWD30 特化方法策略

**保留** `load_rough_binary_surface()` 和 `load_fine_classification_grid()`。

理由：这两个方法执行的不是简单的"加载+reproject"，而是：
- `load_rough_binary_surface`: class → binary fraction 转换 + temporal aggregation + average resampling
- `load_fine_classification_grid`: per-class mode + fraction extraction + class-aware resampling

这些语义转换超出了 `load()` 的职责。`load(reference_grid=...)` 提供的是"原始数据在目标网格上的最近邻/平均重采样"，不做语义变换。

## Technical Approach

### Architecture

```
src/WA/loaders/
├── base.py              # ① load() 签名 + validate_reference_grid + 移除 load_tropic
├── _shared.py           # ② open_*_raster 加 reference_grid 参数 + reproject_to_grid()
├── gwd30.py             # ③ load() 使用逐瓦片 reproject 路径
├── g2017.py             # ④ load() 尾部加 reproject_match
├── glwd.py              # ⑤ 同上
├── berkeley.py          # ⑥ 同上
├── swamps.py            # ⑦ 同上
├── topmodel.py          # ⑧ 同上
├── netcdf_generic.py    # ⑨ 同上
└── registry.py          # 无变更

src/WA/comparison/
├── harmonize.py         # ⑩ _align_2d_surface 检测已对齐 → skip reproject
└── fine_grained.py      # ⑪ harmonize_fine_dataset 同上

src/WA/
├── loader_probe.py      # ⑫ probe_dataset 传入 reference_grid
├── rough_probe.py       # ⑬ 消除 GWD30 分支，统一使用 load() 或保留特化方法
├── visualization/
│   ├── comparison_panel.py  # ⑭ 消除 getattr dispatch
│   └── panel.py             # ⑮ 可能无变更

scripts/
├── hpc_probe_fine_grained.py  # ⑯ 消除重复的 _process_fine_tile
├── plot_phase3_panels.py      # ⑰ 简化 GWD30 分支
└── plot_comparison_panels.py  # ⑱ 简化

tests/
├── test_loaders/*.py       # ⑲ 每个 loader 加 reference_grid 测试
├── test_loader_probe.py    # ⑳ DummyLoader 更新签名
├── test_comparison/*.py    # ㉑ 对齐检测测试
└── test_visualization/*.py # ㉒ 更新 mock
```

### Implementation Phases

#### Phase A: 基础层变更 (`base.py` + `_shared.py`)

**任务：**
1. `base.py`:
   - `DatasetLoader.load()` 签名加 `*, reference_grid: xr.DataArray | None = None`
   - 移除 `load_tropic()` abstractmethod
   - 新增 `validate_reference_grid()`
   - `finalize_dataset()` 签名加 `reference_grid` 参数；当提供时，推导 bbox 从 reference_grid bounds

2. `_shared.py`:
   - `open_single_band_raster()` 加 `reference_grid` 参数：提供时用 `rio.reproject_match(reference_grid)` 替代 `rio.reproject("EPSG:4326")`
   - `open_multiband_raster()` 同上
   - 新增 `reproject_to_grid(data: xr.DataArray | xr.Dataset, reference_grid: xr.DataArray) -> xr.DataArray | xr.Dataset` 通用辅助函数

**验收标准：**
- [x] `load()` 签名改变，`reference_grid=None` 时行为不变
- [x] `load_tropic()` 从 ABC 移除
- [x] `validate_reference_grid` 对无 CRS / 无空间维度的网格抛异常
- [x] `reproject_to_grid()` 对 2D 和 3D+ DataArray 均可用

**文件清单：**
- `src/WA/loaders/base.py`
- `src/WA/loaders/_shared.py`

---

#### Phase B: GWD30 Loader 重写核心路径

**任务：**
1. `gwd30.py` `load()` 方法改写：
   - 当 `reference_grid is not None` 时：
     - 提取 `_reference_grid_spec(reference_grid)` → CRS/transform/width/height
     - 逐瓦片处理：用 `rasterio.warp.reproject()` 将每个瓦片的每个 band 重投影到 reference_grid
     - 使用 `Resampling.mode`（分类数据）或 `Resampling.average`（连续数据）
     - 增量累积到 `(n_bands, height, width)` 数组
     - 组装为 xr.Dataset，坐标从 reference_grid 继承
   - 当 `reference_grid is None` 时：保留旧路径但 emit `warnings.warn()` 提示 OOM 风险
   - 支持 `worker_count` 参数复用现有并行框架

2. `_reference_grid_spec()` 增加 `x`/`y` 维度名 fallback

**验收标准：**
- [x] `load(reference_grid=grid)` 对 1°×1° bbox 返回正确形状的 Dataset
- [x] `load(reference_grid=grid)` 内存峰值 < 2GB（对比旧路径 >10GB）
- [x] `load(reference_grid=None)` 行为不变（带 deprecation warning）
- [x] tqdm 进度条覆盖所有瓦片循环

**文件清单：**
- `src/WA/loaders/gwd30.py`

---

#### Phase C: 非 GWD30 Loader 适配

**任务：**
每个 loader 的 `load()` 方法：
1. 签名加 `*, reference_grid: xr.DataArray | None = None`
2. 在返回前，如果 `reference_grid is not None`，对数据变量调用 `reproject_to_grid()`
3. 对分类数据使用 `Resampling.nearest`；对连续数据使用 `Resampling.bilinear`

具体：
- `g2017.py` — 分类，nearest，单时间步
- `glwd.py` — 分类，nearest，单时间步
- `berkeley.py` — 连续（月均），bilinear，多时间步 → 逐时间步 reproject
- `swamps.py` — 连续（日），bilinear，多时间步 → 逐时间步 reproject
- `topmodel.py` — 连续（月均），bilinear，多维 → 逐 slice reproject
- `netcdf_generic.py` — 按 `is_classification` 元数据选择 resampling

**验收标准：**
- [x] 每个 loader `load(reference_grid=None)` 行为不变
- [x] 每个 loader `load(reference_grid=grid)` 返回数据与 grid 空间坐标一致
- [x] 分类 loader 使用 nearest，连续 loader 使用 bilinear

**文件清单：**
- `src/WA/loaders/g2017.py`
- `src/WA/loaders/glwd.py`
- `src/WA/loaders/berkeley.py`
- `src/WA/loaders/swamps.py`
- `src/WA/loaders/topmodel.py`
- `src/WA/loaders/netcdf_generic.py`

---

#### Phase D: 下游 harmonize 对齐检测

**任务：**
1. `harmonize.py` `_align_2d_surface()` / `_align_binary_fraction()`：
   - 检测输入数据是否已与 reference_grid 空间对齐（比较 lat/lon 坐标 + shape）
   - 如已对齐，跳过 `rio.reproject_match()`，直接返回
   - 添加 `logger.debug("data already aligned to reference grid, skipping reproject")`

2. `fine_grained.py` `harmonize_fine_dataset()` 同理

**验收标准：**
- [x] 已对齐数据不触发 reproject
- [x] 未对齐数据仍正常 reproject
- [x] 日志记录跳过行为

**文件清单：**
- `src/WA/comparison/harmonize.py`
- `src/WA/comparison/fine_grained.py`

---

#### Phase E: 调用方更新

**任务：**

1. `loader_probe.py` `probe_dataset()`:
   - 新增可选 `reference_grid` 参数
   - 传入 `loader.load(bbox, time_range, reference_grid=reference_grid)`
   - CLI 加 `--resolution` 参数，用于构建 comparison grid

2. `rough_probe.py` `probe_prepared_dataset()`:
   - 非 GWD30 数据集：从 `loader.load(bbox, time_range)` + `harmonize_binary_dataset()` 改为 `loader.load(bbox, time_range, reference_grid=reference_grid)`
   - GWD30 保留 `load_rough_binary_surface()` 调用（语义不同）
   - 消除部分 dataset-specific 分支

3. `visualization/comparison_panel.py` `load_native_wetland_surface()`:
   - 移除 `getattr(loader, "load_rough_binary_surface")` 分支
   - 统一使用 `loader.load(bbox, time_range, reference_grid=display_grid)`
   - 注意：此处需要保留原生分辨率选项（用于可视化），reference_grid 可选

4. `scripts/hpc_probe_fine_grained.py`:
   - 移除 `_load_gwd30_parallel()` 和 `_process_fine_tile()` 重复代码
   - 改用 `loader.load_fine_classification_grid()` 或 `loader.load(reference_grid=grid)`
   - G2017/GLWD 改用 `loader.load(bbox, reference_grid=grid)`

5. `scripts/plot_phase3_panels.py`:
   - 简化 GWD30 分支

6. `scripts/plot_comparison_panels.py`:
   - 同上

**验收标准：**
- [x] `loader_probe.py` 对 GWD30 不再 OOM
- [x] `rough_probe.py` GWD30 分支明确仅用于 binary 语义转换
- [x] `hpc_probe_fine_grained.py` 不再重复瓦片处理逻辑
- [x] 所有脚本 `--help` 无报错

**文件清单：**
- `src/WA/loader_probe.py`
- `src/WA/rough_probe.py`
- `src/WA/visualization/comparison_panel.py`
- `scripts/hpc_probe_fine_grained.py`
- `scripts/plot_phase3_panels.py`
- `scripts/plot_comparison_panels.py`（如存在）

---

#### Phase F: 测试全面更新

**任务：**

1. 每个 loader 测试新增 `test_load_with_reference_grid()`:
   - 创建小 reference_grid（`create_comparison_grid`）
   - 调用 `loader.load(bbox, reference_grid=grid)`
   - 验证返回 Dataset 空间坐标与 grid 一致
   - 验证返回数据非全 NaN

2. `test_loader_probe.py`:
   - `DummyLoader.load()` 更新签名
   - 新增 reference_grid 传递测试

3. `test_comparison/test_harmonize.py`:
   - 新增"已对齐输入跳过 reproject"测试

4. GWD30 专项测试:
   - `test_load_with_reference_grid_memory_efficient()` — 验证逐瓦片路径
   - `test_load_without_reference_grid_emits_warning()` — 验证 deprecation warning

**验收标准：**
- [ ] `pytest` 全部通过
- [ ] 新增测试覆盖 reference_grid 有/无两种路径
- [ ] ruff 无 lint 错误

**文件清单：**
- `tests/test_loaders/test_gwd30.py`
- `tests/test_loaders/test_g2017.py`
- `tests/test_loaders/test_glwd.py`
- `tests/test_loaders/test_berkeley.py`
- `tests/test_loaders/test_swamps.py`
- `tests/test_loaders/test_topmodel.py`
- `tests/test_loaders/test_netcdf_generic.py`
- `tests/test_loaders/conftest.py`（可能需要新 fixture）
- `tests/test_loader_probe.py`
- `tests/test_comparison/test_harmonize.py`
- `tests/test_comparison/test_fine_grained.py`

---

### Implementation Order & Dependencies

```
Phase A (base + _shared)
    │
    ├──▶ Phase B (GWD30 rewrite)  ─┐
    │                               ├──▶ Phase E (callers)  ──▶ Phase F (tests)
    └──▶ Phase C (other loaders) ──┘
              │
              └──▶ Phase D (harmonize alignment detection)
```

Phase A 是先决条件。B/C/D 可并行开发（不同文件）。E 依赖 B+C 完成。F 贯穿所有阶段但最终集成验证在最后。

## Alternative Approaches Considered

### 方案 A：新建 `load_aligned()` 方法（不修改 `load()` 签名）
- **优点**：向后兼容，不影响现有代码
- **缺点**：API 表面膨胀，调用方仍需分支；不解决 `loader_probe.py` 通用调用的 OOM 问题

### 方案 B：构造函数注入 reference_grid
- **优点**：`load()` 签名不变
- **缺点**：同一 loader 实例不能为不同 bbox 使用不同 reference_grid；不适合 probe 场景中循环多个 bbox

### 方案 C：只修 GWD30，其他 loader 不动
- **优点**：改动最小
- **缺点**：不消除调用方的 dataset-specific 分支；下游 harmonize 仍需做冗余 reproject

**选定方案**：修改 `load()` 签名（当前提案），因为它提供统一 API 并彻底消除 OOM 路径。

## System-Wide Impact

### Interaction Graph

1. `loader.load(reference_grid=grid)` → 内部调用 `_shared.reproject_to_grid()` 或 `rasterio.warp.reproject()`
2. → 返回已对齐 `xr.Dataset` → `harmonize_binary_dataset()` 检测已对齐 → 跳过 reproject
3. → `compute_rough_binary_metrics()` 直接比较
4. 可视化路径：`load_native_wetland_surface()` 传入 `reference_grid=display_grid`

### Error Propagation

- `validate_reference_grid()` 在 `load()` 入口验证，抛 `ValueError`
- 瓦片级错误（文件损坏、CRS 缺失）→ `logger.warning()` + 跳过该瓦片（与现有行为一致）
- 并行处理 `BrokenProcessPool` → fallback to serial（与现有行为一致）

### State Lifecycle Risks

- **无持久化状态变更**——所有变更在内存中
- **部分失败**：如果某些瓦片 reproject 失败，结果中对应区域为 NaN。与现有行为一致，无新风险

### API Surface Parity

| 接口 | 需更新 | 说明 |
|------|--------|------|
| `DatasetLoader.load()` | 是 | 新增 keyword-only `reference_grid` |
| `GWD30Loader.load_rough_binary_surface()` | 否 | 保留，语义不同 |
| `GWD30Loader.load_fine_classification_grid()` | 否 | 保留，语义不同 |
| `DatasetLoader.load_tropic()` | 删除 | Dead code |
| `probe_dataset()` | 是 | 传透 reference_grid |
| CLI scripts | 是 | 可选 `--resolution` 参数 |

### Integration Test Scenarios

1. **GWD30 + reference_grid → rough_probe 全流程**：
   `loader.load(bbox, time_range, reference_grid=grid)` → `harmonize_binary_dataset()` → `compute_rough_binary_metrics()` → 验证结果与旧路径（load_rough_binary_surface）一致

2. **G2017 + reference_grid → 0.25° 对齐**：
   `loader.load(bbox, reference_grid=grid_025)` → 验证输出 shape 与 grid 一致，分类值正确

3. **reference_grid=None 向后兼容**：
   所有 loader `load(bbox)` 结果与重构前完全一致

4. **harmonize 跳过检测**：
   传入已对齐数据 → `_align_binary_fraction()` 不调用 `rio.reproject_match()`

5. **GWD30 大 bbox + reference_grid 内存测试**：
   5°×5° 热带 bbox，验证峰值内存 < 2GB

## Acceptance Criteria

### Functional Requirements

- [ ] `DatasetLoader.load()` 接受可选 `reference_grid: xr.DataArray | None`
- [ ] GWD30 `load(reference_grid=grid)` 逐瓦片 reproject，不 OOM
- [ ] 非 GWD30 loader `load(reference_grid=grid)` 返回对齐数据
- [ ] `reference_grid=None` 时所有 loader 行为不变
- [x] `load_tropic()` 从 ABC 移除
- [ ] harmonize 检测已对齐数据跳过 reproject
- [ ] 所有调用方传透 reference_grid

### Non-Functional Requirements

- [ ] GWD30 `load(reference_grid=grid)` 对 5°×5° bbox 峰值内存 < 2GB
- [ ] 非 GWD30 loader 性能无退化（reference_grid=None 路径不增加开销）
- [ ] tqdm 进度条覆盖所有 GWD30 循环

### Quality Gates

- [ ] `pytest` 全部通过，含新增 reference_grid 测试
- [ ] `ruff check` 无错误
- [ ] `mypy` 类型检查通过

## Dependencies & Prerequisites

- 当前分支 `feat/phase3-fine-grained-entropy-s2` 的未提交修改需先提交或 stash
- 建议新建分支 `refactor/loader-reference-grid-alignment`
- 无外部依赖变更（rioxarray、rasterio 已在 deps 中）

## Risk Analysis & Mitigation

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| GWD30 逐瓦片 reproject + mode resampling 结果与旧路径数值不一致 | 中 | 中 | 对小 bbox 对比新旧路径输出 |
| 非 GWD30 loader reproject_match 引入微小浮点差异 | 高 | 低 | 预期行为，不影响分析 |
| harmonize 对齐检测误判（坐标微小浮点偏差） | 中 | 中 | 使用 `np.allclose(rtol=1e-6)` 而非严格相等 |
| 并行 worker_count 设置导致 HPC 内存超限 | 低 | 高 | 默认 worker_count=1，文档说明 |
| `load_tropic()` 移除破坏未知调用方 | 低 | 中 | grep 确认无调用方 |

## Success Metrics

1. `loader_probe.py` 对 GWD30 5°×5° bbox 不再 OOM
2. `rough_probe.py` 和 `hpc_probe_fine_grained.py` 中 `if dataset_id == "gwd30"` 分支减少 ≥ 50%
3. 所有现有 160+ 测试继续通过
4. 新增 ≥ 14 个测试（每 loader 2 个 + harmonize 2 个）

## Future Considerations

- Phase 4 趋势分析可直接使用 `load(reference_grid=trend_grid)` 加载对齐数据，不需要单独的对齐步骤
- 后续可考虑 lazy loading（Dask backend）与 reference_grid 结合，实现超大范围的分块处理
- 如果需要支持非 WGS84 的 reference_grid（例如 Lambert 投影），`reproject_to_grid()` 已具备此能力

---

# 中文版摘要

## 概述

重构所有 `DatasetLoader.load()` 方法，接受可选的 `reference_grid` 参数。当提供 reference_grid 时，加载器在逐文件加载阶段直接将数据重投影到目标粗网格，然后合并已对齐的结果。这消除了 GWD30 "先拼接超大 30m mosaic 再重投影"导致的内存溢出问题。

## 关键变更

1. **`load()` 签名**：新增 `reference_grid: xr.DataArray | None = None`
2. **GWD30**：`reference_grid` 提供时走逐瓦片 reproject 路径（类似现有 `load_rough_binary_surface` 的内存高效模式）
3. **其他 loader**：`reference_grid` 提供时在返回前做 `reproject_match`
4. **harmonize.py**：检测已对齐数据，跳过冗余重投影
5. **调用方**：统一传入 `reference_grid`，消除 dataset-specific 分支
6. **清理**：移除从未实现的 `load_tropic()` abstractmethod

## 实施顺序

Phase A（基础层）→ Phase B（GWD30）/ Phase C（其他 loader）/ Phase D（harmonize）→ Phase E（调用方）→ Phase F（测试）

## 风险

- GWD30 新旧路径数值对比需验证
- harmonize 对齐检测需用 `np.allclose` 容忍浮点误差
- 默认 `worker_count=1` 以保守使用内存
