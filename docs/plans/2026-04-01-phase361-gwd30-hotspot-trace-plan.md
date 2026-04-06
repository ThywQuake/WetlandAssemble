---
title: "feat: Phase 3.6.1 GWD30 hotspot 链路诊断方案"
type: feat
status: implemented
date: 2026-04-01
---

# Phase 3.6.1 GWD30 hotspot 链路诊断方案

## 目标

针对两个已存在的 hotspot，沿着 `raw tiles -> staged tiles -> reduced tiles -> final Phase 3.6 outputs`
四层链路做定点追踪，判断 GWD30 在 Phase 3.6 中出现大量 `Non-wetland` / `Water`
的异常究竟发生在哪一层。

## 核心思路

对每个 hotspot：

1. 读取 hotspot bbox
2. 在同一套 AOI reference grid 上分别跑三条 GWD30 路径
   - `raw`：`load_time_fraction_grid(...)`
   - `staged`：`merge_staged_time_fraction_tiles(...)`
   - `reduced`：直接从 `01_gwd30_phase36_annual_unified_v1/tile_*.nc` 重建
3. 分别输出
   - 命中的 tile 列表
   - annual unified fraction 摘要
   - `old argmax dominant`
   - `new wetland-first dominant`
4. 再与最终 `phase3_6_unified_classes_global_500m_2016.nc` 的 `gwd30_dominant_class`
   做逐格对比

## 预期判别

- `raw ≈ staged ≈ reduced`，但 `reduced != final`
  说明问题在 Phase 3.6 最终写出/拼接
- `raw ≈ staged`，但 `staged != reduced`
  说明问题在 tile-reduce / reduced tile 重建
- `raw != staged`
  说明问题在 staged tile 构建或 merge
- `raw` 本身就已经以 `0/1` 为主
  说明问题更上游，在原始 tile 到 coarse time fraction 的投影/汇总

## 产出

- 脚本：`scripts/inspect_phase3_6_1_gwd30_hotspots.py`
- 模块：`src/WA/phase361_gwd30_trace.py`
- 输出：`results/phase3.6.1/*_gwd30_trace.json`
- 汇总：`results/phase3.6.1/phase3_6_1_gwd30_hotspot_traces_2016.json`
