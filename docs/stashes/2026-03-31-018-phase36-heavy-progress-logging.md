# Phase 3.6 海量进度日志

**Date:** 2026-03-31
**Branch:** `refactor/loader-reference-grid-alignment`
**Status:** 已为 Phase 3.6 增加高密度 INFO 日志，覆盖 CLI 参数、输入加载、缓存命中/缺失、每个缓存阶段开始/结束、每个纬向条带进度与统计、最终 summary/materialize 输出。

---

## 本次改动

| File | Change |
|------|--------|
| `src/WA/comparison/phase36.py` | 为 Phase3.6 全流程增加高密度 INFO 日志 |
| `scripts/run_phase3_6_global_entropy.py` | 启动时打印完整 CLI 参数，并在 dry-run 开始/结束时记录日志 |

## 现在会打印什么

### 1. 运行级日志

- `standardized_dir / output_dir / cache_dir / year / bbox / lat_chunk_size`
- `prefer_cache / write_cache`
- 最终输出路径与缓存运行目录

### 2. 输入加载日志

- 三个标准化分类数据集的加载开始
- 每个数据集的空间尺寸和变量数

### 3. 缓存日志

- grid template 命中 / 缺失 / 写入完成
- unified fraction 三个数据集分别命中 / 缺失 / 写入完成
- joint-valid / dominant / metrics / summary 的命中 / 缺失 / 写入完成
- 最终从 staged cache materialize 到正式输出目录的复制动作

### 4. 条带级日志（最密集）

每个纬向条带都会打印：

- 当前处理行号范围：`rows=start:stop/total`
- 当前条带行数：`nrows=...`
- 累计进度百分比：`percent=...%`
- unified fraction 阶段：每个数据集该条带的 `valid_cells`
- joint-valid 阶段：该条带的 `joint_valid`
- dominant 阶段：`valid_g2017 / valid_glwd_v2 / valid_gwd30`
- metrics 阶段：`joint_valid`、`entropy_mean`、`entropy_min`、`entropy_max`
- summary 阶段：该条带纳入 summary 的 `joint_valid`

### 5. 最终汇总日志

- summary 输出完成时的 `joint_valid_cell_count`
- 面积加权平均 entropy
- summary 文件路径

## 设计取向

- 所有日志使用 `INFO` 级别，默认 HPC 日志里就能看到，不需要额外开 debug。
- 日志偏“过程可审计”而不是简洁，因此输出会很多；这正是为了方便你在 HPC 上盯进度。
- 对于全局缓存重跑，日志会非常清楚地显示“哪里命中缓存，哪里真的在重算”。

## 验证

- `python -m py_compile src/WA/comparison/phase36.py scripts/run_phase3_6_global_entropy.py`
- `ruff check src/WA/comparison/phase36.py scripts/run_phase3_6_global_entropy.py tests/test_phase3_6_analysis.py`
- `python -m pytest tests/test_phase3_6_analysis.py -q`
- `python -m pytest tests/ -q`

结果：

- `ruff` 通过
- `tests/test_phase3_6_analysis.py`：`13 passed`
- 全量测试：`350 passed`

## 备注

- 当前日志密度已经足够高；如果后续你还想要更细，可以继续加“每个数据集 dominant class 直方图”或“每条带写盘耗时”。
- 目前没有引入额外的 `tqdm`，因为在 HPC 非交互日志中，纯文本 INFO 行更稳妥、更可追踪。
