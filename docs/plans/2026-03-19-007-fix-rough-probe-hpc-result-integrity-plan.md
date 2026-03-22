---
title: "fix: Rough Probe HPC Result Integrity"
type: fix
status: active
date: 2026-03-19
parent: docs/plans/2026-03-19-003-feat-phase2-rough-binary-completion-plan.md
---

# Rough Probe HPC 结果完整性修复计划

## Overview

`temp/job.03.out.txt` 显示当前 rough probe 虽然能够跑完，但输出结果还不具备可靠的科学解释性。当前最关键的问题不是“没有结果”，而是“产生了看起来完整、实际上部分失真的结果”：

- `wad2m` 在粗尺度参与阶段直接失败。
- `glwd_v2` 被标记为 `participating`，但 harmonized surface 全为 `NaN`。
- `rough_probe` 在存在失败数据集时仍输出 `overall_status: completed`。
- `gwd30` 在某些年份会回退到极慢的 raster-bounds 扫描，导致 HPC 验证成本过高。

这份计划的目标是先把 rough comparison 的 **正确性和状态语义修正到位**，再处理性能硬化。

## Problem Statement

本次 HPC 运行暴露出的关键问题如下：

### 1. `WAD2M` 时间选择逻辑与真实时间轴不兼容

在 [temp/job.03.out.txt](temp/job.03.out.txt) 中，`wad2m` 已经成功加载出 `time: 1, lat: 4, lon: 4` 的数据，但在 `select_comparison_slice()` 阶段因为找不到 `2000-03-01` 精确时间戳而失败。

相关证据：

