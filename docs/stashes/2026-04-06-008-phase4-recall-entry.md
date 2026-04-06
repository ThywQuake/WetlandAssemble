# 2026-04-06-008 Phase4 Recall Entry

## Summary

- 已完成项目 memory、Phase 计划、stash 时间线与当前分支状态回顾。
- 当前应恢复到 `Phase 4`，且以 **Phase 4 / Stage 2** 作为实际工作入口，而不是回到旧的 full-tropics reducer 路线。
- `gwd30` 的当前推荐链路是：
  1. Stage 1: 从 `standardized/_staging/gwd30_<year>/stage_shard_*.json` 构建 native pixel-statistics tiles
  2. Stage 2: `run_phase4_regional.py` 读取这些 Stage-1 tiles，并在区域级应用 Berkeley valid mask

## Current Phase

- Canonical status: `Phase 4 (Trend Analysis)` 已实现，并在最近几轮演进中收敛到新的两阶段区域分析入口。
- Active subphase: `Phase 4 Stage 2 regional integration`

## Last Completed Task

- 最近完成的是 Berkeley valid-mask 的 bbox OOM 修复：
  - Berkeley mask 构建时把 `bbox` 直接传给 `open_time_series(...)`
  - 避免先打开全域 Berkeley 标准化时间序列再裁剪
- 对应 stash:
  - `2026-04-06-005-phase4-stage2-pixel-stats-regional-integration.md`
  - `2026-04-06-006-phase4-berkeley-standardized-mask-source.md`
  - `2026-04-06-007-phase4-berkeley-mask-bbox-oom-fix.md`

## Current Entry Point

- Stage 1 builder:
  - `python scripts/build_phase4_gwd30_pixel_stats.py --year 2020 --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --aggregation monthly --worker-count 1 --no-skip`
- Stage 1 batch submit:
  - `bash scripts/submit_phase4_gwd30_pixel_stats.sh --aggregation monthly --worker-count 1 --cpus 1 --time 480 --partition C064M0256G --no-skip`
- Stage 2 regional run:
  - `python scripts/run_phase4_regional.py --dataset-id gwd30 --region amazon --standardized-dir /lustre/home/2200013429/Wetland_Assemble/data/standardized --output-root results/phase4 --start-year 2013 --end-year 2022 --no-skip`

## Open Risks

- 旧的 full-tropics shard reducer 路线仍在仓库中，但已不是推荐主链，且在 HPC 上有 OOM 历史。
- 真正的 Stage 3 / region-targeted trend analysis 还没有继续展开，当前完成的是 Stage 1 + Stage 2。
- 当前 git worktree 已有大量未提交改动与未跟踪文件；进入下一步实现前必须避免误覆盖已有工作。

## Verification Snapshot

- 最近 stash 记录的本地验证状态：
  - `python -m pytest tests/test_comparison/test_phase4_regional.py -q`
  - `python -m pytest tests/test_comparison/test_trends.py -q`
  - `python -m pytest tests/`
  - `ruff check ...`
- 本次 recall 只读取与总结，没有执行新的测试。
