# Phase 3 实现会话总结

**Date:** 2026-03-22
**Branch:** feat/phase3-fine-grained-entropy-s2
**前序:** Phase 2.5 技术债务修复（同一会话）

---

## 会话概览

本次会话完成了两大块工作：

1. **Phase 2.5 收尾**（从上一个 context 延续）：添加 scipy 依赖 → `pyproject.toml` + `uv.lock`
2. **Phase 3 全量实现**：fine_grained + hotspots + s2_reference + s2_batch + HPC 脚本

最终状态：**110/110 tests passing, ruff clean, 未提交**

---

## Phase 3 实现细节

### Step 3.1: fine_grained.py — 分类调和

- **核心问题解决：循环导入**
  - 导入链：`comparison/__init__` → `fine_grained` → `harmonize` → `loaders.base` → `loaders/__init__` → `gwd30` → `harmonize`（部分初始化）
  - 修复：`fine_grained.py` 中对 `_align_2d_surface` 使用函数内延迟导入
- **测试坐标修正**：原始生成的测试数据用 lat=[1.5, 0.5] / lon=[100.5, 101.5]，与 `create_comparison_grid((100,0,102,2), res=1.0)` 产生的 lat=[2.0, 1.0] / lon=[100.0, 101.0] 不对齐，导致 `Resampling.mode` 重投影结果不符预期。修正为匹配坐标。
- 映射表：FINE_4CLASS_MAPS（4 类）和 FINE_8CLASS_MAPS（8 类），已验证覆盖所有原始值
- GWD30 时间维处理：`scipy.stats.mode` + `xr.apply_ufunc(vectorize=True)`
- 9 个测试全部通过

### Step 3.2: hotspots.py — Shannon 熵 + 热点提取

- Shannon 熵公式：`H = -Σ(p_k * log2(p_k)) / log2(K)`，归一化到 [0, 1]
- 热点提取流水线：percentile 阈值 → `scipy.ndimage.label` 聚类 → size 过滤 → 区域分层（复用 `focus_areas._assign_region`）→ 距离去重（复用 `_is_far_enough`）
- **测试修正**：`min_cluster_cells` 测试最初用 `percentile_threshold=0.1`/`50.0`，但部分一致的 cell 也有非零熵，导致所有 cell 通过阈值。修正为：15 cell 完全一致（熵=0）+ 1 cell 不一致，用 `percentile_threshold=99.0` 确保只有 1 cell 通过
- 9 个测试全部通过

### Step 3.3: s2_reference.py + s2_batch.py + 脚本

- **S2 Cloud Score+ 模式**：`ee.Join.saveFirst('cloud_score')` 连接 S2_SR 和 CLOUD_SCORE_PLUS，`cs_cdf >= 0.60` 阈值掩膜，median composite
- **7 种终态**：downloaded, cached, unsupported_time_window, gee_auth_failed, empty_collection, download_failed, download_limit_exceeded
- **共享测试基础设施**：`tests/test_validation/conftest.py` 提取 `FakeEeModule`，新增 `FakeFilter`/`FakeJoin`/`FakeJoinInstance` 支持 S2 Cloud Score+ join 模式
- s2_batch.py 从 hotspot CSV 文件驱动批量下载
- HPC probe 脚本 + S2 下载 CLI 脚本
- 6 + 3 = 9 个测试全部通过

---

## 文件清单

### 新建 (11 files)

| 文件 | 用途 |
|------|------|
| `src/WA/comparison/fine_grained.py` | 4/8-class 分类调和 |
| `src/WA/comparison/hotspots.py` | Shannon 熵 + 热点 |
| `src/WA/validation/s2_reference.py` | S2 Cloud Score+ 下载 |
| `src/WA/s2_batch.py` | S2 批量下载 |
| `tests/test_comparison/test_fine_grained.py` | 9 tests |
| `tests/test_comparison/test_hotspots.py` | 9 tests |
| `tests/test_validation/test_s2_reference.py` | 6 tests |
| `tests/test_validation/conftest.py` | 共享 FakeEeModule |
| `tests/test_s2_batch.py` | 3 tests |
| `scripts/hpc_probe_fine_grained.py` | HPC 诊断入口 |
| `scripts/run_phase3_s2_downloads.py` | S2 下载 CLI |

### 修改 (2 files)

| 文件 | 变更 |
|------|------|
| `src/WA/comparison/__init__.py` | +fine_grained +hotspots 导出 |
| `src/WA/validation/__init__.py` | +s2_reference 导出 |

---

## HPC 验证命令

```bash
# 0. 本地 commit 后，用 sync-hpc 同步代码到 HPC
# 1. 在 HPC 上：
uv sync --extra dev
uv run python scripts/hpc_probe_fine_grained.py
# 成功后：
uv run python scripts/run_phase3_s2_downloads.py --phase3-root results/phase3/fine/probe --target-time 2019-07-01
```

---

## 已知风险

1. **GWD30 scipy.stats.mode 性能**：大区域 92-band 数据的 vectorized mode 可能较慢，必要时可改用 `np.bincount`
2. **热带持续多云**：S2 在热带区域可能 `empty_collection`，需扩大融合窗口
3. **未提交**：所有改动仍在工作区，需 commit 后用 sync-hpc rsync 到 HPC

---

## 项目进度

| Phase | 状态 | Tests |
|-------|------|-------|
| 1 — Loader Foundation | COMPLETE | 15 |
| 2 — Rough Binary + MODIS | COMPLETE | 82 |
| 2.5 — Tech Debt | COMPLETE | (included in 82) |
| **3 — Fine-Grained + Entropy + S2** | **COMPLETE** | **110** |
| 4 — Trend Analysis | NOT STARTED | — |
| 5 — Review Manifests & Docs | NOT STARTED | — |