- [temp/job.03.out.txt](temp/job.03.out.txt) 中 `wad2m` 状态从 `load dataset` 成功进入 `harmonize binary surface`，随后抛出 `KeyError`。
- [src/WA/comparison/harmonize.py](/Users/mac/Code/WA/src/WA/comparison/harmonize.py#L185) 当前使用 `data.sel(time=timestamp)` 精确匹配。
- [docs/datasets/WAD2M.md](/Users/mac/Code/WA/docs/datasets/WAD2M.md) 明确显示 WAD2M 的时间坐标为 `2000-01-16`, `2000-02-15`, `2000-03-16` 这类月中时间，而不是月初时间。

这意味着当前 rough comparison 对“monthly 但不是 month-start timestamp”的数据集存在系统性兼容问题。

### 2. `GLWD v2` 被误判为有效参与者

在 [temp/job.03.out.txt](temp/job.03.out.txt) 中，`glwd_v2` 的 loader 成功返回了 `combined_classes` 与 area-by-class 数据，但 `harmonized_summary.non_null_count = 0`，说明最终进入 rough binary comparison 的 surface 全空。

相关证据：

- [temp/job.03.out.txt](temp/job.03.out.txt) 中 `glwd_v2` 状态是 `participating`，但 harmonized 结果 `min/max/mean` 全为 `null`。
- [src/WA/loaders/glwd.py](/Users/mac/Code/WA/src/WA/loaders/glwd.py#L47) 当前对 `combined_classes` 目录只取排序后的第一个 tif。
- [docs/datasets/GLWD v2.md](/Users/mac/Code/WA/docs/datasets/GLWD%20v2.md) 的数据 profile 明确给出了 `nodata: 255.0`。

这说明当前至少存在以下一种问题：

1. `combined_classes` 文件选择策略不稳定或选错文件。
2. `255` nodata 在进入二值映射前没有被显式掩膜。
3. 对齐/重采样后有效类别被全部冲刷掉，但 probe 仍把该数据集当成参与者。

### 3. Probe 的总体状态语义有误导性

在 [temp/job.03.out.txt](temp/job.03.out.txt) 中：

- `wad2m` 明确是 `failed`
- 但最终 `overall_status` 仍然是 `completed`

当前实现位于 [src/WA/rough_probe.py](/Users/mac/Code/WA/src/WA/rough_probe.py#L500)。现有逻辑只要 `participant_surfaces >= 2` 就将总体状态设置为 `completed`，没有把 failed dataset 纳入总状态判断。

这会让 HPC 验证脚本把“部分坏结果”伪装成“完成结果”，不利于后续自动化判断与人工排查。

### 4. `GWD30` 的 2016 回退路径过慢

`gwd30` 在这次 run 中被正确标记为 `skipped_time_window`，本身不是 correctness bug，但日志显示 2016 年 tile-code 预筛失败后回退到 raster-bounds scan，单年耗时接近 20 分钟。

这说明：

- GWD30 的 tile discovery 逻辑在部分年份/命名模式上不稳定。
- 当前 rough probe 的默认 HPC 验证成本偏高。

这不是第一优先级，但应该纳入同一修复计划作为后续硬化项。

## Proposed Solution

按“先 correctness，后 observability，最后 performance”的顺序修复。

### Phase 1: 修复 `WAD2M` 的 month-aware 时间选择

核心目标：

- 让 month-start target month 能正确匹配到 month-mid timestamp 数据集。

建议做法：

1. 保留 `select_comparison_slice()` 的 month-start 语义作为 rough comparison 的统一 target month。
2. 在 [src/WA/comparison/harmonize.py](/Users/mac/Code/WA/src/WA/comparison/harmonize.py#L185) 中把当前“精确时间戳选择”改为：
   - 先尝试 exact match；
   - exact match 失败时，按 `Period("M")` 做 month-level match；
   - 若匹配出 1 个切片，则返回该切片；
   - 若匹配出 0 个切片，则保留明确失败；
   - 若匹配出多个切片，则报 explicit ambiguity error。
3. 在返回的 attrs 里保留：
   - `comparison_time`：逻辑目标月
   - `comparison_source_time`：实际命中的原始时间戳

这样既兼容 WAD2M，也不会让时间选择逻辑失去可审计性。

### Phase 2: 修复 `GLWD v2` 的 `combined_classes` 有效值链路

核心目标：

- 保证 GLWD 在 rough binary workflow 中只有在真的产生有效 surface 时才算参与。

建议做法：

1. 在 [src/WA/loaders/glwd.py](/Users/mac/Code/WA/src/WA/loaders/glwd.py#L98) 替换 `_first_raster()`：
   - 优先按稳定命名规则选择 combined raster；
   - 若目录中存在多个 combined raster，必须显式判定，不再依赖字典序。
2. 在 GLWD loader 内对 `combined_classes` 的 nodata `255` 做显式掩膜，避免无效码进入后续映射。
3. 在 [src/WA/comparison/harmonize.py](/Users/mac/Code/WA/src/WA/comparison/harmonize.py#L228) 对 `glwd_v2` 的 `combined_classes` 进入二值映射前增加 sanity check：
   - 若映射后 `non_null_count == 0`，抛出一个明确的 comparison-layer error，而不是静默返回全空 surface。
4. 在 rough probe 中把这类情况标记为：
   - `failed_empty_harmonized_surface`
   或
   - `skipped_empty_harmonized_surface`
   而不是 `participating`。

### Phase 3: 修正 rough probe 的总体状态与摘要语义

核心目标：

- 让脚本对“部分成功”与“完整成功”给出明确区分。

建议做法：

1. 在 [src/WA/rough_probe.py](/Users/mac/Code/WA/src/WA/rough_probe.py#L500) 调整 overall status 逻辑：
   - 有 `failed_prepare` / `failed` 时：
     - 若 metrics 不可用，输出 `failed`
     - 若 metrics 可用，输出 `completed_with_failures`
   - 无失败但有 `skipped_*` 时：输出 `completed_with_skips`
   - 全部健康时：输出 `completed`
2. 在 Summary 中增加：
   - `failed_dataset_count`
   - `skipped_dataset_count`
   - `participating_dataset_count`
3. 如果 pairwise metrics 中 `valid_cell_count == 0` 的组合过多，增加警告摘要，而不是只打印表。

### Phase 4: 处理 `GWD30` 发现逻辑的性能退化

核心目标：

- 避免 2016 年等异常年份触发超慢 fallback。

建议做法：

1. 分析 2016 年 tile filename 是否不满足当前 tile-code 正则。
2. 在 [src/WA/loaders/gwd30.py](/Users/mac/Code/WA/src/WA/loaders/gwd30.py) 增强 `_extract_tile_code()` 的兼容性。
3. 若 filename 仍无法提取 tile code，则考虑：
   - 预缓存 raster bounds
   - 或对 fallback scan 加年份级缓存
4. 该阶段不应阻塞前 3 个 correctness 修复。

## Alternative Approaches Considered

### 1. 仅修改 rough probe 状态，不修底层逻辑

拒绝。这样只能让报告更诚实，不能让结果变正确。

### 2. 在 probe 中对 `WAD2M` 单独写特殊分支

拒绝。问题本质在 comparison layer 的时间选择逻辑，应该在 [harmonize.py](/Users/mac/Code/WA/src/WA/comparison/harmonize.py) 解决，而不是把兼容逻辑塞进 probe。

### 3. 暂时把 `GLWD v2` 排除出 rough comparison

不推荐作为最终方案。可作为短期保护措施，但会削弱 rough comparison 的静态分类对照能力。更合理的做法是先修 loader / nodata / sanity check。

## Technical Approach

### Architecture

```text
rough_probe.py
  -> prepare_datasets()
    -> loader.metadata()
    -> loader.load()
  -> harmonize_binary_dataset()
    -> _prepare_binary_source()
    -> _align_binary_fraction()
    -> select_comparison_slice()
  -> compute_rough_binary_metrics()
  -> select_focus_areas()
  -> render_rough_probe_report()
```

### Implementation Phases

#### Phase 1: Month-aware Comparison Slice

目标文件：

- [src/WA/comparison/harmonize.py](/Users/mac/Code/WA/src/WA/comparison/harmonize.py)
- [tests/test_comparison/test_harmonize.py](/Users/mac/Code/WA/tests/test_comparison/test_harmonize.py)

交付：

- `select_comparison_slice()` 支持 month-level fallback
- 保存 `comparison_source_time`
- 新增 mid-month monthly dataset 测试

成功标准：

- `wad2m` 不再因 `2000-03-01` 精确匹配失败而报错

#### Phase 2: GLWD Validity Chain Fix

目标文件：

- [src/WA/loaders/glwd.py](/Users/mac/Code/WA/src/WA/loaders/glwd.py)
- [src/WA/comparison/harmonize.py](/Users/mac/Code/WA/src/WA/comparison/harmonize.py)
- [tests/test_loaders/test_glwd.py](/Users/mac/Code/WA/tests/test_loaders/test_glwd.py)
- [tests/test_comparison/test_harmonize.py](/Users/mac/Code/WA/tests/test_comparison/test_harmonize.py)

交付：

- 稳定的 `combined_classes` 选择逻辑
- nodata=255 显式掩膜
- 空 harmonized surface 明确失败

成功标准：

- `glwd_v2` 在有真实有效像元时产生 `non_null_count > 0`
- 若全空，status 明确失败或跳过，不再伪装为参与者

#### Phase 3: Probe Status Integrity

目标文件：

- [src/WA/rough_probe.py](/Users/mac/Code/WA/src/WA/rough_probe.py)
- [tests/test_rough_probe.py](/Users/mac/Code/WA/tests/test_rough_probe.py)

交付：

- `completed_with_failures` / `completed_with_skips` 等状态
- 更准确的 summary 计数
- 对大量 `valid_cell_count == 0` 的 metrics 警告

成功标准：

- 有任何 failed dataset 时，`overall_status` 不再是裸 `completed`

#### Phase 4: GWD30 Discovery Hardening

目标文件：

- [src/WA/loaders/gwd30.py](/Users/mac/Code/WA/src/WA/loaders/gwd30.py)
- [tests/test_loaders/test_gwd30.py](/Users/mac/Code/WA/tests/test_loaders/test_gwd30.py)

交付：

- 2016 等年份 tile-code 识别增强
- 或 fallback 缓存策略

成功标准：

- 同 bbox 下 rough probe 不再在 2016 年出现 20 分钟级 fallback

## System-Wide Impact

### Interaction Graph

本次修复会影响以下调用链：

1. `scripts/hpc_probe_rough_binary.py`
2. `WA.rough_probe.run_rough_probe()`
3. `probe_prepared_dataset()`
4. `harmonize_binary_dataset()`
5. `select_comparison_slice()`
6. `compute_rough_binary_metrics()`
7. `render_rough_probe_report()`

其中：

- `WAD2M` bug 来自 comparison layer 的时间选择
- `GLWD` bug 横跨 loader + harmonize layer
- `overall_status` bug 只在 probe/report layer

### Error & Failure Propagation

当前失败模式：

- `WAD2M`: xarray `KeyError` 从 `data.sel(time=timestamp)` 直接冒泡到 probe
- `GLWD`: 没有异常，但返回全空 surface，最终在 metrics 中变成 `valid_cell_count = 0`
- `rough_probe`: dataset failure 没有被提升为 overall failure

修复后要求：

- 时间轴不匹配要么被 month-aware 兼容，要么给出显式 `failed_time_alignment`
- 全空 harmonized surface 必须显式状态化
- overall status 要反映底层真实失败

### State Lifecycle Risks

本次修复不涉及数据库或持久化状态，但涉及两类“结果状态”：

- `participant_surfaces`
- `run_result.status`

风险在于：

- 错误 surface 被放进 `participant_surfaces` 会污染 metrics
- 错误 status 会误导人工或自动化判断

### API Surface Parity

需要确保以下接口保持一致：

- `scripts/hpc_probe_rough_binary.py`
- `src/WA/rough_probe.py`
- `src/WA/comparison/harmonize.py`

不能只在 probe 里做数据集特判，而让 comparison core 继续保留错误语义。

### Integration Test Scenarios

必须覆盖至少以下跨层测试：

1. WAD2M 月中时间轴 + month-start target month 能正确命中 March slice
2. GLWD combined raster 含 `255` nodata 时，不会被误算成有效类别
3. GLWD harmonized surface 全空时，rough probe 报失败/跳过，不报 participating
4. 有 failed dataset 且仍有 metrics 时，overall status 为 `completed_with_failures`
5. GWD30 2016 filename 变体不会再触发极慢 fallback，或者 fallback 结果被缓存

## Acceptance Criteria

### Functional Requirements

- [ ] `wad2m` 在与 `2000-03-01` 类 target month 比较时不再抛 `KeyError`
- [ ] `glwd_v2` 不再出现“status=participating 但 harmonized non_null_count=0”的静默坏状态
- [ ] rough probe 在存在 failed dataset 时不再输出裸 `overall_status: completed`
- [ ] pairwise metrics 中因假参与导致的 `valid_cell_count = 0` 组合显著减少或被显式标注

### Non-Functional Requirements

- [x] 现有 Phase 2 API 保持兼容，不引入 config 改动
- [x] 修复后 HPC rough probe 仍保持详细输出
- [ ] GWD30 性能优化不牺牲正确性

### Quality Gates

- [x] `pytest` 通过
- [x] `ruff` 通过
- [x] `mypy` 通过
- [x] 需要新增针对 `WAD2M` 时间轴、`GLWD` nodata、probe 状态语义的测试

## Success Metrics

- `wad2m` 从 `status=failed` 变为 `status=participating`
- `glwd_v2` 的 `harmonized_summary.non_null_count > 0`，或明确进入 skip/fail 状态
- `overall_status` 与 dataset status counts 一致
- HPC rough probe 输出能被人类快速判断，不再需要人工追 traceback 才知道结果不可信

## Dependencies & Risks

### Dependencies

- Phase 2 comparison foundation 已完成
- rough probe 脚本已存在
- 不依赖 `config/` 修改

### Risks

- `GLWD` 目录内真实文件命名可能与当前推测不一致，需要先在 HPC 上列目录确认
- `WAD2M` 的时间轴问题修复后，可能还会暴露出真正的低值问题，但那将是科学结果，不是系统 bug
- `GWD30` 性能问题可能需要额外缓存层，改动面比 correctness 修复大

## Documentation Plan

- 更新本次修复对应的 plan 勾选
- 新增一份 stash，总结：
  - 根因
  - 修复点
  - HPC 复验结果

## Sources & References

### Internal References

- `temp/job.03.out.txt`
  - `wad2m` failed: lines near failure and traceback
  - `glwd_v2` harmonized all-NaN
  - `overall_status: completed` despite failures
- [src/WA/comparison/harmonize.py](/Users/mac/Code/WA/src/WA/comparison/harmonize.py#L185)
- [src/WA/loaders/glwd.py](/Users/mac/Code/WA/src/WA/loaders/glwd.py#L47)
- [src/WA/rough_probe.py](/Users/mac/Code/WA/src/WA/rough_probe.py#L500)
- [docs/plans/2026-03-19-003-feat-phase2-rough-binary-completion-plan.md](/Users/mac/Code/WA/docs/plans/2026-03-19-003-feat-phase2-rough-binary-completion-plan.md)

### Dataset Documentation

- [docs/datasets/WAD2M.md](/Users/mac/Code/WA/docs/datasets/WAD2M.md)
- [docs/datasets/GLWD v2.md](/Users/mac/Code/WA/docs/datasets/GLWD%20v2.md)

---

# English Summary

This plan addresses four issues exposed by `temp/job.03.out.txt`:

1. `wad2m` fails because rough comparison currently expects exact month-start timestamps.
2. `glwd_v2` is incorrectly treated as participating even when its harmonized surface is fully empty.
3. `rough_probe` reports `overall_status: completed` even when datasets fail.
4. `gwd30` has a severe year-specific performance fallback that should be hardened after correctness fixes.

The execution order is:

1. fix month-aware comparison slicing,
2. fix GLWD valid-data handling,
3. fix probe status semantics,
4. harden GWD30 discovery performance.
