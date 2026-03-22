---
title: "feat: Phase 2 Rough Binary Comparison — Completion"
type: feat
status: active
date: 2026-03-19
parent: docs/plans/2026-03-19-002-feat-phase2345-comparison-trends-manifests-plan.md
---

# Phase 2 粗尺度二值对比 — 收尾计划

## Overview

Phase 2 的核心代码已实现（harmonize, rough_binary, focus_areas, gee_client, modis_reference, rough_probe）。剩余工作是 HPC 端到端验证。`Export.image.*` fallback 和 manifest 持久化推迟到 Phase 5。

## 已完成的交付物

| 文件 | 说明 |
|------|------|
| `src/WA/comparison/harmonize.py` | 二值化 + 月尺度聚合 + 网格对齐 |
| `src/WA/comparison/rough_binary.py` | pairwise metrics + disagreement score + vote fraction |
| `src/WA/comparison/focus_areas.py` | 区域分层 AOI 选取 + 去重 |
| `src/WA/validation/gee_client.py` | Earth Engine 懒加载包装 |
| `src/WA/validation/modis_reference.py` | MODIS 8-day 复合下载，6 种终态 |
| `src/WA/rough_probe.py` | HPC 粗尺度诊断 |
| `scripts/hpc_probe_rough_binary.py` | HPC CLI 入口 |

验证状态：43 tests passing, ruff clean, mypy clean。

## 剩余任务

### Task 2A: HPC 端到端验证

在 HPC 上运行完整 rough binary pipeline：

```bash
# 基础诊断（不下载 MODIS）
uv run python scripts/hpc_probe_rough_binary.py \
  --region tropical \
  --target-time 2019-07-01 \
  --json-out temp/rough_probe_tropical_201907.json

# 指定数据集子集（快速验证）
uv run python scripts/hpc_probe_rough_binary.py \
  --dataset g2017,glwd_v2,wad2m,swamps \
  --target-time 2019-07-01

# 带 MODIS 下载（需要 GEE 凭据）
uv run python scripts/hpc_probe_rough_binary.py \
  --region tropical \
  --target-time 2019-07-01 \
  --download-modis \
  --allow-interactive-auth
```

**验证检查项：**

- [ ] 至少 4 个数据集 `status=participating`（预期：g2017, glwd_v2, gwd30, swamps, wad2m, giems_mc, topmodel 中的大部分）
- [ ] `berkeley_rwawc` 输出 `status=skipped_not_eligible`
- [ ] pairwise metrics 全部有效（kappa, IoU, F1 非 NaN）
- [ ] `disagreement_score` 分布合理：max < 1.0, mean < 0.5
- [ ] focus AOIs 覆盖至少 3 个区域（brazil, indonesia, southeast_asia, africa）
- [ ] 无 `status=failed` 的数据集

**已知预期行为：**

- GIEMS-MC 时间范围 1993-2007，若 target_time=2019-07-01 则 `status=skipped_time_window`
- TOPMODEL 加载较慢（config x forcing 组合多）
- GWD30 tile 发现 ~33s，整体运行时间较长

### Task 2B: Export.image.* fallback

**决策：推迟到 Phase 5 的 `validation/export_policy.py` 统一实现。**

理由：
1. 粗尺度 AOI (2° x 2°, 500m MODIS) 大部分不超 32MB 限制
2. 细尺度 S2 (10m) 更可能触发，Phase 3/5 一并处理更合理
3. 当前 `download_limit_exceeded` 终态已正确识别，不丢数据

### Task 2C: Manifest 持久化

**决策：推迟到 Phase 5 的 `validation/manifests.py` 统一实现。**

当前 `ModisReferenceArtifact` dataclass 保留所有必要字段，Phase 5 仅需添加序列化层。

## Acceptance Criteria

- [ ] HPC rough binary probe 至少 4 个数据集 participating
- [ ] pairwise metrics 无 NaN 值
- [ ] focus AOIs 覆盖 >= 3 个区域
- [ ] rough_probe JSON 输出可正常解析
- [ ] 所有 non-participating 数据集有明确的 skip reason

## Phase 2 → Phase 3 接口

Phase 3 依赖 Phase 2 的以下接口：
- `harmonize.create_comparison_grid()` — 共享参考网格
- `harmonize._prepare_spatial_array()` / `_align_2d_surface()` — 空间对齐工具
- `focus_areas.DEFAULT_FOCUS_REGION_BBOXES` — 区域 bbox 定义
- `focus_areas._is_far_enough()` — 去重逻辑
- `gee_client.EarthEngineClient` — GEE 包装

---

# 英文摘要 (English Summary)

Phase 2 core code is complete. Remaining work is HPC end-to-end validation via `scripts/hpc_probe_rough_binary.py`. Export fallback and manifest persistence are deferred to Phase 5. The probe should confirm >= 4 datasets participating with valid pairwise metrics and geographically stratified focus AOIs.
